"""Pytest fixtures for DocMorph automated test suite."""

import hashlib
from pathlib import Path
import pytest

from app.core.config import settings, Settings
from app.services.detection_engine import DetectionEngine
from app.services.pdf_analyzer import PDFAnalyzer
from app.services.pdf_replacer import PDFReplacer

# Configure test environment invariants
settings.ENVIRONMENT = "testing"
settings.RATE_LIMIT_ENABLED = False
settings.DATABASE_URL = "sqlite:///./test_docmorph.db"
from tests.create_sample import (
    create_ambiguous_field_pdf,
    create_conflicting_pdf,
    create_corrupted_pdf,
    create_empty_page_pdf,
    create_encrypted_pdf,
    create_landscape_practical_pdf,
    create_multiline_field_pdf,
    create_no_footer_pdf,
    create_sample_practical_pdf,
    create_varied_labels_pdf,
)


@pytest.fixture
def temp_test_dir(tmp_path: Path) -> Path:
    """Provides an isolated temporary directory for test artifacts."""
    return tmp_path


# --- Phase 1 Fixtures ---

@pytest.fixture
def sample_practical_pdf(tmp_path: Path) -> Path:
    """Generates a realistic 5-page practical report PDF in a temp directory."""
    pdf_path = tmp_path / "test_practical.pdf"
    create_sample_practical_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def sample_empty_and_image_pdf(tmp_path: Path) -> Path:
    """Generates a 3-page PDF with text, image-only, and blank pages."""
    pdf_path = tmp_path / "test_empty_image.pdf"
    create_empty_page_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    """Generates an encrypted/password-protected PDF."""
    pdf_path = tmp_path / "test_encrypted.pdf"
    create_encrypted_pdf(pdf_path, password="secret_pass_123")
    return pdf_path


@pytest.fixture
def corrupted_pdf(tmp_path: Path) -> Path:
    """Generates a corrupted PDF with truncated contents."""
    pdf_path = tmp_path / "test_corrupted.pdf"
    create_corrupted_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    """Creates a 0-byte file with .pdf extension."""
    pdf_path = tmp_path / "test_empty.pdf"
    pdf_path.write_bytes(b"")
    return pdf_path


@pytest.fixture
def non_pdf_file(tmp_path: Path) -> Path:
    """Creates a valid text file with a .txt extension."""
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("Hello World this is plain text.", encoding="utf-8")
    return txt_path


@pytest.fixture
def fake_signature_pdf(tmp_path: Path) -> Path:
    """Creates a file with .pdf extension but non-PDF contents (signature mismatch)."""
    fake_path = tmp_path / "fake.pdf"
    fake_path.write_text("THIS IS NOT A VALID PDF SIGNATURE AT ALL", encoding="utf-8")
    return fake_path


@pytest.fixture
def analyzer() -> PDFAnalyzer:
    """Provides a fresh PDFAnalyzer instance with default settings."""
    return PDFAnalyzer()


# --- Phase 2 Fixtures ---

@pytest.fixture
def landscape_pdf(tmp_path: Path) -> Path:
    """Generates a landscape-oriented practical PDF."""
    pdf_path = tmp_path / "test_landscape.pdf"
    create_landscape_practical_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def conflicting_pdf(tmp_path: Path) -> Path:
    """Generates a multi-page PDF with conflicting student names across pages."""
    pdf_path = tmp_path / "test_conflicting.pdf"
    create_conflicting_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def no_footer_pdf(tmp_path: Path) -> Path:
    """Generates a PDF without student credentials."""
    pdf_path = tmp_path / "test_no_footer.pdf"
    create_no_footer_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def multiline_field_pdf(tmp_path: Path) -> Path:
    """Generates a PDF where the label is on line 1 and value on line 2."""
    pdf_path = tmp_path / "test_multiline.pdf"
    create_multiline_field_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def varied_labels_pdf(tmp_path: Path) -> Path:
    """Generates a PDF testing varied labels and abbreviations."""
    pdf_path = tmp_path / "test_varied_labels.pdf"
    create_varied_labels_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def ambiguous_field_pdf(tmp_path: Path) -> Path:
    """Generates a PDF with missing and malformed field values."""
    pdf_path = tmp_path / "test_ambiguous.pdf"
    create_ambiguous_field_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def detection_engine() -> DetectionEngine:
    """Provides a fresh DetectionEngine instance with default settings."""
    return DetectionEngine()


@pytest.fixture
def pdf_replacer() -> PDFReplacer:
    """Provides a fresh PDFReplacer instance with default settings."""
    return PDFReplacer()


# --- Phase 4 API & Client Fixtures ---

@pytest.fixture
def client() -> "TestClient":
    """FastAPI TestClient instance with cleanly initialized database."""
    from fastapi.testclient import TestClient
    from app.server import app
    from app.db.session import engine, init_db
    from app.models.base import Base

    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_a_headers(client: "TestClient") -> dict[str, str]:
    """Provides JWT authorization headers for User A."""
    email = "usera@test.com"
    client.post("/api/v1/auth/signup", json={"email": email, "password": "Password123!", "full_name": "User Alpha"})
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b_headers(client: "TestClient") -> dict[str, str]:
    """Provides JWT authorization headers for User B."""
    email = "userb@test.com"
    client.post("/api/v1/auth/signup", json={"email": email, "password": "Password123!", "full_name": "User Beta"})
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file for integrity verification."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()
