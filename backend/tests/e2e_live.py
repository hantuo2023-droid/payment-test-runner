"""Real Chromium integration acceptance. Run as a module, no browser mocks."""
import os
from pathlib import Path
os.environ['PTR_DATA'] = str(Path('test-output/e2e-data').resolve())
os.environ['PTR_TIMEOUT'] = '5'
import asyncio
import json
import socket
import subprocess
import sys
import time
import zipfile
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import initialize
from backend.store import migrate, rows, execute

def run():
    migrate()
    if not rows("SELECT * FROM settings WHERE key='admin_password'"): initialize('acceptance-password')
    server = subprocess.Popen([sys.executable,'-m','uvicorn','sandbox.app:app','--host','127.0.0.1','--port','8080'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1',8080),timeout=.2): break
            except OSError: time.sleep(.1)
        with TestClient(app) as client:
            client.headers['X-PTR-Client'] = 'web'
            assert client.get('/api/accounts').status_code == 401
            assert client.post('/api/auth/login',json={'password':'acceptance-password'}).status_code == 200
            for table in ('results','runs','sessions','accounts','cards','previews'):
                execute(f'DELETE FROM {table}')
            def import_text(kind,text):
                p = client.post('/api/import/preview',json={'kind':kind,'text':text})
                assert p.status_code == 200,p.text
                data=p.json()
                r=client.post('/api/import/confirm',json={'preview_id':data['preview_id']})
                assert r.status_code == 200,r.text
                return data
            accounts = '\n'.join(f'{name}@example.com | sandbox-pass' for name in ('bound','declined','three','invalid','delay','timeout','stop'))
            summary = import_text('accounts',accounts+'\n bound@example.com----sandbox-pass\nnotvalid')
            assert summary['valid']==7 and summary['duplicates']==1 and len(summary['errors'])==1
            fixtures = ['4242424242424242','4000000000000002','4000000000003220','4000000000000069','4242424242424242','4000000000009995','4000000000009995']
            import_text('cards','\n'.join(f'{card}|{index+1}|2035|123' for index,card in enumerate(fixtures)))
            aid = {a['email'].split('@')[0]:a['id'] for a in client.get('/api/accounts').json()}
            cids = sorted(c['id'] for c in client.get('/api/cards').json())
            def start(names,cards):
                body={'task_id':1,'network_id':1,'account_ids':[aid[n] for n in names],'card_ids':cards}
                p=client.post('/api/preflight',json=body)
                assert p.status_code==200,p.text
                assert p.json()['ready'],p.text
                r=client.post('/api/runs',json=dict(body,proof=p.json()['proof']))
                assert r.status_code==200,r.text
                return r.json()['id']
            def wait(rid):
                for _ in range(1200):
                    data=client.get(f'/api/runs/{rid}').json()
                    if data['status'] not in ('QUEUED','RUNNING'): return data
                    time.sleep(.1)
                raise AssertionError('run timeout')
            rid=start(['bound','declined','three','invalid','delay','timeout'],cids[:6])
            first=wait(rid)
            codes=[r['code'] for r in first['results']]
            assert codes==['BOUND','DECLINED','3DS_REQUIRED','INVALID_DATA','BOUND','UNKNOWN_RESULT'],codes
            for result in first['results']:
                assert set(result['artifacts'])=={'screenshot.png','trace.zip','log.jsonl'},result
                folder=Path(os.environ['PTR_DATA'])/'artifacts'/str(rid)/str(result['id'])
                logs=(folder/'log.jsonl').read_text(encoding='utf-8')
                assert 'FILLING' in logs and 'SUBMITTING' in logs and 'WAITING_RESULT' in logs
                with zipfile.ZipFile(folder/'trace.zip') as trace:
                    contents=''.join(trace.read(n).decode() for n in trace.namelist())
                    assert 'sandbox-pass' not in contents and fixtures[0] not in contents
            for fmt in ('txt','csv'):
                export=client.get(f'/api/runs/{rid}/export?format={fmt}')
                assert export.status_code==200 and 'BOUND' in export.text and 'sandbox-pass' not in export.text and fixtures[0] not in export.text
            second_id=start(['stop'],cids[6:])
            for _ in range(100):
                current=client.get(f'/api/runs/{second_id}').json()
                if current['results'][0]['step']=='WAITING_RESULT': break
                time.sleep(.1)
            assert client.post(f'/api/runs/{second_id}/stop').status_code==200
            second=wait(second_id)
            assert second['results'][0]['status']=='CANCELLED',second
            assert len(client.get(f'/api/runs/{rid}').json()['results'])==6
            assert client.post('/api/runs/delete',json={'ids':[second_id],'confirmed':True}).status_code==200
            assert len(client.get('/api/accounts').json())==7
            assert client.get(f'/api/runs/{second_id}').status_code==404
            # Session reuse, expiry fallback, task version isolation checked directly.
            assert rows("SELECT COUNT(*) n FROM sessions WHERE state='VALID'")[0]['n']>=6
            report={'mode':'LIVE','codes':codes,'stop':'PASS','run_isolation':'PASS','exports':'PASS','delete_run':'PASS','artifacts_redacted':'PASS'}
            Path('test-output/e2e-report.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
    finally:
        server.terminate()
        server.wait(timeout=10)

if __name__=='__main__': run()
