import os
from pathlib import Path
os.environ['PTR_DATA'] = str(Path('test-output/unit').resolve())
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.store import rows,execute,seal,now
from backend.auth import initialize

@pytest.fixture
def client():
    with TestClient(app) as c:
        if not rows("SELECT * FROM settings WHERE key='admin_password'"): initialize('unit-test-password')
        c.headers['X-PTR-Client']='web'
        assert c.post('/api/auth/login',json={'password':'unit-test-password'}).status_code==200
        yield c

def test_import_confirm_delete_and_csrf(client):
    execute("DELETE FROM accounts WHERE email='api@example.com'")
    preview=client.post('/api/import/preview',json={'kind':'accounts','text':'api@example.com|secret-password'}).json()
    assert 'secret-password' not in str(preview)
    assert not rows("SELECT id FROM accounts WHERE email='api@example.com'")
    assert client.post('/api/import/confirm',json={'preview_id':preview['preview_id']}).json()['imported']==1
    assert client.post('/api/import/confirm',json={'preview_id':preview['preview_id']}).status_code==400
    account=next(x for x in client.get('/api/accounts').json() if x['email']=='api@example.com')
    assert 'secret' not in account
    assert 'secret-password' not in client.get('/api/accounts/export').text
    assert client.post('/api/accounts/delete',json={'ids':[account['id']]}).status_code==400
    del client.headers['X-PTR-Client']
    assert client.post('/api/accounts/delete',json={'ids':[account['id']],'confirmed':True}).status_code==403
    client.headers['X-PTR-Client']='web'
    assert client.post('/api/accounts/delete',json={'ids':[account['id']],'confirmed':True}).status_code==200

def test_task_network_and_validation(client):
    task={'name':'Custom QA','description':'Contract','environment':'QA','base_url':'http://localhost:8080','login_url':'http://localhost:8080/login','target_url':'http://localhost:8080/settings/payments','enabled':True,'authorized':True}
    r=client.post('/api/tasks',json=task)
    assert r.status_code==200
    tid=r.json()['id']
    task['target_url']='http://localhost:8080/other'
    r=client.put(f'/api/tasks/{tid}',json=task)
    assert r.json()['version']==2 and r.json()['target_url'].endswith('/other')
    task['target_url']=''
    assert client.put(f'/api/tasks/{tid}',json=task).status_code==400
    assert client.post('/api/networks',json={'name':'proxy','protocol':'HTTP','host':'localhost','port':8081,'password':'proxy-secret'}).status_code==200
    assert 'proxy-secret' not in client.get('/api/networks').text
    bad=client.post('/api/networks',json={'name':'bad','protocol':'HTTP','host':'localhost','port':'secret-value'})
    assert bad.status_code==422 and 'secret-value' not in bad.text
    execute('DELETE FROM tasks WHERE id=?',(tid,))

def test_cleanup_and_restart_recovery(client):
    from backend.runner import ARTIFACTS,stop_worker,start_worker
    rid=execute('INSERT INTO runs(task_id,task_version,task_snapshot,network_snapshot,status,started_at) VALUES(?,?,?,?,?,?)',(1,1,'{}',seal({}),'COMPLETED','2000-01-01T00:00:00+00:00'))
    folder=ARTIFACTS/str(rid)/'1'
    folder.mkdir(parents=True,exist_ok=True)
    for file in ('screenshot.png','trace.zip','log.jsonl'): (folder/file).write_bytes(b'test')
    for kind,file in [('screenshots','screenshot.png'),('traces','trace.zip'),('logs','log.jsonl')]:
        assert client.post('/api/data-management/cleanup',json={'kind':kind,'days':7,'confirmed':True}).status_code==200
        assert not (folder/file).exists()
    assert client.post('/api/runs/delete',json={'ids':[rid],'confirmed':True}).status_code==200
    stop_worker()
    rid=execute('INSERT INTO runs(task_id,task_version,task_snapshot,network_snapshot,status,started_at) VALUES(?,?,?,?,?,?)',(1,1,'{}',seal({}),'RUNNING',now()))
    execute("INSERT INTO results(run_id,email,masked,status) VALUES(?,?,?,'RUNNING')",(rid,'stale@example.com','****4242'))
    start_worker()
    assert rows('SELECT status FROM runs WHERE id=?',(rid,))[0]['status']=='INTERRUPTED'
    assert rows('SELECT code FROM results WHERE run_id=?',(rid,))[0]['code']=='INTERRUPTED'
    assert client.post('/api/runs/delete',json={'ids':[rid],'confirmed':True}).status_code==200
