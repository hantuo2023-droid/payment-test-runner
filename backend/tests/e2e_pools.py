"""v0.2 acceptance. All result rows originate from real Chromium Fill/Submit."""
import os
from datetime import datetime
from pathlib import Path
os.environ['PTR_DATA']=str(Path('test-output/v02-live-'+datetime.now().strftime('%Y%m%d-%H%M%S')).resolve())
os.environ['PTR_SANDBOX_URL']='http://127.0.0.1:18080'
os.environ['PTR_TIMEOUT']='4'
import asyncio
import json
import socket
import subprocess
import sys
import time
from PIL import Image
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from backend.main import app
from backend.auth import initialize
from backend.store import migrate,rows,execute
from backend.tests.http_proxy import Proxy
from backend.result_wait import wait_terminal
from backend.origin_policy import restrict_context

ROOT=Path(os.environ['PTR_DATA'])
REPORT={'data_root':str(ROOT)}

def verify_image(path):
    with Image.open(path).convert('RGB') as image:
        count=sum(1 for pixel in image.getdata() if pixel==(34,170,136))
        assert count>10000,f'Blank/wrong screenshot: only {count} terminal pixels'

async def navigation_regression():
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        context=await browser.new_context(service_workers='block')
        await restrict_context(context,{'environment':'QA','base_url':'http://127.0.0.1:18080'})
        page=await context.new_page()
        await page.goto('http://127.0.0.1:18080/health')
        try:
            await page.goto('http://localhost:18080/health')
        except Exception:
            pass
        else:
            raise AssertionError('Unauthorized alternate origin was reachable')
        await page.close()
        page=await context.new_page()
        await page.goto('http://127.0.0.1:18080/health')
        REPORT['Exact origin browser boundary']='PASS'
        events=[]
        first=True
        async def observe():
            nonlocal first
            if first:
                first=False
                await page.evaluate('() => new Promise(resolve => setTimeout(resolve, 1000))')
            loc=page.locator('[data-result="BOUND"]')
            return {'terminal':True,'status':'SUCCESS','code':'BOUND'} if await loc.count() and await loc.is_visible() else {}
        async def navigate():
            await asyncio.sleep(.15)
            await page.goto('http://127.0.0.1:18080/final/BOUND')
        task=asyncio.create_task(navigate())
        result=await wait_terminal(page,observe,4,lambda:None,lambda state,action,page:events.append((state,action)))
        await task
        assert result['code']=='BOUND' and any('transient' in action for _,action in events),events
        await browser.close()
        REPORT['Navigation Transient Regression']='PASS (real execution-context destruction)'

