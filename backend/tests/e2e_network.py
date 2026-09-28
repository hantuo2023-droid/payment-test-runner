"""Checkpoint 2: real SOCKS auth, node editor and Chromium runner only."""
import os
from pathlib import Path
from datetime import datetime
os.environ['PTR_DATA']=str(Path('test-output/network-'+datetime.now().strftime('%Y%m%d-%H%M%S')).resolve())
os.environ['PTR_SANDBOX_URL']='http://127.0.0.1:18084'
os.environ['PTR_TIMEOUT']='5'
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from playwright.async_api import async_playwright
from backend.store import migrate
from backend.auth import initialize
from backend.tests.socks_proxy import SocksProxy

ROOT=Path.cwd()


async def check(proxy):
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        page=await browser.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:3004')
        await page.get_by_label('管理员密码',exact=False).fill('network-test-password')
        await page.get_by_role('button',name='登录',exact=True).click()
        await page.get_by_role('heading',name='Payment Test Runner',exact=False).wait_for()
        async def request(path,body=None,method='POST'):
            response=await page.request.fetch('http://127.0.0.1:3004/api'+path,method=method if body is not None else 'GET',data=body,headers={'X-PTR-Client':'web'})
            assert response.ok,(path,response.status)
            return await response.json()
        async def imp(kind,text):
            preview=await request('/import/preview',{'kind':kind,'text':text})
            assert not preview['errors']
            await request('/import/confirm',{'preview_id':preview['preview_id']})
        await imp('accounts','network@example.com|sandbox-pass')
        await imp('cards','4242424242424242|01|2035|123\n4242424242424242|02|2035|123')
        await imp('networks',f'socks5://fixture-user:fixture-password@127.0.0.1:{proxy.port}')
        # Reload once to pick up API-created fixtures; all following edits are UI.
        await page.reload()
        await page.locator('nav').get_by_role('button',name='设置',exact=True).click()
        nid=next(n['id'] for n in await request('/networks') if n['protocol']=='SOCKS5')
        await page.get_by_role('button',name='编辑节点',exact=True).click()
        dialog=page.get_by_role('dialog')
        assert await dialog.get_by_label('Password',exact=False).input_value()==''
        await dialog.get_by_label('名称',exact=False).fill('Edited SOCKS fixture')
        await dialog.get_by_role('button',name='保存网络').click()
        await dialog.wait_for(state='hidden')
        node=next(n for n in await request('/networks') if n['id']==nid)
        assert node['name']=='Edited SOCKS fixture' and 'secret' not in node
        plan={'task_id':1,'network_ids':[nid]}
        print('Checking valid credentials',flush=True)
        healthy=await request('/preflight',plan)
        assert healthy['ready'],healthy
        # Wrong credential must fail the real upstream and invalidate old proof.
        await page.get_by_role('button',name='编辑节点',exact=True).click()
        await dialog.get_by_label('Password',exact=False).fill('wrong-fixture-password')
        await dialog.get_by_role('button',name='保存网络').click()
        await dialog.wait_for(state='hidden')
        stale=await page.request.post('http://127.0.0.1:3004/api/runs',data=dict(plan,proof=healthy['proof']),headers={'X-PTR-Client':'web'})
        assert stale.status==400
        print('Checking rejected credentials',flush=True)
        failed=await request('/preflight',plan)
        assert not failed['ready'] and proxy.rejected>0
        await page.get_by_role('button',name='编辑节点',exact=True).click()
        await dialog.get_by_label('Password',exact=False).fill('fixture-password')
        await dialog.get_by_role('button',name='保存网络').click()
        await dialog.wait_for(state='hidden')
        print('Checking valid credentials',flush=True)
        healthy=await request('/preflight',plan)
        assert healthy['ready']
        rid=(await request('/runs',dict(plan,proof=healthy['proof'])))['id']
        busy=await page.request.put(f'http://127.0.0.1:3004/api/networks/{nid}',data={'name':'blocked edit','protocol':'SOCKS5','host':'127.0.0.1','port':proxy.port,'username':'fixture-user'},headers={'X-PTR-Client':'web'})
        assert busy.status==409
        for _ in range(300):
            result=await request(f'/runs/{rid}')
            if result['status'] not in ('QUEUED','RUNNING'):break
            await asyncio.sleep(.1)
        assert [r['code'] for r in result['results']]==['BOUND','BOUND'],result
        assert all(r['network_id']==nid for r in result['results'])
        events=await request(f'/runs/{rid}/logs')
        counts={name:sum(e['step']==name for e in events) for name in ('STARTING_BROWSER','AUTH_SUCCESS','FILLING','SUBMITTING','REUSING_CONTEXT')}
        assert counts=={'STARTING_BROWSER':1,'AUTH_SUCCESS':1,'FILLING':2,'SUBMITTING':2,'REUSING_CONTEXT':1},counts
        assert proxy.authenticated>0 and proxy.connections>0 and not errors
        # Clear authentication intentionally, using the same editor control.
        await page.get_by_role('button',name='编辑节点',exact=True).wait_for(state='visible')
        for _ in range(50):
            if await page.get_by_role('button',name='编辑节点',exact=True).is_enabled():break
            await asyncio.sleep(.1)
        await page.get_by_role('button',name='编辑节点',exact=True).click()
        await dialog.get_by_role('checkbox',name='清除用户名和密码',exact=False).check()
        await dialog.get_by_role('button',name='保存网络').click()
        await dialog.wait_for(state='hidden')
        node=next(n for n in await request('/networks') if n['id']==nid)
        assert node['username']==''
        await browser.close()
        report={'authenticated SOCKS5 real Chromium':'PASS','wrong credentials no Direct fallback':'PASS','credential change invalidates proof':'PASS','UI edit / password keep / replace / clear':'PASS','active Run edit rejected':'PASS','counts':counts,'page_errors':errors}
        (ROOT/'test-output/checkpoint-2-network.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))


def main():
    migrate();initialize('network-test-password')
    proxy=SocksProxy(18084).start()
    env=dict(os.environ,BACKEND_URL='http://127.0.0.1:8004',NEXT_TELEMETRY_DISABLED='1')
    processes=[];handles=[]
    try:
        commands=[([sys.executable,'-m','uvicorn','sandbox.app:app','--port','18084'],ROOT),([sys.executable,'-m','uvicorn','backend.main:app','--port','8004'],ROOT),(['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','3004'],ROOT/'frontend')]
        for index,(command,cwd) in enumerate(commands):
            handle=open(ROOT/f'test-output/network-server-{index}.log','w',encoding='utf-8')
            handles.append(handle)
            processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=handle,stderr=handle))
        for _ in range(90):
            try:
                urllib.request.urlopen('http://127.0.0.1:3004',timeout=2)
                break
            except Exception:time.sleep(.5)
        asyncio.run(check(proxy))
    finally:
        proxy.stop()
        for p in reversed(processes):
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:p.terminate()
        for p in processes:p.wait(timeout=15)
        for handle in handles:handle.close()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Playwright request errors include Cookie headers; never print them.
        print('Network E2E failed: '+type(exc).__name__,flush=True)
        import traceback
        for frame in traceback.extract_tb(exc.__traceback__):
            if frame.filename == __file__:
                print(f'{Path(frame.filename).name}:{frame.lineno} {frame.name}',flush=True)
        raise SystemExit(1) from None
