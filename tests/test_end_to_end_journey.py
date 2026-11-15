"""End-to-end integration test simulating the complete user journey in DocMorph."""

import io
import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.models.base import Base
from app.server import create_app
from tests.create_sample import create_sample_practical_pdf


@pytest.fixture
def clean_client():
    """Provides a fresh database and client for end-to-end test run."""
    from app.db.session import engine

    Base.metadata.drop_all(bind=engine)
    init_db()

    app = create_app()
    with TestClient(app) as client:
        yield client


class TestCompleteUserJourney:
    """Simulates an entire student workflow from registration through download."""

    def test_full_personalization_journey_and_isolation(self, clean_client: TestClient, tmp_path):
        # -------------------------------------------------------------
        # STEP 1: Student A registers and logs in
        # -------------------------------------------------------------
        student_a_email = "student.a@university.edu"
        student_a_pass = "SecurePass2026!"

        signup_res = clean_client.post(
            "/api/v1/auth/signup",
            json={
                "email": student_a_email,
                "password": student_a_pass,
                "full_name": "Student A",
            },
        )
        assert signup_res.status_code == 201

        login_res = clean_client.post(
            "/api/v1/auth/login",
            json={"email": student_a_email, "password": student_a_pass},
        )
        assert login_res.status_code == 200
        token_a = login_res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # -------------------------------------------------------------
        # STEP 2: Student A uploads a real multi-page PDF
        # -------------------------------------------------------------
        sample_pdf_path = tmp_path / "journey_lab_manual.pdf"
        create_sample_practical_pdf(sample_pdf_path)
        pdf_bytes = sample_pdf_path.read_bytes()

        upload_res = clean_client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": ("physics_practical.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_res.status_code == 201
        doc_data = upload_res.json()
        doc_id = doc_data["id"]
        assert doc_data["page_count"] == 5
        assert doc_data["original_filename"] == "physics_practical.pdf"

        # -------------------------------------------------------------
        # STEP 3: Student A previews the source PDF
        # -------------------------------------------------------------
        preview_res = clean_client.get(f"/api/v1/documents/{doc_id}/preview", headers=headers_a)
        assert preview_res.status_code == 200
        assert preview_res.headers["Content-Type"] == "application/pdf"
        assert preview_res.content[:5] == b"%PDF-"

        # -------------------------------------------------------------
        # STEP 4: Student A triggers Phase 2 Intelligent Detection
        # -------------------------------------------------------------
        detect_res = clean_client.post(f"/api/v1/documents/{doc_id}/analyze", headers=headers_a)
        assert detect_res.status_code == 200
        detection_data = detect_res.json()
        fields = detection_data["fields"]
        assert len(fields) >= 2  # At least Student Name and Roll Number / Enrollment

        name_field = next(f for f in fields if f["field_type"] == "student_name")
        roll_field = next(f for f in fields if f["field_type"] in ("roll_number", "enrollment_number"))

        # -------------------------------------------------------------
        # STEP 5: Student A confirms Name and corrects Roll Number
        # -------------------------------------------------------------
        # Confirm Name
        conf_res = clean_client.post(
            f"/api/v1/documents/{doc_id}/detections/{name_field['field_id']}/confirm",
            headers=headers_a,
        )
        assert conf_res.status_code == 200
        assert conf_res.json()["review_status"] == "confirmed"

        # Correct Roll Number
        corr_res = clean_client.patch(
            f"/api/v1/documents/{doc_id}/detections/{roll_field['field_id']}",
            headers=headers_a,
            json={
                "review_status": "corrected",
                "corrected_value": "CS-2024-9999",
                "field_type": roll_field["field_type"],
            },
        )
        assert corr_res.status_code == 200
        assert corr_res.json()["review_status"] == "corrected"
        assert corr_res.json()["corrected_value"] == "CS-2024-9999"

        # -------------------------------------------------------------
        # STEP 6: Student B registers and attempts unauthorized access
        # -------------------------------------------------------------
        student_b_email = "student.b@university.edu"
        clean_client.post(
            "/api/v1/auth/signup",
            json={"email": student_b_email, "password": "PasswordB2026!", "full_name": "Student B"},
        )
        login_b = clean_client.post(
            "/api/v1/auth/login",
            json={"email": student_b_email, "password": "PasswordB2026!"},
        )
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Student B cannot get Student A's document, detections, or preview
        assert clean_client.get(f"/api/v1/documents/{doc_id}", headers=headers_b).status_code == 404
        assert clean_client.get(f"/api/v1/documents/{doc_id}/detection", headers=headers_b).status_code == 404
        assert clean_client.get(f"/api/v1/documents/{doc_id}/preview", headers=headers_b).status_code == 404
        assert (
            clean_client.post(
                f"/api/v1/documents/{doc_id}/personalize",
                headers=headers_b,
                json={"replacements": [{"field_id": name_field["field_id"], "field_type": "student_name", "new_value": "Hacker"}]},
            ).status_code
            == 404
        )

        # -------------------------------------------------------------
        # STEP 7: Student A executes Personalization
        # -------------------------------------------------------------
        personalize_res = clean_client.post(
            f"/api/v1/documents/{doc_id}/personalize",
            headers=headers_a,
            json={
                "replacements": [
                    {
                        "field_id": name_field["field_id"],
                        "field_type": "student_name",
                        "new_value": "Smit Patel",
                    },
                    {
                        "field_id": roll_field["field_id"],
                        "field_type": roll_field["field_type"],
                        "new_value": "EC-2026-0042",
                    },
                ]
            },
        )
        assert personalize_res.status_code == 200
        job_data = personalize_res.json()
        assert job_data["status"] == "completed"
        assert job_data["verification_status"] == "passed"
        assert job_data["download_available"] is True

        # Check verification report details
        v_report = job_data["verification_report"]
        assert v_report["is_valid"] is True
        assert v_report["page_count_matches"] is True
        assert v_report["labels_intact"] is True

        # -------------------------------------------------------------
        # STEP 8: Student A previews and downloads personalized PDF
        # -------------------------------------------------------------
        p_preview = clean_client.get(f"/api/v1/documents/{doc_id}/personalized-preview", headers=headers_a)
        assert p_preview.status_code == 200
        assert p_preview.headers["Content-Type"] == "application/pdf"
        assert p_preview.content[:5] == b"%PDF-"

        download_res = clean_client.get(f"/api/v1/documents/{doc_id}/download", headers=headers_a)
        assert download_res.status_code == 200
        assert "attachment" in download_res.headers["Content-Disposition"]
        assert download_res.content[:5] == b"%PDF-"

        # Student B cannot download Student A's output
        assert clean_client.get(f"/api/v1/documents/{doc_id}/download", headers=headers_b).status_code == 404

        # -------------------------------------------------------------
        # STEP 9: Student A deletes the document
        # -------------------------------------------------------------
        delete_res = clean_client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert delete_res.status_code == 204

        # Verify document is gone
        assert clean_client.get(f"/api/v1/documents/{doc_id}", headers=headers_a).status_code == 404
