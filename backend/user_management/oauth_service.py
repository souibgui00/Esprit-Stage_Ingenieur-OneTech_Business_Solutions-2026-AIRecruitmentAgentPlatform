import os
from typing import Optional, Dict, Any
from authlib.integrations.base_client import OAuthError
from authlib.integrations.requests_client import OAuth2Session
from sqlalchemy.orm import Session
from user_management.models import User
from user_management.security import hash_password, generate_verification_token, get_token_expiry
from datetime import datetime
import secrets

class OAuthService:
    def __init__(self):
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/google/callback")
        
        self.github_client_id = os.environ.get("GITHUB_CLIENT_ID")
        self.github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
        self.github_redirect_uri = os.environ.get("GITHUB_REDIRECT_URI", "http://localhost:3000/auth/github/callback")

    def get_google_auth_url(self) -> str:
        """Generate Google OAuth authorization URL."""
        if not self.google_client_id:
            raise ValueError("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")

        google = OAuth2Session(
            self.google_client_id,
            redirect_uri=self.google_redirect_uri,
            scope="openid email profile"
        )
        # Authlib's requests_client uses create_authorization_url(), not authorization_url()
        # access_type=offline requests a refresh token from Google
        url, state = google.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            access_type="offline",
            prompt="consent"
        )
        return url

    def get_github_auth_url(self) -> str:
        """Generate GitHub OAuth authorization URL."""
        if not self.github_client_id:
            raise ValueError("GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.")

        github = OAuth2Session(
            self.github_client_id,
            redirect_uri=self.github_redirect_uri,
            scope="user:email"
        )
        # Authlib's requests_client uses create_authorization_url()
        url, state = github.create_authorization_url(
            "https://github.com/login/oauth/authorize"
        )
        return url

    def handle_google_callback(self, code: str, db: Session) -> User:
        """Handle Google OAuth callback"""
        if not self.google_client_id or not self.google_client_secret:
            raise ValueError("Google OAuth not configured")
        
        google = OAuth2Session(
            self.google_client_id,
            redirect_uri=self.google_redirect_uri
        )
        
        try:
            # Fetch the access token
            token = google.fetch_token(
                "https://oauth2.googleapis.com/token",
                code=code,
                client_secret=self.google_client_secret
            )

            # Get user info — must call .json() to deserialise the response
            google = OAuth2Session(self.google_client_id, token=token)
            resp = google.get("https://www.googleapis.com/oauth2/v3/userinfo")
            resp.raise_for_status()
            user_info = resp.json()

            # Google v3 userinfo uses "sub" as the user identifier (not "id")
            google_id = user_info.get("sub") or user_info.get("id")
            email = user_info.get("email")
            if not email:
                raise ValueError("Google did not return an email address. Ensure 'email' scope is granted.")

            return self.get_or_create_oauth_user(
                db=db,
                provider="google",
                oauth_id=google_id,
                email=email,
                full_name=user_info.get("name"),
                avatar_url=user_info.get("picture")
            )

        except OAuthError as e:
            raise ValueError(f"Google OAuth error: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Google OAuth unexpected error: {str(e)}")

    def handle_github_callback(self, code: str, db: Session) -> User:
        """Handle GitHub OAuth callback"""
        if not self.github_client_id or not self.github_client_secret:
            raise ValueError("GitHub OAuth not configured")

        github = OAuth2Session(
            self.github_client_id,
            redirect_uri=self.github_redirect_uri
        )

        try:
            # Fetch the access token
            token = github.fetch_token(
                "https://github.com/login/oauth/access_token",
                code=code,
                client_secret=self.github_client_secret
            )

            # Get user info — must call .json() to deserialise the response
            github = OAuth2Session(self.github_client_id, token=token)

            resp = github.get("https://api.github.com/user")
            resp.raise_for_status()
            user_info = resp.json()

            # Get user email — GitHub requires a separate call; primary+verified email is mandatory
            email_resp = github.get("https://api.github.com/user/emails")
            email_resp.raise_for_status()
            email_list = email_resp.json()
            primary_email = next(
                (e["email"] for e in email_list if e.get("primary") and e.get("verified")),
                None
            )

            if not primary_email:
                raise ValueError("No verified primary email found on the GitHub account.")

            return self.get_or_create_oauth_user(
                db=db,
                provider="github",
                oauth_id=str(user_info["id"]),
                email=primary_email,
                full_name=user_info.get("name"),
                avatar_url=user_info.get("avatar_url")
            )

        except OAuthError as e:
            raise ValueError(f"GitHub OAuth error: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"GitHub OAuth unexpected error: {str(e)}")

    def get_or_create_oauth_user(
        self, 
        db: Session, 
        provider: str, 
        oauth_id: str, 
        email: str, 
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> User:
        """Get existing OAuth user or create new one (simplified for schema without OAuth fields)"""
        # Check if user exists with this email (since we don't have oauth_provider/oauth_id fields)
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            # Update user status if needed
            if not user.is_active:
                user.is_active = True
            db.commit()
            db.refresh(user)
            return user
        
        # Create new user (simplified - OAuth fields not stored in database)
        # OAuth users get a random password since hashed_password is NOT NULL
        import secrets
        from user_management.security import hash_password
        random_password = secrets.token_urlsafe(32)
        
        new_user = User(
            email=email,
            hashed_password=hash_password(random_password),  # OAuth users need a password (random)
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return new_user

# Singleton instance
oauth_service = OAuthService()