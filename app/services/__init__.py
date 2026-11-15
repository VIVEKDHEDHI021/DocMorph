"""Services module for DocMorph."""

from app.services.confidence_scorer import ConfidenceScorer
from app.services.detection_engine import DetectionEngine
from app.services.detection_service import DetectionAppService
from app.services.document_service import DocumentAppService
from app.services.field_detector import FieldDetector
from app.services.field_grouper import FieldGrouper
from app.services.footer_detector import FooterDetector
from app.services.formatting_analyzer import FormattingAnalyzer
from app.services.output_verifier import OutputVerifier
from app.services.pdf_analyzer import PDFAnalyzer
from app.services.pdf_replacer import PDFReplacer
from app.services.personalization_service import PersonalizationAppService
from app.services.replacement_validator import ReplacementValidator
from app.services.text_segmenter import TextSegmenter
from app.services.value_extractor import ValueExtractor

__all__ = [
    # Phase 1 Services
    "PDFAnalyzer",
    # Phase 2 Services
    "ConfidenceScorer",
    "DetectionEngine",
    "FieldDetector",
    "FieldGrouper",
    "FooterDetector",
    "TextSegmenter",
    "ValueExtractor",
    # Phase 3 Services
    "FormattingAnalyzer",
    "OutputVerifier",
    "PDFReplacer",
    "ReplacementValidator",
    # Phase 4 Application Orchestrators
    "DocumentAppService",
    "DetectionAppService",
    "PersonalizationAppService",
]
