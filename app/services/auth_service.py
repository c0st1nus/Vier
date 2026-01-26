"""Authentication service for JWT tokens and password management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import RefreshToken, User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = (
    settings.SECRET_KEY
    if hasattr(settings, "SECRET_KEY")
    else secrets.token_urlsafe(32)
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(
        data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and verify a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, email: str, password: str) -> User:
        """Create a new user."""
        hashed_password = AuthService.hash_password(password)
        user = User(email=email, password_hash=hashed_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession, email: str, password: str
    ) -> Optional[User]:
        """Authenticate a user with email and password."""
        user = await AuthService.get_user_by_email(db, email)
        if not user:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def save_refresh_token(
        db: AsyncSession, user_id: int, token: str
    ) -> RefreshToken:
        """Save a refresh token to the database, ensuring uniqueness per token value."""
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        # Remove any existing rows with the same token to avoid unique constraint violations
        existing = await db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        existing_tokens = existing.scalars().all()
        for row in existing_tokens:
            await db.delete(row)

        refresh_token = RefreshToken(
            user_id=user_id, token=token, expires_at=expires_at
        )
        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)
        return refresh_token

    @staticmethod
    async def get_refresh_token(db: AsyncSession, token: str) -> Optional[RefreshToken]:
        """Get a refresh token from the database."""
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_refresh_token(db: AsyncSession, token: str) -> bool:
        """Delete a refresh token (logout)."""
        refresh_token = await AuthService.get_refresh_token(db, token)
        if refresh_token:
            await db.delete(refresh_token)
            await db.commit()
            return True
        return False

    @staticmethod
    async def verify_refresh_token(db: AsyncSession, token: str) -> Optional[User]:
        """Verify a refresh token and return associated user."""
        # Decode token
        payload = AuthService.decode_token(token)
        if not payload or payload.get("type") != "refresh":
            return None

        # Check if token exists in database and not expired
        refresh_token = await AuthService.get_refresh_token(db, token)
        if not refresh_token:
            return None

        if refresh_token.expires_at < datetime.utcnow():
            # Token expired, delete it
            await db.delete(refresh_token)
            await db.commit()
            return None

        # Get user
        user_id = payload.get("sub")
        if not user_id:
            return None

        return await AuthService.get_user_by_id(db, int(user_id))


# Singleton instance
auth_service = AuthService()
