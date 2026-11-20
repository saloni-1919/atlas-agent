"""API contract, offline retrieval, file upload and approval-gate tests."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB", tmp_path / "test.sqlite")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    main.init_db()


def make_pdf_with_text(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
    })
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_dashboard_assets_and_health():
    assert client.get("/").status_code == 200
    assert "ATLAS AGENT" in client.get("/").text
    assert client.get("/assets/style.css").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/health").json()["mode"] == "offline-extractive"


def test_add_read_ask_delete_document():
    payload = {"title": "Refund policy", "content": "Refunds are processed within five business days. Customers can request refunds online."}
    response = client.post("/documents", json=payload)
    assert response.status_code == 201
    doc_id = response.json()["id"]
    assert client.get(f"/documents/{doc_id}").json()["content"] == payload["content"]
    assert client.get("/documents").json()[0]["characters"] == len(payload["content"])
    answer = client.post("/ask", json={"question": "When are refunds processed?"}).json()
    assert answer["mode"] == "extractive"
    assert any("five business days" in source["text"] for source in answer["sources"])
    assert client.delete(f"/documents/{doc_id}").json() == {"deleted": True}
    assert client.get(f"/documents/{doc_id}").status_code == 404
    assert client.delete(f"/documents/{doc_id}").status_code == 404


def test_abstains_without_matching_evidence():
    client.post("/documents", json={"title": "Policy", "content": "We offer refunds in five business days."})
    answer = client.post("/ask", json={"question": "quantum astrophysics quasar"}).json()
    assert answer["mode"] == "abstain"
    assert answer["sources"] == []


def test_irrelevant_shared_time_words_are_not_evidence():
    client.post("/documents/sample")
    result = client.post("/ask", json={"question": "How many days can employees work remotely per week?"}).json()
    assert result["mode"] == "abstain"
    assert result["sources"] == []


def test_remote_work_policy_retrieves_relevant_document():
    client.post("/documents/sample")
    client.post("/documents", json={
        "title": "Company Employee Policy",
        "content": "Employees receive 20 days of paid annual leave. Remote work is permitted three days per week."
    })
    result = client.post("/ask", json={"question": "How many days can employees work remotely per week?"}).json()
    assert result["mode"] == "extractive"
    assert result["sources"]
    assert result["sources"][0]["title"] == "Company Employee Policy"
    assert "Remote work is permitted three days per week" in result["sources"][0]["text"]


def test_upload_text_and_pdf():
    text = client.post("/documents/upload", files={"file": ("notes.md", b"Annual leave may be requested online.", "text/markdown")})
    assert text.status_code == 201
    assert text.json()["kind"] == "md"
    pdf = client.post("/documents/upload", files={"file": ("leave.pdf", make_pdf_with_text("Requests must be approved by managers."), "application/pdf")})
    assert pdf.status_code == 201, pdf.text
    assert pdf.json()["kind"] == "pdf"
    stored = client.get(f"/documents/{pdf.json()['id']}").json()
    assert "approved by managers" in stored["content"]


def test_upload_rejects_unsupported_scanned_and_large():
    bad_file = client.post("/documents/upload", files={"file": ("evil.exe", b"X", "application/octet-stream")})
    assert bad_file.status_code == 415
    large = client.post("/documents/upload", files={"file": ("large.txt", b"x" * 3_000_001, "text/plain")})
    assert large.status_code == 413
    blank_pdf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=400)
    writer.write(blank_pdf)
    scanned = client.post("/documents/upload", files={"file": ("blank.pdf", blank_pdf.getvalue(), "application/pdf")})
    assert scanned.status_code == 422
    assert "selectable text" in scanned.json()["detail"]


def test_sample_is_idempotent():
    first = client.post("/documents/sample").json()
    second = client.post("/documents/sample").json()
    assert first["id"] == second["id"]
    assert client.get("/overview").json()["documents"] == 1


def test_document_validation():
    assert client.post("/documents", json={"title": " ", "content": "text"}).status_code == 422
    assert client.post("/documents", json={"title": "valid", "content": "x" * 40_001}).status_code == 422
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_approval_executes_only_after_approval():
    proposal = client.post("/actions/calculation", json={"expression": "(12+8)*2"})
    assert proposal.status_code == 201
    action_id = proposal.json()["id"]
    assert client.get("/actions").json()[0]["result"] is None
    result = client.post(f"/actions/{action_id}/approve")
    assert result.json()["result"] == 40
    assert client.post(f"/actions/{action_id}/approve").status_code == 409
    assert client.get("/actions").json()[0]["decided_at"] is not None
    assert client.get("/overview").json()["actions"]["approved"] == 1


def test_reject_prevents_execution():
    action_id = client.post("/actions/calculation", json={"expression": "8 * 11"}).json()["id"]
    rejected = client.post(f"/actions/{action_id}/reject")
    assert rejected.json()["result"] is None
    assert client.post(f"/actions/{action_id}/approve").status_code == 409
    assert client.get("/actions").json()[0]["status"] == "rejected"


@pytest.mark.parametrize("expression", ["__import__('os').system('echo unsafe')", "2 ** 100", "1 / 0", "2 // 2", "99999999999999", "(1+2) * 'oops'"])
def test_calculator_is_safely_restricted(expression):
    with pytest.raises(ValueError):
        main.calculate(expression)
    assert client.post("/actions/calculation", json={"expression": expression}).status_code == 422


def test_only_valid_actions_and_missing_ids():
    assert main.calculate("-5 + (3 * 2)") == 1
    assert client.post("/actions/nonexistent/approve").status_code == 404
    assert client.post("/actions/nonexistent/reject").status_code == 404


def test_bonus_percentage_absent_returns_no_evidence():
    client.post("/documents/sample")
    client.post("/documents", json={
        "title": "Company Employee Policy",
        "content": "Employees receive 20 days of paid annual leave. Remote work is permitted three days per week."
    })
    result = client.post("/ask", json={"question": "What is the annual employee bonus percentage?"}).json()
    assert result["mode"] == "abstain"
    assert result["sources"] == []


def test_bonus_percentage_with_actual_evidence_retrieves():
    client.post("/documents", json={
        "title": "Company Employee Policy",
        "content": "Employees receive an annual bonus of 12% of their base salary."
    })
    result = client.post("/ask", json={"question": "What is the annual employee bonus percentage?"}).json()
    assert result["mode"] == "extractive"
    assert len(result["sources"]) == 1
    assert "12%" in result["sources"][0]["text"]


def test_percentage_question_does_not_accept_days_as_evidence():
    client.post("/documents", json={
        "title": "Company Employee Policy",
        "content": "Remote work is permitted three days per week."
    })
    result = client.post("/ask", json={"question": "What percentage of employees work remotely?"}).json()
    assert result["mode"] == "abstain"
    assert result["sources"] == []
