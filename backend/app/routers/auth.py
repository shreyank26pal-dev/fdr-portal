from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import InstitutionOut, LoginIn, MfaVerifyIn, TokenOut, UserOut
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    new_totp_secret,
    totp_uri,
    verify_password,
    verify_totp,
)
from app.services import audit, clock

router = APIRouter(prefix="/auth", tags=["Auth"])


def _login(db: Session, email: str, password: str, otp: str | None) -> TokenOut:
    user = db.execute(select(User).where(User.email == email.lower())).scalar()
    if user is None or not user.is_active:
        raise HTTPException(401, "Invalid email or password")
    if user.failed_logins >= settings.MAX_FAILED_LOGINS:
        raise HTTPException(423, "Account locked after repeated failed logins. Contact the administrator.")
    if not verify_password(password, user.password_hash):
        user.failed_logins += 1
        audit.record(db, user, "LOGIN_FAILED", "user", user.id)
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    if user.mfa_enabled:
        if not otp:
            raise HTTPException(401, {"message": "OTP required", "mfa_required": True})
        if not verify_totp(user.totp_secret or "", otp):
            raise HTTPException(401, "Invalid OTP")
    user.failed_logins = 0
    user.last_login_at = clock.now()
    audit.record(db, user, "LOGIN", "user", user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut, summary="Login (JSON) - returns JWT")
def login(body: LoginIn, db: Session = Depends(get_db)):
    return _login(db, body.email, body.password, body.otp)


@router.post("/token", response_model=TokenOut, summary="OAuth2 form login (used by the Swagger 'Authorize' button)")
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, None)


@router.get("/me", summary="Current user + institution")
def me(user: User = Depends(get_current_user)):
    return {
        "user": UserOut.model_validate(user),
        "institution": InstitutionOut.model_validate(user.institution) if user.institution else None,
        "bank": {"id": user.bank.id, "name": user.bank.name} if user.bank else None,
        "simulated_today": clock.today(),
        "clock_offset_days": clock.offset_days(),
    }


@router.post("/mfa/setup", summary="Generate a TOTP secret (scan the otpauth URI in an authenticator app)")
def mfa_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.totp_secret = new_totp_secret()
    db.commit()
    return {"secret": user.totp_secret, "otpauth_uri": totp_uri(user.totp_secret, user.email)}


@router.post("/mfa/enable", summary="Confirm the first OTP to enable MFA")
def mfa_enable(body: MfaVerifyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.totp_secret or not verify_totp(user.totp_secret, body.otp):
        raise HTTPException(400, "Invalid OTP")
    user.mfa_enabled = True
    audit.record(db, user, "MFA_ENABLED", "user", user.id)
    db.commit()
    return {"mfa_enabled": True}


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    audit.record(db, user, "PASSWORD_CHANGED", "user", user.id)
    db.commit()
    return {"ok": True}
