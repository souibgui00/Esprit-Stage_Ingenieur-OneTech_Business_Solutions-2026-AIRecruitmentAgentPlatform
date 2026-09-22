from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import time
import uuid

from shared.database import get_db
from user_management.models import User, UserSession, UserActivity, UserPreferences, UserPasswordReset
from user_management.schemas import (
    UserCreate, UserResponse, Token, TokenData, UserUpdate, 
    ChangePassword, ResetPasswordRequest, ResetPasswordConfirm, 
    UpdateEmailRequest, RefreshTokenRequest, VerifyEmailRequest,
    TwoFactorSetup, SessionResponse, ActivityResponse,
    OAuthUrlResponse, OAuthCallbackRequest,
    UserPreferencesCreate, UserPreferencesResponse
)
from user_management.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    verify_token
)
from user_management.dependencies import get_current_user
from user_management.email_service import email_service
from user_management.oauth_service import oauth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory rate limiting for login and register attempts
login_attempts = {}
register_attempts = {}

def log_user_activity(db: Session, user_id: uuid.UUID, action: str, description: str = None,
                     ip_address: str = None, user_agent: str = None):
    """Log user activity for audit trail."""
    activity = UserActivity(
        user_id=user_id,
        action=action,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(activity)
    db.commit()

def get_client_info(request: Request) -> tuple:
    """Extract client IP and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Rate limiting: 3 registration attempts per minute per IP
    client_ip = "client"  # In production, use request.client.host
    current_time = time.time()
    
    # Clean old attempts (older than 1 minute)
    register_attempts[client_ip] = [t for t in register_attempts.get(client_ip, []) if current_time - t < 60]
    
    # Check rate limit
    if len(register_attempts.get(client_ip, [])) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives d'inscription. Réessayez dans 1 minute."
        )
    
    # Record this attempt
    register_attempts.setdefault(client_ip, []).append(current_time)
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé."
        )
    
    # Create user with only the fields that exist in the model
    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        is_active=True  # Auto-activate since verification is not implemented
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé."
        )

    # Log registration activity
    ip_address, user_agent = get_client_info(request)
    log_user_activity(db, new_user.id, "register", "User registered", ip_address, user_agent)

    return new_user

@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Rate limiting: 5 login attempts per minute per IP
    client_ip = "client"  # In production, use request.client.host
    current_time = time.time()
    
    # Clean old attempts (older than 1 minute)
    login_attempts[client_ip] = [t for t in login_attempts.get(client_ip, []) if current_time - t < 60]
    
    # Check rate limit
    if len(login_attempts.get(client_ip, [])) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de connexion. Réessayez dans 1 minute."
        )
    
    # Record this attempt
    login_attempts.setdefault(client_ip, []).append(current_time)
    
    # Authenticate user
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur inactif."
        )
    
    # Create JWT tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    # Create session
    ip_address, user_agent = get_client_info(request)
    session = UserSession(
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(session)
    db.commit()
    
    # Log login activity
    log_user_activity(db, user.id, "login", "User logged in", ip_address, user_agent)
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Invalidate current session
    ip_address, user_agent = get_client_info(request)
    session = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.token == request.headers.get("authorization", "").replace("Bearer ", ""),
        UserSession.is_active == True
    ).first()
    
    if session:
        session.is_active = False
        db.commit()
    
    # Log logout activity
    log_user_activity(db, current_user.id, "logout", "User logged out", ip_address, user_agent)
    
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user(user_update: UserUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only update fields that actually exist in the User model
    # UserUpdate schema has fields that don't exist in simplified schema
    # For now, this endpoint is effectively a no-op for profile updates
    # Real profile updates would require adding fields to User model
    
    # Log update activity
    ip_address, user_agent = get_client_info(request)
    log_user_activity(db, current_user.id, "profile_update", "User profile update attempted", ip_address, user_agent)
    
    return current_user

@router.post("/change-password")
def change_password(password_data: ChangePassword, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect."
        )
    
    current_user.hashed_password = hash_password(password_data.new_password)
    db.commit()
    
    # Log password change activity
    ip_address, user_agent = get_client_info(request)
    log_user_activity(db, current_user.id, "password_change", "User changed password", ip_address, user_agent)
    
    return {"message": "Password changed successfully"}

@router.post("/forgot-password")
def forgot_password(request_data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Request a password reset link.
    Always returns the same response regardless of whether the email exists
    to prevent user enumeration.
    """
    from user_management.security import generate_reset_token, get_token_expiry

    user = db.query(User).filter(User.email == request_data.email).first()
    if not user:
        # Security: do not reveal whether the email is registered
        return {"message": "If the email exists, a reset link has been sent."}

    # Invalidate any existing unused tokens for this user
    db.query(UserPasswordReset).filter(
        UserPasswordReset.user_id == user.id,
        UserPasswordReset.is_used == False
    ).update({"is_used": True})

    # Generate a cryptographically secure token (URL-safe, 48 bytes → 64 chars)
    raw_token = generate_reset_token()

    reset_entry = UserPasswordReset(
        user_id=user.id,
        token=raw_token,
        expires_at=get_token_expiry(hours=1)  # Valid for 1 hour
    )
    db.add(reset_entry)
    db.commit()

    # Attempt to send email; fall back to logging the link in development
    sent = email_service.send_password_reset_email(user.email, raw_token)
    if not sent:
        import logging
        logging.getLogger(__name__).warning(
            "[DEV] SMTP unavailable — password reset link: "
            f"%s/auth/reset-password?token=%s",
            email_service.frontend_url, raw_token
        )

    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(reset_data: ResetPasswordConfirm, db: Session = Depends(get_db)):
    """
    Consume a password reset token and set a new password.
    Validates: token existence, expiry, single-use state, and password strength.
    """
    from datetime import timezone

    invalid_exc = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Le lien de réinitialisation est invalide ou a expiré."
    )

    reset_entry = db.query(UserPasswordReset).filter(
        UserPasswordReset.token == reset_data.token
    ).first()

    if not reset_entry:
        raise invalid_exc

    if reset_entry.is_used:
        raise invalid_exc

    # Compare expiry against UTC now (both are naive UTC datetimes)
    now_utc = datetime.utcnow()
    if reset_entry.expires_at < now_utc:
        raise invalid_exc

    # Retrieve the user
    user = db.query(User).filter(User.id == reset_entry.user_id).first()
    if not user or not user.is_active:
        raise invalid_exc

    # Hash and store the new password
    user.hashed_password = hash_password(reset_data.new_password)

    # Mark token as used (prevents replay)
    reset_entry.is_used = True

    # Invalidate all active sessions to force re-login with new password
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.is_active == True
    ).update({"is_active": False})

    db.commit()

    return {"message": "Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter."}

