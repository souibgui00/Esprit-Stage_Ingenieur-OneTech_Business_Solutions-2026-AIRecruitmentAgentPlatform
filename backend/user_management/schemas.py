import uuid
import re
from datetime import datetime
from pydantic import BaseModel, field_validator

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str | None = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Veuillez entrer une adresse email valide (ex: jean.dupont@email.com)')
        if ' ' in v:
            raise ValueError('L\'email ne doit pas contenir d\'espaces')
        if v.startswith('.') or v.endswith('.'):
            raise ValueError('L\'email ne peut pas commencer ou finir par un point')
        return v

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule (A-Z)')
        if not re.search(r'[a-z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule (a-z)')
        if not re.search(r'\d', v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre (0-9)')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*(),.?":{}|<>)')
        return v

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: str | None = None
    timezone: str | None = None
    language: str | None = None
    email_notifications: bool | None = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule (A-Z)')
        if not re.search(r'[a-z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule (a-z)')
        if not re.search(r'\d', v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre (0-9)')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*(),.?":{}|<>)')
        return v

class ResetPasswordRequest(BaseModel):
    email: str

class ResetPasswordConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule (A-Z)')
        if not re.search(r'[a-z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule (a-z)')
        if not re.search(r'\d', v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre (0-9)')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*(),.?":{}|<>)')
        return v

class UpdateEmailRequest(BaseModel):
    new_email: str
    password: str

    @field_validator('new_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Veuillez entrer une adresse email valide (ex: jean.dupont@email.com)')
        return v

class Token(BaseModel):
    access_token: str
    refresh_token: str  # Always returned by every auth flow (login, OAuth callbacks, refresh)
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class VerifyEmailRequest(BaseModel):
    token: str

class TwoFactorSetup(BaseModel):
    enabled: bool
    code: str | None = None

class SessionResponse(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    expires_at: datetime | None
    is_active: bool
    is_current: bool  # Whether this is the current session

    class Config:
        from_attributes = True

class ActivityResponse(BaseModel):
    id: uuid.UUID
    action: str
    description: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class OAuthUrlResponse(BaseModel):
    authorization_url: str

class OAuthCallbackRequest(BaseModel):
    code: str


class UserPreferencesCreate(BaseModel):
    job_keywords: str | None = None
    preferred_locations: list[str] | None = None
    preferred_contract_types: list[str] | None = None
    remote_preference: bool | None = None
    min_salary: int | None = None
    target_roles: list[str] | None = None
    application_mode: str | None = None  # RECOMMEND_ONLY or AUTO_APPLY
    min_match_score: float | None = None
    max_applications_per_day: int | None = None


class UserPreferencesResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_keywords: str
    preferred_locations: list[str]
    preferred_contract_types: list[str]
    remote_preference: bool
    min_salary: int | None
    target_roles: list[str] = []
    application_mode: str = "RECOMMEND_ONLY"
    min_match_score: float = 80.0
    max_applications_per_day: int = 5
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
