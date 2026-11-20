"""Conversation persistence and backwards-compatible SQLite migration checks."""
import sqlite3
from fastapi.testclient import TestClient
import pytest
from app import main

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB', tmp_path / 'test.sqlite')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    main.init_db()


def test_local_conversations_persist_and_delete_without_touching_documents():
    doc = client.post('/documents', json={'title':'Company Employee Policy','content':'Remote work is permitted three days per week.'}).json()
    convo = client.post('/conversations').json()
    assert convo['title'] == 'New conversation'
    cid = convo['id']
    answer = client.post(f'/conversations/{cid}/messages', json={
        'question':'How many days can employees work remotely per week?'
    })
    assert answer.status_code == 201
    assert answer.json()['mode'] == 'extractive'
    assert 'three days' in answer.json()['answer']
    history = client.get(f'/conversations/{cid}').json()
    assert len(history['messages']) == 2
    assert [msg['role'] for msg in history['messages']] == ['user','assistant']
    assert history['messages'][1]['sources'][0]['document_id'] == doc['id']
    assert history['title'].startswith('How many days')
    assert client.get('/conversations').json()[0]['id'] == cid
    main.init_db()  # simulate service restart / non-destructive migration
    assert len(client.get(f'/conversations/{cid}').json()['messages']) == 2
    assert client.delete(f'/conversations/{cid}').json() == {'deleted':True}
    assert client.get(f'/conversations/{cid}').status_code == 404
    assert client.get(f'/documents/{doc["id"]}').status_code == 200


def test_missing_evidence_stored_as_abstention():
    client.post('/documents', json={'title':'Policy','content':'Employees receive 20 days of annual leave.'})
    cid=client.post('/conversations').json()['id']
    response=client.post(f'/conversations/{cid}/messages',json={'question':'What is the annual employee bonus percentage?'})
    assert response.json()['mode']=='abstain'
    assert response.json()['sources']==[]
    assert client.get(f'/conversations/{cid}').json()['messages'][-1]['mode']=='abstain'


def test_error_paths_and_input_validation():
    assert client.get('/conversations/not-present').status_code == 404
    assert client.post('/conversations/not-present/messages',json={'question':'Will it work?'}).status_code == 404
    cid = client.post('/conversations').json()['id']
    assert client.post(f'/conversations/{cid}/messages',json={'question':'a'}).status_code == 422
    assert client.delete('/conversations/not-present').status_code == 404


def test_existing_v13_database_is_upgraded_without_data_loss(tmp_path, monkeypatch):
    old=tmp_path/'legacy.sqlite'
    with sqlite3.connect(old) as connection:
        connection.executescript('''
          CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'text', created_at TEXT NOT NULL);
          CREATE TABLE actions (id TEXT PRIMARY KEY, expression TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL, decided_at TEXT);
          INSERT INTO documents VALUES ('legacy','Old policy','Keep this content','text','2026-01-01');
        ''')
    monkeypatch.setattr(main,'DB',old)
    main.init_db()
    assert client.get('/documents/legacy').json()['content']=='Keep this content'
    assert client.get('/conversations').json()==[]
    assert client.post('/conversations').status_code==201
