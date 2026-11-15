"""Core PDF Analyzer Service for DocMorph.

Handles PDF validation, metadata extraction, page-by-page layout-preserving
text extraction, statistics calculation, and lifecycle management.
"""

from io import BytesIO
from pathlib import Path
import re
import time
from typing import Any, Optional
import pymupdf

from app.core.config import Settings, settings
from app.core.exceptions import (
    DocMorphError,
    EncryptedPDFError,
    InvalidFileTypeError,
    InvalidPDFError,
    PDFProcessingError,
    PDFValidationError,
    SecurityValidationError,
)
from app.schemas.pdf_data import (
    ExtractedPage,
    ExtractionSummary,
    PDFAnalysisResult,
    PDFMetadata,
)
from app.utils.file_validator import FileValidator


class PDFAnalyzer:
    """Production-grade PDF analysis engine.

    Thread-safe, stateless service responsible for safely inspecting PDFs,
    extracting structured metadata, and extracting normalized page text.
    """

    def __init__(self, config: Settings = settings) -> None:
        """Initialize the analyzer with application configuration.

        Args:
            config: Settings instance controlling file limits and defaults.
        """
        self.config = config

    def analyze(self, file_path: Path | str, base_dir: Path | None = None) -> PDFAnalysisResult:
        """Analyzes a PDF file from an on-disk path.

        Performs full validation, opens the document safely with context managers,
        extracts metadata and page text, and returns a structured response.

        Args:
            file_path: Path to the target PDF file.
            base_dir: Optional base directory to restrict path traversal.

        Returns:
            PDFAnalysisResult with complete metadata, page text, and summary.

        Raises:
            PDFValidationError: On validation, size, extension, or encryption failures.
            PDFProcessingError: If extraction fails due to internal parser issues.
        """
        start_time = time.perf_counter()

        # Step 1: File validation (extension, existence, size, magic bytes, path security)
        resolved_path = FileValidator.validate_file_path(
            file_path=file_path,
            base_dir=base_dir,
            config=self.config,
        )

        sanitized_filename = FileValidator.sanitize_filename(resolved_path.name)
        file_size = resolved_path.stat().st_size

        # Step 2: Safe Document Lifecycle Management with context manager
        try:
            with pymupdf.open(str(resolved_path)) as doc:
                # Step 3: Validate document integrity and encryption
                FileValidator.validate_pdf_document(doc)

                # Step 4: Extract metadata
                metadata = self.extract_metadata(
                    doc=doc,
                    filename=sanitized_filename,
                    file_size_bytes=file_size,
                )

                # Step 5: Extract page-by-page text
                pages = self.extract_pages(doc=doc)

                # Step 6: Compute document summary and statistics
                duration = time.perf_counter() - start_time
                summary = self.generate_summary(pages=pages, duration_seconds=duration)

                return PDFAnalysisResult(
                    filename=sanitized_filename,
                    metadata=metadata,
                    summary=summary,
                    pages=pages,
                )
        except (PDFValidationError, DocMorphError):
            # Re-raise domain validation errors directly
            raise
        except pymupdf.FileDataError as e:
            raise InvalidPDFError("The PDF document is corrupted, damaged, or unreadable.") from e
        except Exception as e:
            raise PDFProcessingError("An unexpected error occurred while processing the PDF.") from e

    def analyze_bytes(
        self,
        data: bytes,
        filename: str = "document.pdf",
    ) -> PDFAnalysisResult:
        """Analyzes an in-memory PDF byte stream (e.g. from FastAPI UploadFile).

        Args:
            data: Raw PDF bytes.
            filename: Original user-provided filename.

        Returns:
            PDFAnalysisResult structured model.

        Raises:
            PDFValidationError: If validation fails.
            PDFProcessingError: If extraction fails.
        """
        start_time = time.perf_counter()

        # Validate bytes and filename
        FileValidator.validate_bytes(data=data, filename=filename, config=self.config)
        sanitized_filename = FileValidator.sanitize_filename(filename)
        file_size = len(data)

        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                FileValidator.validate_pdf_document(doc)

                metadata = self.extract_metadata(
                    doc=doc,
                    filename=sanitized_filename,
                    file_size_bytes=file_size,
                )
                pages = self.extract_pages(doc=doc)
                duration = time.perf_counter() - start_time
                summary = self.generate_summary(pages=pages, duration_seconds=duration)

                return PDFAnalysisResult(
                    filename=sanitized_filename,
                    metadata=metadata,
                    summary=summary,
                    pages=pages,
                )
        except (PDFValidationError, DocMorphError):
            raise
        except pymupdf.FileDataError as e:
            raise InvalidPDFError("The PDF document is corrupted, damaged, or unreadable.") from e
        except Exception as e:
            raise PDFProcessingError("An unexpected error occurred while processing the PDF bytes.") from e

    def extract_metadata(
        self,
        doc: pymupdf.Document,
        filename: str,
        file_size_bytes: Optional[int] = None,
    ) -> PDFMetadata:
        """Extracts and normalizes document metadata.

        Safely handles missing or empty metadata fields without crashing.

        Args:
            doc: Open PyMuPDF document.
            filename: Clean filename of the document.
            file_size_bytes: Optional size in bytes.

        Returns:
            PDFMetadata model instance.
        """
        raw_meta: dict[str, Any] = getattr(doc, "metadata", {}) or {}

        def _clean_str(val: Any) -> Optional[str]:
            if val is None:
                return None
            s = str(val).strip()
            return s if s else None

        title = _clean_str(raw_meta.get("title"))
        author = _clean_str(raw_meta.get("author"))
        subject = _clean_str(raw_meta.get("subject"))
        creator = _clean_str(raw_meta.get("creator"))
        producer = _clean_str(raw_meta.get("producer"))
        pdf_version = _clean_str(raw_meta.get("format")) or (f"PDF {doc.version}" if hasattr(doc, "version") else None)

        creation_date = self._parse_pdf_date(_clean_str(raw_meta.get("creationDate")))
        modification_date = self._parse_pdf_date(_clean_str(raw_meta.get("modDate")))

        is_encrypted = bool(getattr(doc, "is_encrypted", False))

        return PDFMetadata(
            filename=filename,
            title=title,
            author=author,
            subject=subject,
            creator=creator,
            producer=producer,
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=doc.page_count,
            pdf_version=pdf_version,
            file_size_bytes=file_size_bytes,
            is_encrypted=is_encrypted,
        )

    def extract_pages(self, doc: pymupdf.Document) -> list[ExtractedPage]:
        """Extracts normalized text and metrics page-by-page.

        Preserves 1-indexed page numbering and sensible reading order.

        Args:
            doc: Open PyMuPDF document.

        Returns:
            List of ExtractedPage instances.
        """
        extracted_pages: list[ExtractedPage] = []

        for page_idx, page in enumerate(doc, start=1):
            # Extract text with sort=True to preserve top-to-bottom, left-to-right reading order
            raw_text = page.get_text("text", sort=True)
            normalized_text = self.normalize_text(raw_text)

            has_text = len(normalized_text) > 0
            word_count = len(normalized_text.split()) if has_text else 0
            char_count = len(normalized_text)

            # Check if page contains embedded images
            has_images = len(page.get_images()) > 0

            extracted_pages.append(
                ExtractedPage(
                    page_number=page_idx,
                    text=normalized_text,
                    character_count=char_count,
                    word_count=word_count,
                    has_text=has_text,
                    has_images=has_images,
                )
            )

        return extracted_pages

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalizes extracted text while preserving meaningful paragraphs and content.

        - Replaces CRLF and CR with LF.
        - Strips trailing whitespace on every line.
        - Replaces multiple consecutive horizontal spaces/tabs with a single space.
        - Collapses 3 or more consecutive newlines into 2 (preserving paragraph breaks).
        - Strips leading and trailing empty lines from the full block.

        Args:
            text: Raw extracted text string.

        Returns:
            Clean normalized text string.
        """
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Process line by line: normalize inline spaces, strip trailing spaces
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            # Replace multiple consecutive horizontal whitespace characters with a single space
            cleaned_line = re.sub(r"[ \t]+", " ", line).rstrip()
            cleaned_lines.append(cleaned_line)

        joined = "\n".join(cleaned_lines)

        # Collapse excess empty lines (e.g. 3 or more blank lines -> 2 blank lines)
        collapsed = re.sub(r"\n{3,}", "\n\n", joined)

        return collapsed.strip()

    @staticmethod
    def generate_summary(
        pages: list[ExtractedPage],
        duration_seconds: float,
    ) -> ExtractionSummary:
        """Calculates aggregate document statistics.

        Args:
            pages: List of extracted page data.
            duration_seconds: Elapsed processing time in seconds.

        Returns:
            ExtractionSummary instance.
        """
        total_pages = len(pages)
        pages_with_text = sum(1 for p in pages if p.has_text)
        empty_pages = sum(1 for p in pages if not p.has_text)
        total_chars = sum(p.character_count for p in pages)
        total_words = sum(p.word_count for p in pages)
        avg_chars = round(total_chars / total_pages, 2) if total_pages > 0 else 0.0

        formatted_duration = f"{duration_seconds:.4f}s"

        return ExtractionSummary(
            total_pages=total_pages,
            pages_with_text=pages_with_text,
            empty_pages=empty_pages,
            total_characters=total_chars,
            total_words=total_words,
            average_characters_per_page=avg_chars,
            status="success",
            processing_duration_seconds=round(duration_seconds, 6),
            processing_duration_formatted=formatted_duration,
        )

    @staticmethod
    def _parse_pdf_date(raw_date: Optional[str]) -> Optional[str]:
        """Parses PDF timestamp formats (e.g. D:YYYYMMDDHHMMSS) to readable ISO format.

        Args:
            raw_date: Raw date string from PDF metadata.

        Returns:
            Clean ISO-formatted timestamp or original string if parsing fails.
        """
        if not raw_date:
            return None

        # Standard PDF date format: D:YYYYMMDDHHmmSS[OHH'mm']
        match = re.match(r"^D:(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2}))?", raw_date)
        if match:
            year, month, day, hour, minute, second = match.groups()
            if hour and minute and second:
                return f"{year}-{month}-{day} {hour}:{minute}:{second}"
            return f"{year}-{month}-{day}"

        return raw_date

