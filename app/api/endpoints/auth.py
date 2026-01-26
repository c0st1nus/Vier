"""Authentication endpoints for user registration, login, and token management."""

import logging
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Register a new user.

    Args:
        user_data: User registration data (email, password)
        db: Database session

    Returns:
        TokenResponse: Access token, refresh token, and user info

    Raises:
        HTTPException: If email already exists
    """
    # Check if user already exists
    existing_user = await auth_service.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    try:
        user = await auth_service.create_user(db, user_data.email, user_data.password)
        logger.info(f"New user registered: {user.email}")
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    # Generate tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    # Save refresh token to database
    await auth_service.save_refresh_token(db, cast(int, user.id), refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=cast(int, user.id),
            email=cast(str, user.email),
            created_at=cast(datetime, user.created_at),
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Login with email and password.

    Args:
        credentials: User login credentials (email, password)
        db: Database session

    Returns:
        TokenResponse: Access token, refresh token, and user info

    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    user = await auth_service.authenticate_user(
        db, credentials.email, credentials.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"User logged in: {user.email}")

    # Generate tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    # Save refresh token to database
    await auth_service.save_refresh_token(db, cast(int, user.id), refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=cast(int, user.id),
            email=cast(str, user.email),
            created_at=cast(datetime, user.created_at),
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Refresh access token using refresh token.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        TokenResponse: New access token and refresh token

    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    # Verify refresh token
    user = await auth_service.verify_refresh_token(db, request.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"Token refreshed for user: {user.email}")

    # Generate new tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    new_refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    # Delete old refresh token and save new one
    await auth_service.delete_refresh_token(db, request.refresh_token)
    await auth_service.save_refresh_token(db, cast(int, user.id), new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse(
            id=cast(int, user.id),
            email=cast(str, user.email),
            created_at=cast(datetime, user.created_at),
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: RefreshTokenRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Logout user by invalidating refresh token.

    Args:
        request: Refresh token request
        current_user: Current authenticated user
        db: Database session

    Returns:
        None (204 No Content)
    """
    # Delete refresh token
    deleted = await auth_service.delete_refresh_token(db, request.refresh_token)
    if deleted:
        logger.info(f"User logged out: {current_user.email}")
    else:
        logger.warning(
            f"Logout attempted with invalid token by user: {current_user.email}"
        )

    # Return 204 regardless of whether token was found
    return None


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: User information
    """
    return UserResponse(
        id=cast(int, current_user.id),
        email=cast(str, current_user.email),
        created_at=cast(datetime, current_user.created_at),
    )
