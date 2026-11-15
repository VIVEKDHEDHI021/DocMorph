"""Automated test suite for document upload, preview, and lifecycle management."""

from pathlib import Path
from fastapi.testclient import TestClient


class TestDocumentAPI:
    """Tests document upload, listing, preview, and ownership security."""

    def test_upload_valid_pdf(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies uploading a valid PDF returns 201 with document metadata."""
        with open(sample_practical_pdf, "rb") as f:
            res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert data["original_filename"] == sample_practical_pdf.name
        assert data["page_count"] == 5
        assert data["status"] == "uploaded"

    def test_upload_corrupted_pdf_rejected(
        self,
        client: TestClient,
        corrupted_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies uploading a corrupted PDF is rejected with 400 Bad Request."""
        with open(corrupted_pdf, "rb") as f:
            res = client.post(
                "/api/v1/documents/upload",
                files={"file": (corrupted_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        assert res.status_code == 400
        assert "corrupted" in res.json()["detail"].lower() or "damaged" in res.json()["detail"].lower()

    def test_upload_invalid_extension_rejected(
        self,
        client: TestClient,
        non_pdf_file: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies uploading a non-PDF file is rejected with 400 Bad Request."""
        with open(non_pdf_file, "rb") as f:
            res = client.post(
                "/api/v1/documents/upload",
                files={"file": (non_pdf_file.name, f, "text/plain")},
                headers=user_a_headers,
            )
        assert res.status_code == 400
        assert "unsupported file extension" in res.json()["detail"].lower()

    def test_list_documents(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies listing documents returns paginated user records."""
        with open(sample_practical_pdf, "rb") as f:
            client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )

        res = client.get("/api/v1/documents", headers=user_a_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] >= 1
        assert any(item["original_filename"] == sample_practical_pdf.name for item in data["items"])

    def test_get_document_detail(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies fetching document detail by id."""
        with open(sample_practical_pdf, "rb") as f:
            upload_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = upload_res.json()["id"]

        res = client.get(f"/api/v1/documents/{doc_id}", headers=user_a_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == doc_id
        assert data["page_count"] == 5

    def test_document_preview_stream(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies preview endpoint streams raw PDF content with application/pdf header."""
        with open(sample_practical_pdf, "rb") as f:
            upload_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = upload_res.json()["id"]

        res = client.get(f"/api/v1/documents/{doc_id}/preview", headers=user_a_headers)
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF")

    def test_document_ownership_enforcement(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
        user_b_headers: dict[str, str],
    ) -> None:
        """SECURITY: Verifies User B cannot access, preview, or delete User A's document."""
        with open(sample_practical_pdf, "rb") as f:
            upload_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = upload_res.json()["id"]

        # User B attempts to access User A's document
        res_get = client.get(f"/api/v1/documents/{doc_id}", headers=user_b_headers)
        assert res_get.status_code == 404

        # User B attempts to preview User A's document
        res_prev = client.get(f"/api/v1/documents/{doc_id}/preview", headers=user_b_headers)
        assert res_prev.status_code == 404

        # User B attempts to delete User A's document
        res_del = client.delete(f"/api/v1/documents/{doc_id}", headers=user_b_headers)
        assert res_del.status_code == 404

    def test_delete_document(
        self,
        client: TestClient,
        sample_practical_pdf: Path,
        user_a_headers: dict[str, str],
    ) -> None:
        """Verifies deleting a document removes it from user listings."""
        with open(sample_practical_pdf, "rb") as f:
            upload_res = client.post(
                "/api/v1/documents/upload",
                files={"file": (sample_practical_pdf.name, f, "application/pdf")},
                headers=user_a_headers,
            )
        doc_id = upload_res.json()["id"]

        del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=user_a_headers)
        assert del_res.status_code == 204

        get_res = client.get(f"/api/v1/documents/{doc_id}", headers=user_a_headers)
        assert get_res.status_code == 404

