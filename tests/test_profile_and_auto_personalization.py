"""Tests for anonymous sessions, student profile matching, and auto-personalization."""

import pytest
from fastapi.testclient import TestClient

from app.schemas.api_schemas import PersonalizeFieldItem
from app.schemas.detection_data import (
    ConfidenceLevel,
    DetectedField,
    DetectionResult,
    DetectionSummary,
    FieldConflict,
    FieldType,
    ReviewStatus,
)
from app.schemas.profile_data import (
    ProfileMatchResult,
    ProfileMatchStatus,
    StudentProfile,
)
from app.services.profile_matcher import ProfileMatcher


def _make_dummy_summary(fields, conflicts):
    return DetectionSummary(
        total_fields_detected=len(fields),
        high_confidence_count=len(fields),
        medium_confidence_count=0,
        low_confidence_count=0,
        review_required_count=len(conflicts),
        conflicts_count=len(conflicts),
        fields_by_type={},
    )


def test_anonymous_session_creation(client: TestClient):
    """Verifies that an account-free anonymous session is created with a valid JWT token."""
    response = client.post("/api/v1/auth/anonymous-session")
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"].startswith("anon_")
    assert data["user"]["email"].endswith("@session.docmorph.local")


def test_profile_matcher_different_values_plans_replacement():
    """Verifies that when detected values differ from the student profile, a replacement plan is created."""
    profile = StudentProfile(
        full_name="Neel Vyas",
        enrollment_number="92400120560",
        roll_number="42",
    )

    detected_fields = [
        DetectedField(
            field_id="field-name-1",
            field_type=FieldType.STUDENT_NAME,
            original_value="Vivek Dhedhi",
            suggested_value="Vivek Dhedhi",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            review_status=ReviewStatus.PENDING,
            occurrences_count=1,
            pages=[1],
        ),
        DetectedField(
            field_id="field-enr-1",
            field_type=FieldType.ENROLLMENT_NUMBER,
            original_value="92400120571",
            suggested_value="92400120571",
            confidence=0.92,
            confidence_level=ConfidenceLevel.HIGH,
            review_status=ReviewStatus.PENDING,
            occurrences_count=1,
            pages=[1],
        ),
    ]

    detection_result = DetectionResult(
        document_id="doc-test-123",
        filename="test.pdf",
        total_pages=1,
        detected_fields=detected_fields,
        conflicts=[],
        detection_summary=_make_dummy_summary(detected_fields, []),
    )

    result = ProfileMatcher.match_profile(detection_result, profile)
    assert result.document_id == "doc-test-123"
    assert result.all_eligible_for_auto is True
    assert result.requires_manual_review is False
    assert len(result.auto_replacement_plan) == 2

    # Verify student_name comparison
    name_comp = result.comparisons["student_name"]
    assert name_comp.status == ProfileMatchStatus.DIFFERENT
    assert name_comp.detected_value == "Vivek Dhedhi"
    assert name_comp.profile_value == "Neel Vyas"
    assert name_comp.auto_action_eligible is True

    # Verify enrollment_number comparison
    enr_comp = result.comparisons["enrollment_number"]
    assert enr_comp.status == ProfileMatchStatus.DIFFERENT
    assert enr_comp.detected_value == "92400120571"
    assert enr_comp.profile_value == "92400120560"
    assert enr_comp.auto_action_eligible is True


