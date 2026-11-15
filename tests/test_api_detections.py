"""Automated test suite for detection and manual review endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient


class TestDetectionAPI:
    """Tests Phase 2 detection trigger, field listing, and manual review mutations."""

    def test_trigger_detection_success(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies triggering detection extracts fields and updates document state."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]

        det_res = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers)
        assert det_res.status_code == 200
        data = det_res.json()
        assert data["document_id"] == doc_id
        assert data["status"] == "awaiting_review"
        assert len(data["fields"]) >= 3

        field_types = [f["field_type"] for f in data["fields"]]
        assert "student_name" in field_types
        assert "enrollment_number" in field_types
        assert "roll_number" in field_types

    def test_get_detection_results(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies retrieving previously analyzed detections."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers)

        res = client.get(f"/api/v1/documents/{doc_id}/detection", headers=user_a_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["document_id"] == doc_id
        assert data["summary"]["total_fields"] >= 3

    def test_confirm_field(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies confirming a field updates its status to 'confirmed'."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        target_field = det_data["fields"][0]

        res = client.post(
            f"/api/v1/documents/{doc_id}/detections/{target_field['field_id']}/confirm",
            headers=user_a_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["field_id"] == target_field["field_id"]
        assert data["review_status"] == "confirmed"

    def test_correct_field_value(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies correcting a field preserves original_value while updating suggested_value."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        name_field = next(f for f in det_data["fields"] if f["field_type"] == "student_name")

        res = client.patch(
            f"/api/v1/documents/{doc_id}/detections/{name_field['field_id']}",
            json={
                "review_status": "corrected",
                "corrected_value": "Vivek Dhedhi",
            },
            headers=user_a_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["original_value"] == name_field["original_value"]  # Untouched
        assert data["suggested_value"] == "Vivek Dhedhi"
        assert data["corrected_value"] == "Vivek Dhedhi"
        assert data["review_status"] == "corrected"

    def test_reject_field(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies rejecting a field updates review_status to 'rejected'."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        target_field = det_data["fields"][0]

        res = client.post(
            f"/api/v1/documents/{doc_id}/detections/{target_field['field_id']}/reject",
            headers=user_a_headers,
        )
        assert res.status_code == 200
        assert res.json()["review_status"] == "rejected"

    def test_detection_ownership_enforcement(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
        user_b_headers: dict[str, str],
    ) -> None:
        """SECURITY: Verifies User B cannot analyze, query, or mutate User A's detections."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers)

        # User B attempts to trigger analysis
        res_ana = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_b_headers)
        assert res_ana.status_code == 404

        # User B attempts to read detections
        res_get = client.get(f"/api/v1/documents/{doc_id}/detection", headers=user_b_headers)
        assert res_get.status_code == 404

        # User B attempts to confirm a field
        res_conf = client.post(
            f"/api/v1/documents/{doc_id}/detections/student_name_1/confirm",
            headers=user_b_headers,
        )
        assert res_conf.status_code == 404

