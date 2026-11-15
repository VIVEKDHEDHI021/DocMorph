"""Authentication routes for DocMorph."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.api_schemas import Token, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/anonymous-session", response_model=Token, status_code=status.HTTP_201_CREATED)
def create_anonymous_session(db: Session = Depends(get_db)):
    """Creates a cryptographically secure isolated anonymous session token for account-free usage."""
    user_repo = UserRepository(db)
    session_uuid = uuid.uuid4().hex
    user = User(
        email=f"anon_{session_uuid[:16]}@session.docmorph.local",
        hashed_password=get_password_hash(uuid.uuid4().hex),
        full_name="Student",
        is_active=True,
        is_superuser=False,
    )
    created_user = user_repo.create(user)
    token = create_access_token(subject=created_user.id)
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(created_user),
    )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    """Registers a new user account."""
    user_repo = UserRepository(db)
    existing = user_repo.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    user = User(
        email=payload.email.lower().strip(),
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name or "",
        is_active=True,
    )
    return user_repo.create(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticates user credentials and returns a JWT access token."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated.",
        )

    token = create_access_token(subject=user.id)
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)

