"""DocMorph configuration module.

Defines runtime settings, security configurations, file limits, and storage paths.
Supports configuration via environment variables with the `DOCMORPH_` prefix.
"""

from pathlib import Path
import warnings
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DocMorph application settings and limits."""

    model_config = SettingsConfigDict(
        env_prefix="DOCMORPH_",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Metadata
    APP_NAME: str = "DocMorph"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production, testing
    DEBUG: bool = True

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost",
        "https://localhost",
        "capacitor://localhost",
    ]

    # Security & JWT Configuration
    SECRET_KEY: str = "docmorph-development-secret-key-super-secure-32bytes-minimum"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    DEV_AUTH_MODE: bool = False  # Strictly disabled: enforce unique isolated sessions per client

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 15
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 30
    RATE_LIMIT_API_PER_MINUTE: int = 180

    # Database Configuration (SQLite default for local dev, Postgres compatible)
    DATABASE_URL: str = "sqlite:///./docmorph.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True

    # Storage Backend Configuration (local | s3)
    STORAGE_BACKEND: str = "local"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "docmorph-documents"
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION: str = "auto"

    # PDF Engine Validation Limits
    MAX_FILE_SIZE_MB: int = 20  # Default maximum upload limit: 20 MB
    ALLOWED_EXTENSIONS: tuple[str, ...] = (".pdf",)
    ALLOWED_MIME_TYPES: tuple[str, ...] = ("application/pdf",)

    # Phase 2 Footer & Detection Engine Configuration
    FOOTER_HEIGHT_PERCENT: float = 0.20  # Default bottom 20%
    CONFIDENCE_HIGH_THRESHOLD: float = 0.90
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.70

    # Phase 3 Personalization & Replacement Configuration
    MIN_REPLACEMENT_FONT_SIZE: float = 6.0  # Lowest font size to scale long text before collision
    MAX_REPLACEMENT_TEXT_LENGTH: int = 100  # Reasonable upper bound on student field input
    DEFAULT_HORIZONTAL_PADDING: float = 2.0  # Buffer margin between text and neighboring elements

    # Base Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    INPUT_DIR: Path = BASE_DIR / "input"
    OUTPUT_DIR: Path = BASE_DIR / "output"
    STORAGE_DIR: Path = BASE_DIR / "storage"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Ensures production-grade security invariants."""
        if self.ENVIRONMENT.lower() == "production":
            # 1. Enforce strong non-default secret key
            if self.SECRET_KEY == "docmorph-development-secret-key-super-secure-32bytes-minimum":
                raise ValueError(
                    "CRITICAL: DOCMORPH_SECRET_KEY must be set to a secure secret in production!"
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("DOCMORPH_SECRET_KEY must be at least 32 characters in production.")

            # 2. Prevent wildcards in CORS origins
            if "*" in self.CORS_ORIGINS:
                self.CORS_ORIGINS = [orig for orig in self.CORS_ORIGINS if orig != "*"]
                warnings.warn(
                    "Wildcard CORS origin '*' removed for production compliance.",
                    UserWarning,
                    stacklevel=2,
                )

            # 3. Disable development bypasses in production
            self.DEV_AUTH_MODE = False
            self.DEBUG = False

        return self

    @property
    def max_file_size_bytes(self) -> int:
        """Returns the maximum allowed file size in bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def uploads_dir(self) -> Path:
        """Isolated private directory for uploaded source PDFs."""
        path = self.STORAGE_DIR / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def personalized_dir(self) -> Path:
        """Isolated private directory for personalized output PDFs."""
        path = self.STORAGE_DIR / "personalized"
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global singleton settings instance
settings = Settings()