def main():
    migrate()
    if not rows("SELECT 1 FROM settings WHERE key='admin_password'"):initialize('acceptance-pools-password')
    for table in ('results','runs','sessions','accounts','cards','previews'):execute(f'DELETE FROM {table}')
    execute("DELETE FROM networks WHERE protocol!='Direct'")
    execute('DELETE FROM tasks WHERE id>2')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','sandbox.app:app','--port','18080'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    proxies=[Proxy(18881).start(),Proxy(18882).start()]
    try:
        for _ in range(80):
            try:
                with socket.create_connection(('127.0.0.1',18080),timeout=.2):break
            except OSError:time.sleep(.1)
        if '--navigation-only' in sys.argv:
            asyncio.run(navigation_regression())
            Path('test-output/origin-navigation-report.json').write_text(json.dumps(REPORT,indent=2),encoding='utf-8')
            print(json.dumps(REPORT,indent=2))
            return
        with TestClient(app) as client:
            client.headers['X-PTR-Client']='web'
            assert client.post('/api/auth/login',json={'password':'acceptance-pools-password'}).status_code==200
            def post(path,body):
                r=client.post('/api'+path,json=body)
                assert r.status_code==200,(path,r.text)
                return r.json()
            def imp(kind,text):
                p=post('/import/preview',{'kind':kind,'text':text})
                assert not p['errors'],p
                return post('/import/confirm',{'preview_id':p['preview_id']})
            imp('accounts','one@example.com|sandbox-pass\ntwo@example.com|sandbox-pass\nthree@example.com----sandbox-pass')
            account_ids=[a['id'] for a in client.get('/api/accounts').json()][::-1]
            imp('networks','http://127.0.0.1:18881\nhttp://127.0.0.1:18882')
            networks=client.get('/api/networks').json()
            direct=next(n['id'] for n in networks if n['protocol']=='Direct')
            nodes=[n['id'] for n in networks if n['protocol']=='HTTP']
            assert all(n['selected'] for n in networks if n['protocol']!='Direct')
            assert not next(n['selected'] for n in networks if n['protocol']=='Direct')
            def selection(kind,ids):
                post('/pools/'+kind+'/selection',{'all':True,'selected':False})
                assert not any(r['selected'] for r in client.get('/api/'+kind).json())
                for i in ids:post('/pools/'+kind+'/selection',{'ids':[i],'selected':True})
                assert sorted(r['id'] for r in client.get('/api/'+kind).json() if r['selected'])==sorted(ids)
            counter=0
            def data(n,number='4242424242424242'):
                nonlocal counter
                old={c['id'] for c in client.get('/api/cards').json()}
                lines=[]
                for _ in range(n):
                    lines.append(f'{number}|{counter%12+1}|{2035+counter//12}|123')
                    counter+=1
                imp('cards','\n'.join(lines))
                created=[c for c in client.get('/api/cards').json() if c['id'] not in old]
                assert all(c['selected'] for c in created)
                return sorted(c['id'] for c in created)
            def task(scenario='immediate',environment='Sandbox'):
                t={'name':scenario,'description':'Real browser acceptance','environment':environment,'base_url':'http://127.0.0.1:18080','login_url':'http://127.0.0.1:18080/login','target_url':'http://127.0.0.1:18080/settings/payments/'+scenario,'authorized':environment!='Production','enabled':True}
                return post('/tasks',t)['id']
            def start(tid,accounts,cards,nodes, before_start=None):
                selection('accounts',accounts);selection('cards',cards);selection('networks',nodes)
                body={'task_id':tid}  # Server must use persisted checkbox selections.
                p=post('/preflight',body)
                assert p['ready'],p
                if before_start:before_start()
                return post('/runs',dict(body,proof=p['proof']))['id']
            def wait(rid):
                for _ in range(2400):
                    r=client.get(f'/api/runs/{rid}').json()
                    if r['status'] not in ('QUEUED','RUNNING'):return r
                    time.sleep(.06)
                raise AssertionError('Run timeout')
            def log(rid):return client.get(f'/api/runs/{rid}/logs').json()
            def verify(r,expected,login=None):
                items=r['results']
                assert len(items)==expected and len({x['card_id'] for x in items})==expected,items
                events=[]
                for item in items:
                    assert item['code']=='BOUND',item
                    folder=ROOT/'artifacts'/str(r['id'])/str(item['id'])
                    events += [json.loads(s) for s in (folder/'log.jsonl').read_text(encoding='utf-8').splitlines()]
                    verify_image(folder/'screenshot.png')
                counts={k:sum(e['step']==k for e in events) for k in ('AUTH_SUCCESS','FILLING','SUBMITTING','STARTING_BROWSER')}
                assert counts['FILLING']==expected and counts['SUBMITTING']==expected,counts
                if login is not None:assert counts['AUTH_SUCCESS']==login,counts
                for before,after in zip(items,items[1:]):assert before['ended_at']<=after['started_at']
                return {'RunItems':len(items),'Login count':counts['AUTH_SUCCESS'],'Fill count':counts['FILLING'],'Submit count':counts['SUBMITTING'],'Results':len(items),'Browser launches':counts['STARTING_BROWSER']}
            for n in (5,10):
                tid=task('spinner')
                rid=start(tid,account_ids[:1],data(n),[direct])
                REPORT[f'1 account + {n} test data']=verify(wait(rid),n,1)
                print(f'PASS 1 account + {n} data',flush=True)
                assert REPORT[f'1 account + {n} test data']['Browser launches']==1
            selected=data(12)
            multi=wait(start(task(),account_ids,selected,nodes))
            verify(multi,12)
            assert all(p.binds>0 for p in proxies)
            assert {r['network_id'] for r in multi['results']}==set(nodes)
            REPORT['Multiple resources']={'Selected Test Data':12,'RunItems':12,'Duplicate Test Data Execution':'NO','proxy_submits':[p.binds for p in proxies]}
            hundred=data(100)
            subset=hundred[::6][:17]
            partial=wait(start(task(),account_ids[:2],subset,[direct]))
            verify(partial,17)
            assert {r['card_id'] for r in partial['results']}==set(subset)
            REPORT['Custom partial selection']={'Database new records':100,'Selected':17,'RunItems':17}
            # Explicit re-selection of a previously used record is supported.
            rerun=wait(start(task(),account_ids[:1],subset[:1],[direct]))
            verify(rerun,1)
            assert rows('SELECT use_count FROM cards WHERE id=?',(subset[0],))[0]['use_count']==2
            for kind in ('accounts','cards','networks'):
                post('/pools/'+kind+'/selection',{'all':True,'selected':True})
                assert all(r['selected'] for r in client.get('/api/'+kind).json())
                post('/pools/'+kind+'/selection',{'all':True,'selected':False})
                assert not any(r['selected'] for r in client.get('/api/'+kind).json())
                assert client.get('/api/'+kind+'/export').status_code==200
                REPORT[kind+' selection/import/export']='PASS'
            scenarios=[('immediate','4242424242424242','BOUND'),('spinner','4242424242424242','BOUND'),('spinner','4000000000000002','DECLINED'),('spinner','4000000000003220','3DS_REQUIRED'),('redirect','4242424242424242','BOUND'),('multiple','4242424242424242','BOUND'),('delayed','4242424242424242','BOUND'),('iframe','4000000000003220','3DS_REQUIRED'),('spinner','4000000000009995','UNKNOWN_RESULT')]
            for mode,number,expected in scenarios:
                r=wait(start(task(mode),account_ids[:1],data(1,number),[direct]));item=r['results'][0]
                assert item['code']==expected,item
                events=log(r['id'])
                if expected!='UNKNOWN_RESULT':
                    verify_image(ROOT/'artifacts'/str(r['id'])/str(item['id'])/'screenshot.png')
                    final=next(e for e in events if e['step']=='FINAL_STATE_DETECTED')
                    evidence=next(e for e in events if e['step']=='EVIDENCE_SAVED')
                    assert final['time']<evidence['time']
                else:assert any(e['step']=='RESULT_TIMEOUT' for e in events)
                if mode in ('redirect','multiple','delayed'):assert '/final/' in item['final_url']
                if mode=='spinner':assert any(e['step']=='PROCESSING' for e in events)
                REPORT[mode+' → '+expected]='PASS'
                print(f'PASS {mode} {expected}',flush=True)
            stopcards=data(8)
            stopped_id=start(task('spinner'),account_ids[:1],stopcards,[direct])
            for _ in range(400):
                r=client.get(f'/api/runs/{stopped_id}').json()
                if sum(x['status']=='SUCCESS' for x in r['results'])>=2 and any(x['step']=='PROCESSING' for x in r['results']):break
                time.sleep(.06)
            post(f'/runs/{stopped_id}/stop',{})
            stopped=wait(stopped_id)
            assert sum(x['status']=='SUCCESS' for x in stopped['results'])>=2
            assert any(x['code']=='NOT_EXECUTED' for x in stopped['results'])
            for item in stopped['results']:
                if item['code']=='NOT_EXECUTED':assert rows('SELECT use_count FROM cards WHERE id=?',(item['card_id'],))[0]['use_count']==0
            REPORT['Batch STOP']='PASS'
            imp('accounts','bad-batch@example.com|incorrect')
            bad=next(a['id'] for a in client.get('/api/accounts').json() if a['email']=='bad-batch@example.com')
            badrun=wait(start(task(),[bad],data(4),[direct]))
            assert all(r['code']=='NO_AVAILABLE_ACCOUNT' for r in badrun['results'])
            assert all(rows('SELECT use_count FROM cards WHERE id=?',(r['card_id'],))[0]['use_count']==0 for r in badrun['results'])
            # A healthy checked node fails after preflight; remaining selected node continues.
            failnode=Proxy(18883).start()
            imp('networks','http://127.0.0.1:18883')
            failed_id=next(n['id'] for n in client.get('/api/networks').json() if n['port']==18883)
            # Ascending ids: this new proxy comes second; after its failure the first resumes.
            fallback=wait(start(task(),account_ids[:1],data(4),[nodes[0],failed_id],failnode.stop))
            assert [r['code'] for r in fallback['results']]==['BOUND']*4,fallback
            REPORT['Bad resource isolation']='PASS'
            for fmt in ('csv','txt'):
                export=client.get(f"/api/runs/{partial['id']}/export?format={fmt}")
                assert export.status_code==200 and 'network_name' in export.text and 'reason' in export.text
                assert 'sandbox-pass' not in export.text and '4242424242424242' not in export.text
            assert len(client.get(f"/api/runs/{multi['id']}").json()['results'])==12
            REPORT.update({'Session reuse':'PASS','Default auto-selected':'PASS','Sequential final-before-next':'PASS','Blank Screenshot Regression':'PASS (saved PNG terminal pixels checked)','Final result log':'PASS','Run Isolation':'PASS','TXT / CSV Export':'PASS'})
        asyncio.run(navigation_regression())
        Path('test-output/v02-e2e-report.json').write_text(json.dumps(REPORT,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(REPORT,indent=2,ensure_ascii=True))
    finally:
        for proxy in proxies:proxy.stop()
        server.terminate();server.wait(timeout=10)

if __name__=='__main__':main()
