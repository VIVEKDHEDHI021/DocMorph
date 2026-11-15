"""Pydantic v2 data models for DocMorph PDF extraction and analysis results.

Provides strict type validation, immutability, and schema serialization.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PDFMetadata(BaseModel):
    """Metadata extracted from the PDF document."""

    model_config = ConfigDict(frozen=True)

    filename: str = Field(description="Sanitized name of the PDF file")
    title: Optional[str] = Field(default=None, description="Document title if present")
    author: Optional[str] = Field(default=None, description="Document author if present")
    subject: Optional[str] = Field(default=None, description="Document subject if present")
    creator: Optional[str] = Field(default=None, description="Application that created the document")
    producer: Optional[str] = Field(default=None, description="Producer tool that generated the PDF")
    creation_date: Optional[str] = Field(default=None, description="Creation timestamp")
    modification_date: Optional[str] = Field(default=None, description="Last modification timestamp")
    page_count: int = Field(ge=0, description="Total number of pages in the document")
    pdf_version: Optional[str] = Field(default=None, description="PDF format/specification version")
    file_size_bytes: Optional[int] = Field(default=None, ge=0, description="File size in bytes")
    is_encrypted: bool = Field(default=False, description="Whether the document is encrypted")


class ExtractedPage(BaseModel):
    """Structured text and content statistics for an individual PDF page."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1, description="1-indexed page number")
    text: str = Field(description="Normalized selectable text extracted from the page")
    character_count: int = Field(ge=0, description="Total number of characters in extracted text")
    word_count: int = Field(ge=0, description="Total number of words in extracted text")
    has_text: bool = Field(description="True if the page contains selectable text")
    has_images: bool = Field(default=False, description="True if the page contains embedded images")


class ExtractionSummary(BaseModel):
    """Aggregate statistics and performance metrics for the PDF extraction."""

    model_config = ConfigDict(frozen=True)

    total_pages: int = Field(ge=0, description="Total number of pages processed")
    pages_with_text: int = Field(ge=0, description="Number of pages containing selectable text")
    empty_pages: int = Field(ge=0, description="Number of pages without selectable text")
    total_characters: int = Field(ge=0, description="Total characters extracted across all pages")
    total_words: int = Field(ge=0, description="Total words extracted across all pages")
    average_characters_per_page: float = Field(
        ge=0.0, description="Average number of characters per page"
    )
    status: str = Field(default="success", description="Status indicator of the extraction process")
    processing_duration_seconds: float = Field(
        ge=0.0, description="Total processing time in seconds"
    )
    processing_duration_formatted: str = Field(
        description="Human-readable processing duration string"
    )


class PDFAnalysisResult(BaseModel):
    """Complete structured response representing the analysis of a PDF file."""

    model_config = ConfigDict(frozen=True)

    filename: str = Field(description="Name of the analyzed PDF file")
    metadata: PDFMetadata = Field(description="Extracted document metadata")
    summary: ExtractionSummary = Field(description="Document statistics and extraction summary")
    pages: list[ExtractedPage] = Field(description="List of extracted page data in reading order")

