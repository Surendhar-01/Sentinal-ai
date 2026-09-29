from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

ROLES = ("admin", "approver", "analyst", "viewer")

PERMISSIONS: dict[str, tuple[str, ...]] = {
    "documents:read": ("admin", "approver", "analyst", "viewer"),
    "documents:write": ("admin", "analyst"),
    "documents:delete": ("admin",),
    "knowledge:search": ("admin", "approver", "analyst", "viewer"),
    "agents:read": ("admin", "approver", "analyst", "viewer"),
    "tools:read": ("admin", "approver", "analyst", "viewer"),
    "executions:run": ("admin", "analyst"),
    "executions:read": ("admin", "approver", "analyst", "viewer"),
    "chat:run": ("admin", "analyst"),
    "tasks:read": ("admin", "approver", "analyst", "viewer"),
    "tasks:write": ("admin",),
    "evidence:read": ("admin", "approver", "analyst", "viewer"),
    "evidence:write": ("admin", "analyst"),
    "approvals:read": ("admin", "approver", "analyst", "viewer"),
    "approvals:request": ("admin", "analyst"),
    "approvals:decide": ("admin", "approver"),
    "audit:read": ("admin", "approver"),
    "users:read": ("admin",),
    "users:write": ("admin",),
}

DEFAULT_PASSWORDS = {
    "admin": "sentinel-admin",
    "approver": "sentinel-approver",
    "analyst": "sentinel-analyst",
    "viewer": "sentinel-viewer",
}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def has_permission(role: str, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, ())


def permissions_for(role: str) -> list[str]:
    return sorted(name for name, roles in PERMISSIONS.items() if role in roles)


def create_access_token(username: str, role: str, ttl_hours: int | None = None) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours or settings.jwt_ttl_hours)
    return jwt.encode(
        {"sub": username, "role": role, "permissions": permissions_for(role), "exp": expires},
        settings.secret_key,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except (JWTError, TypeError):
        return None


def get_user_by_token(token: str, db: Session) -> User | None:
    payload = decode_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired credentials")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require(*permissions: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        missing = [name for name in permissions if not has_permission(user.role, name)]
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not permitted to perform this action ({', '.join(missing)})",
            )
        return user

    return dependency


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403, detail=f"Role '{user.role}' is not one of: {', '.join(roles)}"
            )
        return user

    return dependency


def seed_users(db: Session) -> dict:
    created = {}
    for username, password in DEFAULT_PASSWORDS.items():
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, password_hash=hash_password(password), role=username))
            created[username] = password
    db.commit()
    return created
