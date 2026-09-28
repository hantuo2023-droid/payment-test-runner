"""Real Chromium integration acceptance. Run as a module, no browser mocks."""
import os
from datetime import datetime
from pathlib import Path
os.environ['PTR_DATA'] = str(Path('test-output/v02-core-'+datetime.now().strftime('%Y%m%d-%H%M%S')).resolve())
os.environ['PTR_TIMEOUT'] = '5'
os.environ['PTR_SANDBOX_URL']='http://127.0.0.1:18082'
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
from backend.store import migrate, rows, execute, unseal, seal

def run():
    migrate()
    if not rows("SELECT * FROM settings WHERE key='admin_password'"): initialize('acceptance-password')
    server = subprocess.Popen([sys.executable,'-m','uvicorn','sandbox.app:app','--host','127.0.0.1','--port','18082'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1',18082),timeout=.2): break
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
            fixtures = ['4242424242424242','4000000000000002','4000000000003220','4000000000000069','4242424242424242','4000000000009995','4000000000009995','4242424242424242']
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
            codes=['BOUND','DECLINED','3DS_REQUIRED','INVALID_DATA','BOUND','UNKNOWN_RESULT']
            if '--tail-only' not in sys.argv:
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
                second_id=start(['stop','bound'],cids[6:])
                for _ in range(100):
                    current=client.get(f'/api/runs/{second_id}').json()
                    if current['results'][0]['step'] in ('WAITING_RESULT','PROCESSING'): break
                    time.sleep(.1)
                assert client.post(f'/api/runs/{second_id}/stop').status_code==200
                second=wait(second_id)
                assert all(r['status']=='CANCELLED' for r in second['results']),second
                assert second['results'][1]['code']=='NOT_EXECUTED'
                assert len(client.get(f'/api/runs/{rid}').json()['results'])==6
                assert client.post('/api/runs/delete',json={'ids':[second_id],'confirmed':True}).status_code==200
                assert len(client.get('/api/accounts').json())==7
                assert client.get(f'/api/runs/{second_id}').status_code==404
                # Session reuse, expiry fallback, task version isolation checked directly.
                assert rows("SELECT COUNT(*) n FROM sessions WHERE state='VALID'")[0]['n']>=6
                for month,expired in [(10,False),(11,True)]:
                    if expired:
                        session=rows('SELECT secret FROM sessions WHERE account_id=? AND task_id=1',(aid['bound'],))[0]
                        state=unseal(session['secret'])
                        state['cookies']=[]
                        execute('UPDATE sessions SET secret=? WHERE account_id=? AND task_id=1',(seal(state),aid['bound']))
                    import_text('cards',f'4242424242424242|{month}|2035|123')
                    cid=max(c['id'] for c in client.get('/api/cards').json())
                    srid=start(['bound'],[cid])
                    session_run=wait(srid)
                    assert session_run['results'][0]['code']=='BOUND'
                    events=client.get(f'/api/runs/{srid}/logs').json()
                    assert any(e['step']=='AUTHENTICATING' for e in events)==expired
            # Explicit bad credentials are classified separately from timeouts.
            import_text('accounts','bad@example.com|wrong-password')
            aid['bad']=max(a['id'] for a in client.get('/api/accounts').json())
            import_text('cards','4242424242424242|9|2035|123')
            bad_id=start(['bad'],[max(c['id'] for c in client.get('/api/cards').json())])
            assert wait(bad_id)['results'][0]['code']=='NO_AVAILABLE_ACCOUNT'
            assert any(e['step']=='ERROR' and e['action']=='BAD_CREDENTIALS' for e in client.get(f'/api/runs/{bad_id}/logs').json())
            import_text('accounts','login-timeout@example.com|sandbox-pass')
            aid['login-timeout']=max(a['id'] for a in client.get('/api/accounts').json())
            timeout_id=start(['login-timeout'],[cids[7]])
            assert wait(timeout_id)['results'][0]['code']=='NO_AVAILABLE_ACCOUNT'
            assert any(e['step']=='ERROR' and e['action']=='LOGIN_TIMEOUT' for e in client.get(f'/api/runs/{timeout_id}/logs').json())
            # Real connection failure must prevent START.
            network=client.post('/api/networks',json={'name':'Dead proxy','protocol':'HTTP','host':'127.0.0.1','port':9}).json()
            probe=client.post('/api/preflight',json={'task_id':1,'network_id':network['id'],'account_ids':[aid['bound']],'card_ids':[]}).json()
            assert not probe['ready'] and not probe['connected'] and not probe['proof']
            assert client.post('/api/runs',json={'task_id':1,'network_id':network['id'],'account_ids':[aid['bound']],'card_ids':[],'proof':''}).status_code==400
            # Production UI task on the controlled site opens the form without binding.
            config=client.get('/api/tasks').json()[0]
            config.update(name='Local Production UI',environment='Production',authorized=False)
            ui_task=client.post('/api/tasks',json=config).json()
            body={'task_id':ui_task['id'],'network_id':1,'account_ids':[aid['bound']],'card_ids':[]}
            proof=client.post('/api/preflight',json=body).json()
            ui_id=client.post('/api/runs',json=dict(body,proof=proof['proof'])).json()['id']
            assert wait(ui_id)['results'][0]['code']=='UI_VERIFIED'
            assert not any(e['step'] in ('FILLING','SUBMITTING') for e in client.get(f'/api/runs/{ui_id}/logs').json())
            execute('DELETE FROM tasks WHERE id=?',(ui_task['id'],))
            report={'mode':'LIVE','codes':codes,'stop_active_and_waiting':'PASS','run_isolation':'PASS','exports':'PASS','delete_run':'PASS','artifacts_redacted':'PASS','session_reuse':'PASS','expired_session_relogin':'PASS','bad_credentials':'PASS','login_timeout':'PASS','failed_network_blocks_start':'PASS','production_ui_no_binding':'PASS'}
            if '--tail-only' in sys.argv:
                report={k:v for k,v in report.items() if k in ('bad_credentials','login_timeout','failed_network_blocks_start','production_ui_no_binding')}
            Path('test-output/e2e-tail-report.json' if '--tail-only' in sys.argv else 'test-output/e2e-report.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
    finally:
        server.terminate()
        server.wait(timeout=10)

if __name__=='__main__': run()
