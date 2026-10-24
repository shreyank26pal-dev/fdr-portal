"""Authentication (JWT + optional TOTP MFA) and role-based access control."""
from datetime import timedelta
from typing import Iterable

import bcrypt
import jwt
import pyotp
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import AICTE_ROLES, Role
from app.models import Instrument, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ----------------------------- passwords ---------------------------------- #
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ------------------------------- tokens ----------------------------------- #
def create_access_token(user: User) -> str:
    # real time (not simulated clock) so time-travel demos don't expire sessions
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])


# -------------------------------- MFA ------------------------------------- #
def new_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="SecureDeposit AICTE")


# ----------------------------- dependencies ------------------------------- #
def get_current_user(
    request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception:  # noqa: BLE001
        raise cred_exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise cred_exc
    # Auditors are strictly read-only, enforced for every endpoint.
    if user.role == Role.AUDITOR and request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Auditor role is read-only")
    return user


def require_roles(*roles: Role):
    allowed = set(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role {user.role.value} is not allowed. Needs one of: {', '.join(r.value for r in roles)}",
            )
        return user

    return _dep


# ------------------------------ scoping ----------------------------------- #
def can_view_instrument(user: User, inst: Instrument) -> bool:
    if user.role in (Role.ADMIN, Role.AUDITOR, Role.SCRUTINY_OFFICER, Role.APPROVING_AUTHORITY):
        return True
    if user.role == Role.REGIONAL_OFFICER:
        return inst.institution is not None and inst.institution.region == user.region
    if user.role == Role.INSTITUTION:
        return inst.institution_id == user.institution_id
    if user.role == Role.BANK:
        return user.bank_id is not None and inst.bank_id == user.bank_id
    return False


def ensure_can_view(user: User, inst: Instrument) -> None:
    if not can_view_instrument(user, inst):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")


def is_aicte(user: User) -> bool:
    return user.role in AICTE_ROLES


def roles_in(user: User, roles: Iterable[Role]) -> bool:
    return user.role in set(roles)

