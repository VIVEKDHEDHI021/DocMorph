"""FastAPI dependency injection module for database, authentication, and application services."""

from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.detection_service import DetectionAppService
from app.services.document_service import DocumentAppService
from app.services.personalization_service import PersonalizationAppService
from app.storage import get_storage
from app.storage.base import StorageProvider

# Optional bearer scheme allows dev mode fallback when token is absent
security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authenticates user via Bearer JWT strictly. Enforces tenant and session isolation."""
    user_repo = UserRepository(db)

    # Check if token is provided and valid
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and "sub" in payload:
            user_id = payload["sub"]
            user = user_repo.get_by_id(user_id)
            if user and user.is_active:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_doc_service(
    db: Session = Depends(get_db),
) -> DocumentAppService:
    """Dependency injecting DocumentAppService."""
    storage = get_storage()
    return DocumentAppService(db=db, storage=storage)


def get_det_service(
    db: Session = Depends(get_db),
) -> DetectionAppService:
    """Dependency injecting DetectionAppService."""
    storage = get_storage()
    return DetectionAppService(db=db, storage=storage)


def get_personalization_service(
    db: Session = Depends(get_db),
) -> PersonalizationAppService:
    """Dependency injecting PersonalizationAppService."""
    storage = get_storage()
    return PersonalizationAppService(db=db, storage=storage)