def test_profile_matcher_already_matching():
    """Verifies that when detected values already match the profile, no replacement is planned."""
    profile = StudentProfile(
        full_name="Vivek Dhedhi",
        enrollment_number="92400120571",
    )

    detected_fields = [
        DetectedField(
            field_id="field-name-1",
            field_type=FieldType.STUDENT_NAME,
            original_value="Vivek Dhedhi",
            suggested_value="Vivek Dhedhi",
            confidence=0.96,
            confidence_level=ConfidenceLevel.HIGH,
            review_status=ReviewStatus.PENDING,
            occurrences_count=1,
            pages=[1],
        ),
        DetectedField(
            field_id="field-enr-1",
            field_type=FieldType.ENROLLMENT_NUMBER,
            original_value="92400120571",
            suggested_value="92400120571",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            review_status=ReviewStatus.PENDING,
            occurrences_count=1,
            pages=[1],
        ),
    ]

    detection_result = DetectionResult(
        document_id="doc-test-456",
        filename="test.pdf",
        total_pages=1,
        detected_fields=detected_fields,
        conflicts=[],
        detection_summary=_make_dummy_summary(detected_fields, []),
    )

    result = ProfileMatcher.match_profile(detection_result, profile)
    assert len(result.auto_replacement_plan) == 0
    assert result.comparisons["student_name"].status == ProfileMatchStatus.ALREADY_MATCHING
    assert result.comparisons["enrollment_number"].status == ProfileMatchStatus.ALREADY_MATCHING


def test_profile_matcher_with_conflicts_requires_manual_review():
    """Verifies that cross-page conflicts flag requires_manual_review = True and block auto-replacement."""
    profile = StudentProfile(
        full_name="Neel Vyas",
        enrollment_number="92400120560",
    )

    detected_fields = [
        DetectedField(
            field_id="field-name-1",
            field_type=FieldType.STUDENT_NAME,
            original_value="Vivek Dhedhi",
            suggested_value="Vivek Dhedhi",
            confidence=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            review_status=ReviewStatus.PENDING,
            occurrences_count=2,
            pages=[1, 2],
        )
    ]

    conflicts = [
        FieldConflict(
            conflict_id="conflict-1",
            field_type=FieldType.STUDENT_NAME,
            field_ids=["field-name-1"],
            conflicting_values=["Vivek Dhedhi", "Rahul Sharma"],
            pages=[1, 2],
            description="Conflicting student names",
        )
    ]

    detection_result = DetectionResult(
        document_id="doc-test-789",
        filename="test.pdf",
        total_pages=2,
        detected_fields=detected_fields,
        conflicts=conflicts,
        detection_summary=_make_dummy_summary(detected_fields, conflicts),
    )

    result = ProfileMatcher.match_profile(detection_result, profile)
    assert result.has_conflicts is True
    assert result.requires_manual_review is True
    assert result.all_eligible_for_auto is False
    assert result.comparisons["student_name"].status == ProfileMatchStatus.CONFLICTING


def test_api_match_profile_and_auto_personalize(
    client: TestClient,
    sample_practical_pdf: any,
    user_a_headers: dict[str, str],
):
    """Integration test: upload -> analyze -> match-profile -> auto-personalize end-to-end."""
    with open(sample_practical_pdf, "rb") as f:
        res = client.post(
            "/api/v1/documents/upload",
            files={"file": (sample_practical_pdf.name, f, "application/pdf")},
            headers=user_a_headers,
        )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Trigger detection
    res_det = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers)
    assert res_det.status_code == 200

    profile_payload = {
        "full_name": "Neel Vyas",
        "enrollment_number": "92400120560",
        "roll_number": "25",
    }

    # Match profile
    res_match = client.post(
        f"/api/v1/documents/{doc_id}/match-profile",
        json=profile_payload,
        headers=user_a_headers,
    )
    assert res_match.status_code == 200
    match_data = res_match.json()
    assert match_data["document_id"] == doc_id
    assert "comparisons" in match_data

    # Auto personalize
    if match_data["all_eligible_for_auto"] and match_data["auto_replacement_plan"]:
        res_auto = client.post(
            f"/api/v1/documents/{doc_id}/auto-personalize",
            json=profile_payload,
            headers=user_a_headers,
        )
        assert res_auto.status_code == 200
        job_data = res_auto.json()
        assert job_data["status"] == "completed"
        assert job_data["download_available"] is True

