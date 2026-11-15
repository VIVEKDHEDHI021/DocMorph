"""Automated test suite for DocMorph Phase 1 Core PDF Engine.

Covers:
- File validation (signatures, extensions, size limits, corruption, encryption, path traversal)
- Metadata extraction (presence, missing fields, dates, versions)
- Page-by-page text extraction (ordering, layouts, normalization, blank/image-only pages)
- Document reliability (lifecycle closure, immutability of inputs, error containment)
- In-memory stream analysis
- CLI interface functionality
"""

import hashlib
from pathlib import Path
import subprocess
import sys
import pytest
import pymupdf

from app.core.config import Settings
from app.core.exceptions import (
    DocMorphError,
    EmptyFileError,
    EncryptedPDFError,
    FileTooLargeError,
    InvalidFileTypeError,
    InvalidPDFError,
    PDFValidationError,
    SecurityValidationError,
)
from app.schemas.pdf_data import PDFAnalysisResult
from app.services.pdf_analyzer import PDFAnalyzer
from app.utils.file_validator import FileValidator
from tests.conftest import compute_file_sha256


# ==============================================================================
# SECTION A: FILE VALIDATION TESTS
# ==============================================================================

class TestFileValidation:
    """Test suite for PDF file validation security and integrity checks."""

    def test_valid_pdf_accepted(self, analyzer: PDFAnalyzer, sample_practical_pdf: Path) -> None:
        """Verifies that a well-formed PDF is successfully validated and analyzed."""
        result = analyzer.analyze(sample_practical_pdf)
        assert isinstance(result, PDFAnalysisResult)
        assert result.filename == sample_practical_pdf.name
        assert result.summary.status == "success"
        assert result.summary.total_pages == 5

    def test_invalid_extension_rejected(self, analyzer: PDFAnalyzer, non_pdf_file: Path) -> None:
        """Verifies that non-PDF extensions (.txt, .docx, etc.) are rejected."""
        with pytest.raises(InvalidFileTypeError) as exc_info:
            analyzer.analyze(non_pdf_file)
        assert "Unsupported file extension" in str(exc_info.value)
        assert non_pdf_file.name not in str(exc_info.value) or ".txt" in str(exc_info.value)

    def test_incorrect_pdf_signature_rejected(
        self, analyzer: PDFAnalyzer, fake_signature_pdf: Path
    ) -> None:
        """Verifies that files with .pdf extension but missing %PDF- magic bytes are rejected."""
        with pytest.raises(InvalidFileTypeError) as exc_info:
            analyzer.analyze(fake_signature_pdf)
        assert "magic bytes" in str(exc_info.value) or "signature" in str(exc_info.value)

    def test_empty_file_rejected(self, analyzer: PDFAnalyzer, empty_pdf: Path) -> None:
        """Verifies that 0-byte PDF files are rejected with EmptyFileError."""
        with pytest.raises(EmptyFileError) as exc_info:
            analyzer.analyze(empty_pdf)
        assert "empty (0 bytes)" in str(exc_info.value)

    def test_file_larger_than_configured_limit_rejected(
        self, sample_practical_pdf: Path, tmp_path: Path
    ) -> None:
        """Verifies that files exceeding the configured maximum size are rejected."""
        # Create an analyzer with a strict 1 KB limit to test size enforcement
        strict_config = Settings(MAX_FILE_SIZE_MB=0)
        # Manually set a tiny limit: 100 bytes
        strict_analyzer = PDFAnalyzer(config=strict_config)

        # The sample PDF is ~13KB, which will exceed 0 MB (0 bytes)
        with pytest.raises(FileTooLargeError) as exc_info:
            strict_analyzer.analyze(sample_practical_pdf)
        assert "exceeds maximum allowed limit" in str(exc_info.value)

    def test_corrupted_pdf_rejected(self, analyzer: PDFAnalyzer, corrupted_pdf: Path) -> None:
        """Verifies that corrupted, damaged, or truncated PDF files are rejected."""
        with pytest.raises(InvalidPDFError) as exc_info:
            analyzer.analyze(corrupted_pdf)
        assert "corrupted" in str(exc_info.value).lower() or "damaged" in str(exc_info.value).lower()

    def test_encrypted_pdf_rejected(self, analyzer: PDFAnalyzer, encrypted_pdf: Path) -> None:
        """Verifies that password-protected and encrypted PDFs are rejected with EncryptedPDFError."""
        with pytest.raises(EncryptedPDFError) as exc_info:
            analyzer.analyze(encrypted_pdf)
        assert "password-protected or encrypted" in str(exc_info.value)

    def test_path_traversal_in_filename_rejected(self) -> None:
        """Verifies that directory traversal patterns ('..') in filenames are caught."""
        dangerous_filenames = [
            "../../etc/passwd.pdf",
            "..\\..\\Windows\\System32\\cmd.pdf",
            "normal_file/../../../sensitive.pdf",
            "file\0hidden.pdf",
        ]
        for bad_name in dangerous_filenames:
            with pytest.raises(SecurityValidationError) as exc_info:
                FileValidator.sanitize_filename(bad_name)
            assert "traversal" in str(exc_info.value).lower() or "null" in str(exc_info.value).lower()

    def test_path_traversal_boundary_enforcement(
        self, tmp_path: Path, sample_practical_pdf: Path
    ) -> None:
        """Verifies that paths resolving outside an enforced base directory are rejected."""
        sub_dir = tmp_path / "allowed_folder"
        sub_dir.mkdir()

        # sample_practical_pdf is in tmp_path, not in sub_dir
        with pytest.raises(SecurityValidationError) as exc_info:
            FileValidator.validate_file_path(sample_practical_pdf, base_dir=sub_dir)
        assert "outside the allowed directory" in str(exc_info.value)

    def test_nonexistent_file_rejected(self, analyzer: PDFAnalyzer, tmp_path: Path) -> None:
        """Verifies that non-existent paths raise InvalidPDFError without system path leaks."""
        missing_path = tmp_path / "does_not_exist.pdf"
        with pytest.raises(InvalidPDFError) as exc_info:
            analyzer.analyze(missing_path)
        assert "does not exist" in str(exc_info.value)


