"""Replacement Validation Service for DocMorph.

Validates replacement requests against document detection results, ensuring
only confirmed fields are personalized and guarding against collisions, malformed
coordinates, and invalid payloads.
"""

from typing import Optional

from app.core.config import Settings, settings
from app.core.exceptions import (
    FieldNotFoundError,
    InvalidBoundingBoxError,
    InvalidReplacementRequestError,
    UnconfirmedFieldError,
)
from app.schemas.detection_data import DetectionResult, ReviewStatus
from app.schemas.replacement_data import ReplacementItem, ReplacementRequest


class ReplacementValidator:
    """Validates replacement request specifications before executing document mutations."""

    def __init__(self, config: Settings = settings) -> None:
        """Initialize with configuration thresholds.

        Args:
            config: Application configuration instance.
        """
        self.config = config
        self.max_text_length = config.MAX_REPLACEMENT_TEXT_LENGTH

    def validate_request(
        self,
        request: ReplacementRequest,
        detection_result: DetectionResult,
    ) -> None:
        """Validates a complete ReplacementRequest against trusted DetectionResult.

        Args:
            request: The client replacement request.
            detection_result: Trusted Phase 2 detection result.

        Raises:
            InvalidReplacementRequestError: If payload parameters or IDs are invalid.
            FieldNotFoundError: If a requested field_id does not exist in the document.
            UnconfirmedFieldError: If target field is unconfirmed or rejected.
            InvalidBoundingBoxError: If occurrence coordinates are invalid.
        """
        if not request.replacements:
            raise InvalidReplacementRequestError("Replacement request contains no replacement items.")

        # Verify document_id match if provided
        if request.document_id and detection_result.document_id:
            if request.document_id != detection_result.document_id:
                raise InvalidReplacementRequestError(
                    f"Document ID mismatch: request target '{request.document_id}' does not "
                    f"match analyzed document '{detection_result.document_id}'."
                )

        seen_field_ids: set[str] = set()

        for item in request.replacements:
            # Check for duplicate requests targeting the same field
            if item.field_id in seen_field_ids:
                raise InvalidReplacementRequestError(
                    f"Duplicate replacement item for field_id '{item.field_id}'."
                )
            seen_field_ids.add(item.field_id)

            # Locate field in detection results
            detected_field = detection_result.get_field(item.field_id)
            if not detected_field:
                raise FieldNotFoundError(
                    f"Field ID '{item.field_id}' was not found in document detection results."
                )

            # Enforce manual review confirmation requirement
            # A field can be confirmed either in DetectionResult or specified in item.review_status
            effective_status = detected_field.status
            if item.review_status in (ReviewStatus.CONFIRMED, ReviewStatus.CORRECTED):
                effective_status = item.review_status

            if effective_status == ReviewStatus.REJECTED:
                raise UnconfirmedFieldError(
                    f"Cannot personalize rejected field '{item.field_id}' ({item.field_type.value})."
                )

            if effective_status == ReviewStatus.PENDING:
                raise UnconfirmedFieldError(
                    f"Cannot personalize unconfirmed field '{item.field_id}' ({item.field_type.value}). "
                    f"Only confirmed or manually corrected fields may be personalized."
                )

            # Validate replacement value
            self.validate_replacement_value(item.new_value, field_id=item.field_id)

            # Validate occurrence coordinates
            if not detected_field.occurrences:
                raise InvalidReplacementRequestError(
                    f"Field '{item.field_id}' has no recorded physical occurrences."
                )

            for occ in detected_field.occurrences:
                bbox = occ.value_bbox or occ.bbox
                if bbox.is_empty or bbox.width <= 0 or bbox.height <= 0:
                    raise InvalidBoundingBoxError(
                        f"Field '{item.field_id}' has invalid bounding box coordinates "
                        f"on page {occ.page_number} ({bbox.to_tuple()})."
                    )

    def validate_replacement_value(self, new_value: str, field_id: str = "field") -> None:
        """Validates the text value proposed for replacement.

        Args:
            new_value: Proposed replacement string.
            field_id: Field identifier for contextual error messages.

        Raises:
            InvalidReplacementRequestError: If text is empty, whitespace-only, or too long.
        """
        if not new_value or not new_value.strip():
            raise InvalidReplacementRequestError(
                f"Replacement value for '{field_id}' cannot be empty or blank."
            )

        if len(new_value) > self.max_text_length:
            raise InvalidReplacementRequestError(
                f"Replacement value for '{field_id}' ({len(new_value)} chars) exceeds "
                f"maximum allowed limit of {self.max_text_length} characters."
            )

