"""Resource exhaustion and access restriction checks using real Chromium."""
import os
from pathlib import Path
from datetime import datetime
os.environ['PTR_DATA']=str(Path('test-output/v02-faults-'+datetime.now().strftime('%Y%m%d-%H%M%S')).resolve())
os.environ['PTR_SANDBOX_URL']='http://127.0.0.1:18083'
os.environ['PTR_TIMEOUT']='4'
import json
import socket
import subprocess
import sys
import time
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import initialize
from backend.store import migrate, rows, execute
from backend.tests.http_proxy import Proxy

def main():
    migrate();initialize('fault-acceptance-password')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','sandbox.app:app','--port','18083'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    proxies=[Proxy(18884,18083).start(),Proxy(18885,18083).start(),Proxy(18886,18083).start()]
    try:
        for _ in range(60):
            try:
                with socket.create_connection(('127.0.0.1',18083),timeout=.2):break
            except OSError:time.sleep(.1)
        with TestClient(app) as c:
            c.headers['X-PTR-Client']='web'
            assert c.post('/api/auth/login',json={'password':'fault-acceptance-password'}).status_code==200
            def post(path,body):
                r=c.post('/api'+path,json=body)
                assert r.status_code==200,r.text
                return r.json()
            def imp(kind,text):
                p=post('/import/preview',{'kind':kind,'text':text})
                assert not p['errors']
                post('/import/confirm',{'preview_id':p['preview_id']})
            imp('accounts','bad@example.com|incorrect\ngood@example.com|sandbox-pass')
            imp('cards','\n'.join(f'4242424242424242|{m}|2040|123' for m in range(1,5)))
            imp('networks','\n'.join(f'http://127.0.0.1:{p}' for p in (18884,18885,18886,9)))
            accounts=sorted(a['id'] for a in c.get('/api/accounts').json())
            cards=sorted(a['id'] for a in c.get('/api/cards').json())
            nodes={n['port']:n['id'] for n in c.get('/api/networks').json() if n['port']}
            def run(a,n,before=None):
                body={'task_id':1,'account_ids':a,'card_ids':cards,'network_ids':n}
                p=post('/preflight',body);assert p['ready'],p
                if before:before()
                rid=post('/runs',dict(body,proof=p['proof']))['id']
                for _ in range(1200):
                    result=c.get(f'/api/runs/{rid}').json()
                    if result['status'] not in ('QUEUED','RUNNING'):return result,p
                    time.sleep(.05)
                raise AssertionError('Run timed out')
            if '--account-exhaustion-only' in sys.argv:
                exhausted,_=run(accounts[:1],[1])
                assert [r['code'] for r in exhausted['results']]==['NO_AVAILABLE_ACCOUNT']*4
                assert all(r['step']=='NOT_EXECUTED' for r in exhausted['results'])
                assert all(r['used']==0 and r['selected']==1 and r['use_count']==0 and r['last_used_at'] is None for r in rows('SELECT * FROM cards'))
                events=c.get(f"/api/runs/{exhausted['id']}/logs").json()
                assert not any(e['step']=='SUBMITTING' for e in events)
                report={'all accounts unavailable preserves unused selected data':'PASS','no submission when all accounts unavailable':'PASS'}
                Path('test-output/checkpoint-3-account-exhaustion.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
                print(json.dumps(report,indent=2))
                return
            mixed,_=run(accounts,[1])
            assert [r['code'] for r in mixed['results']]==['BOUND']*4
            assert all(r['account_id']==accounts[1] for r in mixed['results'])
            assert [r['use_count'] for r in rows('SELECT use_count FROM cards ORDER BY id')]==[1]*4
            healthy,proof=run(accounts[1:],[nodes[18884],nodes[9]])
            assert any(not n['connected'] for n in proof['networks'])
            assert all(r['network_id']==nodes[18884] and r['code']=='BOUND' for r in healthy['results'])
            exhausted,_=run(accounts[1:],[nodes[18886]],proxies[2].stop)
            assert [r['code'] for r in exhausted['results']]==['NO_AVAILABLE_NETWORK']*4
            assert [r['use_count'] for r in rows('SELECT use_count FROM cards ORDER BY id')]==[2]*4
            proxies[2]=None
            proxies[2]=Proxy(18886,18083).start()
            recovered,_=run(accounts[1:],[nodes[18884],nodes[18886]],proxies[0].stop)
            proxies[0]=None
            assert [r['code'] for r in recovered['results']]==['BOUND']*4
            assert all(r['network_id']==nodes[18886] for r in recovered['results'])
            assert [r['use_count'] for r in rows('SELECT use_count FROM cards ORDER BY id')]==[3]*4
            proxies[0]=Proxy(18884,18083).start()
            before=proxies[1].binds
            proxies[0].deny_bind=True
            blocked,_=run(accounts[1:],[nodes[18884],nodes[18885]])
            assert all(r['code']=='ACCESS_BLOCKED' for r in blocked['results']),blocked
            assert proxies[1].binds==before  # No switch to another node after 429.
            assert all(r['step']=='NOT_EXECUTED' for r in blocked['results'][1:])
            assert [r['use_count'] for r in rows('SELECT use_count FROM cards ORDER BY id')]==[4,3,3,3]
            proxies[0].deny_bind=False
            proxies[0].drop_bind=True
            before=proxies[1].binds
            unknown,_=run(accounts[1:],[nodes[18884],nodes[18885]])
            assert [r['code'] for r in unknown['results']]==['UNKNOWN_RESULT','BOUND','UNKNOWN_RESULT','BOUND']
            assert proxies[1].binds==before+2
            events=c.get(f"/api/runs/{unknown['id']}/logs").json()
            assert sum(e['step']=='SUBMITTING' for e in events)==4
            assert [r['use_count'] for r in rows('SELECT use_count FROM cards ORDER BY id')]==[5,4,4,4]
            report={'pre-submit same data survives bad account and node':'PASS','pre-submit exhaustion does not consume data':'PASS','post-submit unknown never resubmits':'PASS','bad account removed; remaining account continues':'PASS','failed preflight node excluded':'PASS','NO_AVAILABLE_NETWORK':'PASS','HTTP 429 after Submit stops without node switch':'PASS'}
            Path('test-output/checkpoint-3-faults.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report,indent=2))
    finally:
        for p in proxies:
            if p:p.stop()
        server.terminate();server.wait(timeout=10)

if __name__=='__main__':main()