# ==============================================================================
# SECTION B: METADATA EXTRACTION TESTS
# ==============================================================================

class TestMetadataExtraction:
    """Test suite for PDF metadata extraction and normalization."""

    def test_page_count_extracted_correctly(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies that the page count is exact."""
        result = analyzer.analyze(sample_practical_pdf)
        assert result.metadata.page_count == 5
        assert result.summary.total_pages == 5

    def test_available_metadata_extracted(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies that title, author, subject, creator, and producer are correctly captured."""
        result = analyzer.analyze(sample_practical_pdf)
        meta = result.metadata
        assert meta.title == "CS-301 Data Structures Practical Manual"
        assert meta.author == "Rahul Patel"
        assert meta.subject == "Computer Science Lab Practical Submission"
        assert meta.creator == "DocMorph Test Suite"
        assert meta.producer == "PyMuPDF PDF Generator"
        assert meta.is_encrypted is False
        assert meta.creation_date is not None
        assert "2026-10-31" in meta.creation_date
        assert meta.file_size_bytes is not None
        assert meta.file_size_bytes > 0

    def test_missing_metadata_handled_gracefully(self, tmp_path: Path, analyzer: PDFAnalyzer) -> None:
        """Verifies that PDFs with no metadata fields do not crash and return None values."""
        pdf_path = tmp_path / "no_meta.pdf"
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Sample content without metadata")
        # Explicitly empty metadata
        doc.set_metadata({})
        doc.save(str(pdf_path))
        doc.close()

        result = analyzer.analyze(pdf_path)
        assert result.metadata.page_count == 1
        assert result.metadata.title is None
        assert result.metadata.author is None
        assert result.metadata.subject is None


# ==============================================================================
# SECTION C: PAGE-BY-PAGE TEXT EXTRACTION TESTS
# ==============================================================================

class TestTextExtraction:
    """Test suite for page text extraction, ordering, statistics, and edge cases."""

    def test_five_page_document_extracted(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies all five pages are extracted with 1-based indexing."""
        result = analyzer.analyze(sample_practical_pdf)
        assert len(result.pages) == 5

        page_numbers = [p.page_number for p in result.pages]
        assert page_numbers == [1, 2, 3, 4, 5]

    def test_expected_content_extracted(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies that specific personal and academic content is extracted accurately."""
        result = analyzer.analyze(sample_practical_pdf)

        # Check required personal information present on all pages
        for p in result.pages:
            assert "Rahul Patel" in p.text
            assert "2300012345" in p.text
            assert "Roll No: 25" in p.text
            assert f"Page {p.page_number} of 5" in p.text

        # Check specific practical topics on individual pages
        assert "Practical 1: Implementation of Stack using Arrays" in result.pages[0].text
        assert "Practical 2: Singly Linked List" in result.pages[1].text
        assert "Practical 3: Binary Search Tree" in result.pages[2].text
        assert "Practical 4: Graph Traversal & Algorithm Comparison Matrix" in result.pages[3].text
        assert "Practical 5: Sorting Algorithms Empirical Analysis" in result.pages[4].text

    def test_distinct_tabular_layout_extracted(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies extraction of Page 4's tabular benchmark layout."""
        result = analyzer.analyze(sample_practical_pdf)
        p4_text = result.pages[3].text

        assert "Algorithm" in p4_text
        assert "BFS" in p4_text
        assert "DFS" in p4_text
        assert "Dijkstra" in p4_text
        assert "Bellman-Ford" in p4_text
        assert "Floyd-Warshall" in p4_text

    def test_word_and_character_counts_accurate(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies that character and word counts match normalized text lengths."""
        result = analyzer.analyze(sample_practical_pdf)

        calc_total_chars = 0
        calc_total_words = 0
        for p in result.pages:
            assert p.character_count == len(p.text)
            assert p.word_count == len(p.text.split())
            calc_total_chars += p.character_count
            calc_total_words += p.word_count

        assert result.summary.total_characters == calc_total_chars
        assert result.summary.total_words == calc_total_words
        expected_avg = round(calc_total_chars / 5, 2)
        assert result.summary.average_characters_per_page == expected_avg

    def test_empty_and_image_only_pages_handled_correctly(
        self, analyzer: PDFAnalyzer, sample_empty_and_image_pdf: Path
    ) -> None:
        """Verifies distinction between pages with selectable text, image-only, and blank pages."""
        result = analyzer.analyze(sample_empty_and_image_pdf)

        assert result.summary.total_pages == 3
        assert result.summary.pages_with_text == 1
        assert result.summary.empty_pages == 2

        # Page 1: Selectable text
        p1 = result.pages[0]
        assert p1.has_text is True
        assert p1.has_images is False
        assert "DocMorph Test Document" in p1.text

        # Page 2: Image-only (no selectable text)
        p2 = result.pages[1]
        assert p2.has_text is False
        assert p2.has_images is True
        assert p2.text == ""
        assert p2.word_count == 0
        assert p2.character_count == 0

        # Page 3: Blank page (no text, no image)
        p3 = result.pages[2]
        assert p3.has_text is False
        assert p3.has_images is False
        assert p3.text == ""

    def test_whitespace_normalization_preserves_paragraphs(self) -> None:
        """Verifies that excessive spaces and newlines are normalized without loss of paragraphs."""
        raw = "Line 1   with   excessive   spaces.   \n\n\n\n\nLine 2 after huge gap.\n\nLine 3."
        normalized = PDFAnalyzer.normalize_text(raw)

        expected = "Line 1 with excessive spaces.\n\nLine 2 after huge gap.\n\nLine 3."
        assert normalized == expected


# ==============================================================================
# SECTION D: RELIABILITY AND SECURITY TESTS
# ==============================================================================

class TestReliabilityAndSecurity:
    """Test suite for document lifecycle, non-destructive processing, and security."""

    def test_original_pdf_remains_unchanged(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies that analysis is strictly read-only and leaves the source file byte-identical."""
        hash_before = compute_file_sha256(sample_practical_pdf)

        # Run extraction
        analyzer.analyze(sample_practical_pdf)

        hash_after = compute_file_sha256(sample_practical_pdf)
        assert hash_before == hash_after, "Original PDF was modified during analysis!"

    def test_file_handle_is_closed_after_analysis(
        self, analyzer: PDFAnalyzer, sample_practical_pdf: Path
    ) -> None:
        """Verifies that PyMuPDF closes the file handle and does not lock the file on Windows."""
        analyzer.analyze(sample_practical_pdf)

        # On Windows, if a file handle remains open, attempting to open for writing will fail
        with open(sample_practical_pdf, "rb+") as f:
            first_byte = f.read(1)
            f.seek(0)
            f.write(first_byte)  # Re-writing same byte proves file lock was released

    def test_safe_error_messages_do_not_leak_internal_paths(
        self, analyzer: PDFAnalyzer, tmp_path: Path
    ) -> None:
        """Verifies that domain exception messages never expose host paths."""
        deep_secret_dir = tmp_path / "secret_server_root" / "internal_storage"
        deep_secret_dir.mkdir(parents=True)
        bad_file = deep_secret_dir / "invalid.pdf"
        bad_file.write_text("Not a pdf at all", encoding="utf-8")

        with pytest.raises(DocMorphError) as exc_info:
            analyzer.analyze(bad_file)

        error_message = exc_info.value.user_message
        assert str(deep_secret_dir) not in error_message
        assert "secret_server_root" not in error_message


# ==============================================================================
# SECTION E: IN-MEMORY BYTES EXTRACTION TESTS
# ==============================================================================

class TestBytesExtraction:
    """Test suite for in-memory byte analysis (FastAPI upload compatibility)."""

    def test_analyze_bytes_success(self, analyzer: PDFAnalyzer, sample_practical_pdf: Path) -> None:
        """Verifies analyze_bytes produces identical results to analyze file."""
        data = sample_practical_pdf.read_bytes()
        result = analyzer.analyze_bytes(data, filename="memory_practical.pdf")

        assert result.filename == "memory_practical.pdf"
        assert result.summary.total_pages == 5
        assert result.metadata.author == "Rahul Patel"

    def test_analyze_bytes_empty(self, analyzer: PDFAnalyzer) -> None:
        """Verifies analyze_bytes rejects empty bytes."""
        with pytest.raises(EmptyFileError):
            analyzer.analyze_bytes(b"", filename="empty.pdf")

    def test_analyze_bytes_invalid_signature(self, analyzer: PDFAnalyzer) -> None:
        """Verifies analyze_bytes rejects non-PDF bytes."""
        with pytest.raises(InvalidFileTypeError):
            analyzer.analyze_bytes(b"some non pdf text data", filename="test.pdf")


# ==============================================================================
# SECTION F: CLI EXECUTION TESTS
# ==============================================================================

class TestCLIExecution:
    """Test suite for CLI entry point execution and exit codes."""

    def test_cli_success(self, sample_practical_pdf: Path) -> None:
        """Verifies that python -m app.main <file> succeeds and outputs formatted text."""
        cmd = [sys.executable, "-m", "app.main", str(sample_practical_pdf)]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 0
        output = proc.stdout
        assert "DOCMORPH" in output
        assert "PDF ANALYSIS ENGINE" in output
        assert f"File: {sample_practical_pdf.name}" in output
        assert "Total Pages: 5" in output
        assert "Pages With Text: 5" in output
        assert "--------------- PAGE 1 ---------------" in output
        assert "Rahul Patel" in output
        assert "PDF analysis completed successfully." in output

    def test_cli_json_flag(self, sample_practical_pdf: Path) -> None:
        """Verifies that python -m app.main <file> --json outputs valid JSON."""
        cmd = [sys.executable, "-m", "app.main", str(sample_practical_pdf), "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 0
        import json
        data = json.loads(proc.stdout)
        assert data["filename"] == sample_practical_pdf.name
        assert data["summary"]["total_pages"] == 5

    def test_cli_error_exit_code(self, non_pdf_file: Path) -> None:
        """Verifies that CLI returns exit code 1 on validation error and prints error block."""
        cmd = [sys.executable, "-m", "app.main", str(non_pdf_file)]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 1
        output = proc.stdout
        assert "DOCMORPH ERROR" in output
        assert "Error: Unsupported file extension" in output

