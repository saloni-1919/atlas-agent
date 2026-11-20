"""Local Ollama provider + semantic search tests: deterministic, no external service needed."""
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB", tmp_path / "test.sqlite")
    for key in ["ATLAS_AI_PROVIDER", "ATLAS_RETRIEVAL", "ATLAS_EMBED_MODEL", "ATLAS_MIN_SIMILARITY", "OPENAI_API_KEY", "ATLAS_OLLAMA_URL"]:
        monkeypatch.delenv(key, raising=False)
    main.init_db()


def fake_local(path, payload):
    if path == "/api/chat":
        return {"message": {"content": "Employees can work remotely three days per week [1]."}}
    assert path == "/api/embed"
    vectors = []
    for text in payload["input"]:
        t = text.lower()
        if "remote" in t or "telecommute" in t or "staff" in t:
            vectors.append([1.0, 0.0, 0.0])
        elif "refund" in t:
            vectors.append([0.0, 1.0, 0.0])
        elif "bonus" in t:
            vectors.append([0.0, 0.0, 1.0])
        else:
            vectors.append([0.0, 0.5, 0.5])
    return {"embeddings": vectors}


def test_semantic_paraphrase_caches_vectors_and_deletion(monkeypatch):
    monkeypatch.setenv("ATLAS_RETRIEVAL", "ollama")
    calls = []
    def service(path, payload):
        calls.append((path, payload))
        return fake_local(path, payload)
    monkeypatch.setattr(main, "local_request", service)
    item = client.post("/documents", json={"title": "Employee policy", "content": "Remote work is permitted three days per week."}).json()
    client.post("/documents", json={"title": "Refunds", "content": "Refunds are handled in five business days."})
    first = client.post("/ask", json={"question": "How frequently may staff telecommute?"}).json()
    assert first["mode"] == "extractive"
    assert len(first["sources"]) == 1
    assert first["sources"][0]["document_id"] == item["id"]
    assert "Remote work" in first["sources"][0]["text"]
    index_calls = [call for call in calls if call[0] == "/api/embed" and len(call[1]["input"]) > 1]
    assert len(index_calls) == 1  # batch 2 documents
    client.post("/ask", json={"question": "Can staff telecommute?"})
    assert len([call for call in calls if call[0] == "/api/embed" and len(call[1]["input"]) > 1]) == 1
    with main.db() as database:
        assert database.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0] == 2
    assert client.delete(f"/documents/{item['id']}").status_code == 200
    with main.db() as database:
        assert database.execute("SELECT COUNT(*) FROM chunk_embeddings WHERE document_id=?", (item["id"],)).fetchone()[0] == 0
    after = client.post("/ask", json={"question": "How frequently may staff telecommute?"}).json()
    assert after["mode"] == "abstain"


def test_semantic_bonus_abstains_even_with_high_similarity(monkeypatch):
    monkeypatch.setenv("ATLAS_RETRIEVAL", "ollama")
    monkeypatch.setattr(main, "local_request", lambda path, payload: {"embeddings": [[1.0, 0.0] for _ in payload["input"]]})
    client.post("/documents", json={"title": "Employee policy", "content": "Employees receive 20 days of annual leave."})
    result = client.post("/ask", json={"question": "What is the annual employee bonus percentage?"}).json()
    assert result["mode"] == "abstain"
    assert result["sources"] == []


def test_semantic_percentage_accepts_12_percent(monkeypatch):
    monkeypatch.setenv("ATLAS_RETRIEVAL", "ollama")
    monkeypatch.setattr(main, "local_request", lambda path, payload: {"embeddings": [[1.0, 0.0] for _ in payload["input"]]})
    client.post("/documents", json={"title": "Bonus plan", "content": "The annual employee bonus is 12% of salary."})
    result = client.post("/ask", json={"question": "What is the annual employee bonus percentage?"}).json()
    assert result["mode"] == "extractive"
    assert "12%" in result["sources"][0]["text"]


def test_local_ollama_chat_answer_and_status(monkeypatch):
    monkeypatch.setenv("ATLAS_AI_PROVIDER", "ollama")
    monkeypatch.setattr(main, "local_request", fake_local)
    health = client.get("/health").json()
    assert health["provider"] == "ollama"
    assert health["retrieval"] == "lexical"
    client.post("/documents", json={"title": "Employee policy", "content": "Remote work is permitted three days per week."})
    result = client.post("/ask", json={"question": "How many days can employees work remotely per week?"}).json()
    assert result["mode"] == "model"
    assert "three days" in result["answer"]
    assert result["sources"]


def test_ollama_connection_failure_explained(monkeypatch):
    def refused(*args, **kwargs):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(main.urllib.request, "urlopen", refused)
    monkeypatch.setenv("ATLAS_AI_PROVIDER", "ollama")
    client.post("/documents", json={"title": "Employee remote work policy", "content": "Employees may work remotely three days per week."})
    result = client.post("/ask", json={"question": "How many days can employees work remotely per week?"})
    assert result.status_code == 503
    assert "Ollama" in result.json()["detail"]


def test_invalid_external_ollama_host_refused(monkeypatch):
    monkeypatch.setenv("ATLAS_OLLAMA_URL", "https://example.com")
    with pytest.raises(HTTPException) as exc:
        main.ollama_url("/api/chat")
    assert exc.value.status_code == 500


def test_invalid_similarity_config_explained(monkeypatch):
    monkeypatch.setenv("ATLAS_RETRIEVAL", "ollama")
    monkeypatch.setenv("ATLAS_MIN_SIMILARITY", "not-a-number")
    monkeypatch.setattr(main, "local_request", fake_local)
    client.post("/documents", json={"title": "Employee policy", "content": "Remote work is permitted three days per week."})
    result = client.post("/ask", json={"question": "Remote work policy?"})
    assert result.status_code == 500
    assert "ATLAS_MIN_SIMILARITY" in result.json()["detail"]
