"""Release-candidate security, tool approval, AI guard and migration tests."""
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from app import main
from scripts.migrate_db import migrate

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB', tmp_path / 'test.sqlite')
    for k in ['OPENAI_API_KEY', 'ATLAS_AI_PROVIDER', 'ATLAS_RETRIEVAL']:
        monkeypatch.delenv(k, raising=False)
    main.init_db()


def test_favicon_security_headers_and_same_origin():
    icon = client.get('/assets/favicon.svg')
    assert icon.status_code == 200
    assert icon.headers['content-type'].startswith('image/svg+xml')
    assert client.get('/').headers['x-frame-options'] == 'DENY'
    assert 'script-src' in client.get('/').headers['content-security-policy']
    block = client.post('/documents', headers={'Origin': 'http://evil.test'}, json={'title': 'Policy', 'content': 'Some content'})
    assert block.status_code == 403
    allow = client.post('/documents', headers={'Origin': 'http://testserver'}, json={'title': 'Policy', 'content': 'Some content'})
    assert allow.status_code == 201


def test_bad_host_is_rejected():
    assert client.get('/health', headers={'Host': 'untrusted.example'}).status_code == 400


def test_custom_pdf_title_and_validation():
    from tests.test_main import make_pdf_with_text
    result = client.post('/documents/upload', data={'title': 'Benefits Handbook'}, files={
        'file': ('original.pdf', make_pdf_with_text('Employees receive three days of remote work.'), 'application/pdf')
    })
    assert result.status_code == 201
    assert result.json()['title'] == 'Benefits Handbook'
    assert client.post('/documents', json={'title': 'Bad\nTitle', 'content': 'ok'}).status_code == 422


def test_ollama_readiness_status(monkeypatch):
    assert client.get('/system/status').json()['ready'] is True
    monkeypatch.setenv('ATLAS_AI_PROVIDER', 'ollama')
    def unreachable(*args, **kwargs):
        raise OSError('Connection refused')
    monkeypatch.setattr(main.urllib.request, 'urlopen', unreachable)
    body = client.get('/system/status').json()
    assert body['ready'] is False and 'Ollama' in body['message']


def test_chat_calculator_plans_requires_human_approval_and_persists():
    cid = client.post('/conversations').json()['id']
    response = client.post(f'/conversations/{cid}/messages', json={'question':'/calc (12 + 8) * 2'})
    assert response.status_code == 201
    data = response.json()
    assert data['mode'] == 'tool-proposed'
    action_id = data['action_id']
    assert client.get('/actions').json()[0]['status'] == 'pending'
    messages = client.get(f'/conversations/{cid}').json()['messages']
    assert messages[-1]['action_id'] == action_id
    assert 'Nothing has been executed' in messages[-1]['content']
    assert client.post(f'/actions/{action_id}/approve').json()['result'] == 40
    assert client.post(f'/actions/{action_id}/reject').status_code == 409


def test_invalid_calculation_does_not_store_messages_or_actions():
    cid = client.post('/conversations').json()['id']
    bad = client.post(f'/conversations/{cid}/messages', json={'question':'/calc __import__("os")'})
    assert bad.status_code == 422
    assert client.get(f'/conversations/{cid}').json()['messages'] == []
    assert client.get('/actions').json() == []


def test_model_numeric_guard_refuses_invented_values(monkeypatch):
    monkeypatch.setenv('ATLAS_AI_PROVIDER', 'ollama')
    client.post('/documents', json={'title': 'Employee policy', 'content': 'Remote work is permitted three days per week.'})
    monkeypatch.setattr(main, 'local_request', lambda *args: {'message': {'content': 'Workers can stay home for 7 days per week [1].'}})
    response = client.post('/ask', json={'question':'How many days can employees work remotely per week?'}).json()
    assert response['mode'] == 'extractive' and response['warning']
    assert 'three days' in response['answer']
    monkeypatch.setattr(main, 'local_request', lambda *args: {'message': {'content': 'Employees can work remotely 3 days per week [1].'}})
    response = client.post('/ask', json={'question':'How many days can employees work remotely per week?'}).json()
    assert response['mode'] == 'model'


def test_model_guard_requires_valid_citations():
    evidence = [{'text': 'Revenue increased 12% in 2025.'}]
    assert not main.supported_model_answer('Revenue increased 12%.', evidence)
    assert not main.supported_model_answer('Revenue increased 12% [2].', evidence)
    assert main.supported_model_answer('Revenue increased 12% [1].', evidence)


def test_legacy_db_migration_preserves_rows_and_previous_backup(tmp_path):
    old = tmp_path / 'old.sqlite'
    with closing(sqlite3.connect(old)) as connection:
        connection.executescript('''
          CREATE TABLE documents (id TEXT PRIMARY KEY,title TEXT,content TEXT,kind TEXT,created_at TEXT);
          CREATE TABLE actions (id TEXT PRIMARY KEY,expression TEXT,status TEXT,result TEXT,created_at TEXT,decided_at TEXT);
          INSERT INTO documents VALUES ('legacy','Work policy','Remote work is three days per week','text','2026-01-01');
        ''')
    target = tmp_path / 'new.sqlite'
    assert migrate(old, target) == target
    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute('SELECT title FROM documents').fetchone()[0] == 'Work policy'
    with pytest.raises(ValueError):
        migrate(old, target)
    assert migrate(old, target, replace=True) == target
    assert list(tmp_path.glob('new.sqlite.backup-*'))
    with closing(sqlite3.connect(old)) as connection:
        assert connection.execute('SELECT COUNT(*) FROM documents').fetchone()[0] == 1