@router.post("/verify-email")
def verify_email(verification_data: VerifyEmailRequest, db: Session = Depends(get_db)):
    # Email verification not implemented - simplified schema
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email verification functionality not available in simplified schema"
    )

@router.post("/request-email-verification")
def request_email_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Email verification not implemented - simplified schema
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email verification functionality not available in simplified schema"
    )

@router.post("/update-email")
def update_email(email_data: UpdateEmailRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Email update not implemented - simplified schema
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email update functionality not available in simplified schema"
    )

@router.post("/refresh-token", response_model=Token)
def refresh_token(token_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    # Verify refresh token
    payload = verify_token(token_data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if session exists and is active
    session = db.query(UserSession).filter(
        UserSession.refresh_token == token_data.refresh_token,
        UserSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    # Get user
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Generate new tokens
    access_token = create_access_token(data={"sub": user.email})
    new_refresh_token = create_refresh_token(data={"sub": user.email})
    
    # Update session
    session.token = access_token
    session.refresh_token = new_refresh_token
    session.expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()
    
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@router.get("/sessions", response_model=list[SessionResponse])
def get_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).order_by(UserSession.created_at.desc()).all()
    
    # Mark current session (you'd need to pass the current token)
    # For simplicity, we'll just return all sessions
    return sessions

@router.delete("/sessions/{session_id}")
def revoke_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.is_active = False
    db.commit()
    
    return {"message": "Session revoked"}

@router.get("/activity", response_model=list[ActivityResponse])
def get_activity(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 50):
    activities = db.query(UserActivity).filter(
        UserActivity.user_id == current_user.id
    ).order_by(UserActivity.created_at.desc()).limit(limit).all()
    
    return activities

@router.delete("/account")
def delete_account(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Log account deletion activity
    ip_address, user_agent = get_client_info(request)
    log_user_activity(db, current_user.id, "account_deletion", "User deleted account", ip_address, user_agent)
    
    # Deactivate user instead of deleting (soft delete)
    current_user.is_active = False
    current_user.email = f"deleted_{current_user.id}@deleted.com"  # Make email unusable
    # Set password to a random hash to prevent any potential authentication
    from user_management.security import hash_password
    import secrets
    random_password = secrets.token_urlsafe(32)
    current_user.hashed_password = hash_password(random_password)
    db.commit()
    
    return {"message": "Account deleted successfully"}

# OAuth endpoints
@router.get("/google/auth-url", response_model=OAuthUrlResponse)
def get_google_auth_url():
    """Get Google OAuth authorization URL"""
    try:
        authorization_url = oauth_service.get_google_auth_url()
        return {"authorization_url": authorization_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/google/callback", response_model=Token)
def google_callback(callback_data: OAuthCallbackRequest, request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        user = oauth_service.handle_google_callback(callback_data.code, db)
        
        # Create JWT tokens
        access_token = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})
        
        # Create session
        ip_address, user_agent = get_client_info(request)
        session = UserSession(
            user_id=user.id,
            token=access_token,
            refresh_token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(session)
        db.commit()
        
        # Log OAuth login activity
        log_user_activity(db, user.id, "oauth_login", "User logged in via Google", ip_address, user_agent)
        
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/github/auth-url", response_model=OAuthUrlResponse)
def get_github_auth_url():
    """Get GitHub OAuth authorization URL"""
    try:
        authorization_url = oauth_service.get_github_auth_url()
        return {"authorization_url": authorization_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/github/callback", response_model=Token)
def github_callback(callback_data: OAuthCallbackRequest, request: Request, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    try:
        user = oauth_service.handle_github_callback(callback_data.code, db)
        
        # Create JWT tokens
        access_token = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})
        
        # Create session
        ip_address, user_agent = get_client_info(request)
        session = UserSession(
            user_id=user.id,
            token=access_token,
            refresh_token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(session)
        db.commit()
        
        # Log OAuth login activity
        log_user_activity(db, user.id, "oauth_login", "User logged in via GitHub", ip_address, user_agent)
        
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# User Preferences endpoints
@router.get("/preferences", response_model=UserPreferencesResponse)
def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's job search preferences. Creates default preferences if not set."""
    preferences = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    if not preferences:
        # Create default preferences
        preferences = UserPreferences(
            user_id=current_user.id,
            job_keywords="developer python react javascript",
            preferred_locations=[],
            preferred_contract_types=[],
            remote_preference=False,
            min_salary=None
        )
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    return preferences


@router.put("/preferences", response_model=UserPreferencesResponse)
def update_user_preferences(
    preferences_in: UserPreferencesCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's job search preferences."""
    preferences = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    if not preferences:
        # Create if doesn't exist
        preferences = UserPreferences(
            user_id=current_user.id,
            job_keywords=preferences_in.job_keywords or "developer python react javascript",
            preferred_locations=preferences_in.preferred_locations or [],
            preferred_contract_types=preferences_in.preferred_contract_types or [],
            remote_preference=preferences_in.remote_preference if preferences_in.remote_preference is not None else False,
            min_salary=preferences_in.min_salary
        )
        db.add(preferences)
    else:
        # Update existing
        if preferences_in.job_keywords is not None:
            preferences.job_keywords = preferences_in.job_keywords
        if preferences_in.preferred_locations is not None:
            preferences.preferred_locations = preferences_in.preferred_locations
        if preferences_in.preferred_contract_types is not None:
            preferences.preferred_contract_types = preferences_in.preferred_contract_types
        if preferences_in.remote_preference is not None:
            preferences.remote_preference = preferences_in.remote_preference
        if preferences_in.min_salary is not None:
            preferences.min_salary = preferences_in.min_salary
        if preferences_in.target_roles is not None:
            preferences.target_roles = preferences_in.target_roles
        if preferences_in.application_mode is not None:
            preferences.application_mode = preferences_in.application_mode
        if preferences_in.min_match_score is not None:
            preferences.min_match_score = preferences_in.min_match_score
        if preferences_in.max_applications_per_day is not None:
            preferences.max_applications_per_day = preferences_in.max_applications_per_day
    
    db.commit()
    db.refresh(preferences)
    return preferences
