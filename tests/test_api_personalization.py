"""Automated test suite for personalization, job tracking, and download endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient


class TestPersonalizationAPI:
    """Tests Phase 3 personalization execution, job tracking, and secure downloads."""

    def test_personalize_unconfirmed_field_rejected(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """SECURITY: Verifies attempting to personalize an unconfirmed field returns 403 Forbidden."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        name_field = next(f for f in det_data["fields"] if f["field_type"] == "student_name")

        # Field is currently pending (unconfirmed)
        res = client.post(
            f"/api/v1/documents/{doc_id}/personalize",
            json={
                "replacements": [
                    {
                        "field_id": name_field["field_id"],
                        "field_type": "student_name",
                        "new_value": "Vivek Dhedhi",
                    }
                ]
            },
            headers=user_a_headers,
        )
        assert res.status_code == 403
        assert "unconfirmed" in res.json()["detail"].lower()

    def test_personalize_confirmed_fields_success(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies personalizing confirmed fields succeeds and generates verified output."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        name_field = next(f for f in det_data["fields"] if f["field_type"] == "student_name")
        roll_field = next(f for f in det_data["fields"] if f["field_type"] == "roll_number")

        # Confirm fields
        client.post(
            f"/api/v1/documents/{doc_id}/detections/{name_field['field_id']}/confirm",
            headers=user_a_headers,
        )
        client.post(
            f"/api/v1/documents/{doc_id}/detections/{roll_field['field_id']}/confirm",
            headers=user_a_headers,
        )

        res = client.post(
            f"/api/v1/documents/{doc_id}/personalize",
            json={
                "replacements": [
                    {
                        "field_id": name_field["field_id"],
                        "field_type": "student_name",
                        "new_value": "Vivek Dhedhi",
                    },
                    {
                        "field_id": roll_field["field_id"],
                        "field_type": "roll_number",
                        "new_value": "42",
                    },
                ]
            },
            headers=user_a_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["verification_status"] == "passed"
        assert data["total_replacements"] == 2
        assert data["successful_replacements"] == 2
        assert data["download_available"] is True
        assert len(data["occurrence_results"]) == 10

    def test_job_status_retrieval(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies querying job status by job_id returns complete execution metrics."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        name_field = next(f for f in det_data["fields"] if f["field_type"] == "student_name")

        client.post(
            f"/api/v1/documents/{doc_id}/detections/{name_field['field_id']}/confirm",
            headers=user_a_headers,
        )

        p_res = client.post(
            f"/api/v1/documents/{doc_id}/personalize",
            json={
                "replacements": [
                    {
                        "field_id": name_field["field_id"],
                        "field_type": "student_name",
                        "new_value": "Vivek Dhedhi",
                    }
                ]
            },
            headers=user_a_headers,
        )
        job_id = p_res.json()["job_id"]

        job_res = client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
        assert job_res.status_code == 200
        data = job_res.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["verification_report"]["is_valid"] is True

    def test_download_personalized_pdf_success(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies authorized download streams attachment PDF bytes."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        name_field = next(f for f in det_data["fields"] if f["field_type"] == "student_name")

        client.post(
            f"/api/v1/documents/{doc_id}/detections/{name_field['field_id']}/confirm",
            headers=user_a_headers,
        )

        client.post(
            f"/api/v1/documents/{doc_id}/personalize",
            json={
                "replacements": [
                    {
                        "field_id": name_field["field_id"],
                        "field_type": "student_name",
                        "new_value": "Vivek Dhedhi",
                    }
                ]
            },
            headers=user_a_headers,
        )

        dl_res = client.get(f"/api/v1/documents/{doc_id}/download", headers=user_a_headers)
        assert dl_res.status_code == 200
        assert dl_res.headers["content-type"] == "application/pdf"
        assert "attachment" in dl_res.headers["content-disposition"]
        assert dl_res.content.startswith(b"%PDF")

    def test_download_ownership_enforcement(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
        user_b_headers: dict[str, str],
    ) -> None:
        """SECURITY: Verifies User B cannot download or preview User A's personalized document."""
        with open(sample_practical_pdf, "rb") as f:
            up_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = up_res.json()["id"]
        det_data = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=user_a_headers).json()
        name_field = next(f for f in det_data["fields"] if f["field_type"] == "student_name")

        client.post(
            f"/api/v1/documents/{doc_id}/detections/{name_field['field_id']}/confirm",
            headers=user_a_headers,
        )

        client.post(
            f"/api/v1/documents/{doc_id}/personalize",
            json={
                "replacements": [
                    {
                        "field_id": name_field["field_id"],
                        "field_type": "student_name",
                        "new_value": "Vivek Dhedhi",
                    }
                ]
            },
            headers=user_a_headers,
        )

        # User B attempts to download User A's personalized output
        res_dl = client.get(f"/api/v1/documents/{doc_id}/download", headers=user_b_headers)
        assert res_dl.status_code == 404

        # User B attempts to preview User A's personalized output
        res_prev = client.get(
            f"/api/v1/documents/{doc_id}/personalized-preview", headers=user_b_headers
        )
        assert res_prev.status_code == 404

