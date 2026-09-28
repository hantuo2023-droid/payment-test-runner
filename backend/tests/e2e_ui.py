"""Browser acceptance against Next.js and live FastAPI/Sandbox servers."""
import os
from datetime import datetime
from pathlib import Path
os.environ['PTR_DATA']=str(Path('test-output/v02-ui-'+datetime.now().strftime('%Y%m%d-%H%M%S')).resolve())
os.environ['PTR_SANDBOX_URL']='http://127.0.0.1:18081'
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from playwright.async_api import async_playwright
from backend.store import migrate,rows,execute
from backend.auth import initialize
from backend.tests.http_proxy import Proxy

ROOT=Path.cwd()

async def warning_test(page):
    before=len(await (await page.request.get('http://127.0.0.1:3001/api/cards')).json())
    await page.locator('nav').get_by_role('button',name='测试数据',exact=True).click()
    await page.get_by_role('button',name='粘贴导入',exact=True).first.click()
    dialog=page.get_by_role('dialog')
    await dialog.get_by_label('粘贴文本',exact=False).fill('4242424242424242|01/20|123')
    await dialog.get_by_role('button',name='预览导入').click()
    await dialog.get_by_role('status').filter(has_text='有效期已过期').wait_for()
    assert '4242424242424242' not in await dialog.get_by_role('status').inner_text()
    assert await dialog.get_by_role('button',name='确认导入').is_enabled()
    await dialog.get_by_role('button',name='确认导入').click()
    await dialog.wait_for(state='hidden')
    assert len(await (await page.request.get('http://127.0.0.1:3001/api/cards')).json())==before+1
    report={'expired data warning visible, masked and import allowed':'PASS'}
    Path('test-output/warning-ui-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)

async def browser_test():
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        page=await browser.new_page(viewport={'width':1512,'height':1100},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        await page.goto('http://127.0.0.1:3001')
        await page.get_by_label('管理员密码',exact=False).fill('ui-acceptance-password')
        await page.get_by_role('button',name='登录',exact=True).click()
        await page.get_by_role('heading',name='Payment Test Runner',exact=False).wait_for()
        if '--warning-only' in sys.argv:
            await warning_test(page)
            assert not errors,errors
            await browser.close()
            return
        async def nav(label):
            await page.locator('nav').get_by_role('button',name=label,exact=True).click()
        async def records(kind): return await (await page.request.get('http://127.0.0.1:3001/api/'+kind)).json()
        async def selected(kind,n):
            for _ in range(100):
                items=await records(kind)
                ids=sorted(r['id'] for r in items if r['selected'])
                on_pool=await page.get_by_role('heading',name={'accounts':'账号','cards':'测试数据','networks':'设置'}[kind],exact=True).count()
                visible_count=await page.locator('table input[type=checkbox]:checked').count()
                if len(ids)==n and (not on_pool or visible_count==n): return ids
                await asyncio.sleep(.1)
            raise AssertionError((kind,n,ids))
        async def import_data(button,text,filename=None):
            await page.get_by_role('button',name=button,exact=True).first.click()
            dialog=page.get_by_role('dialog')
            if filename:
                await dialog.locator('input[type=file]').first.set_input_files({'name':filename,'mimeType':'text/plain','buffer':text.encode()})
            else: await dialog.get_by_label('粘贴文本',exact=False).fill(text)
            await dialog.get_by_role('button',name='预览导入').click()
            await dialog.get_by_role('button',name='确认导入').click()
            await dialog.wait_for(state='hidden')
        async def run(expected):
            await nav('首页')
            await page.get_by_test_id('planned-count').filter(has_text=str(expected)).wait_for()
            start=page.get_by_role('button',name='START',exact=True)
            for _ in range(200):
                if await start.is_enabled(): break
                await asyncio.sleep(.2)
            assert await start.is_enabled(),await page.locator('body').inner_text()
            pools={k:sorted(x['id'] for x in await records(k) if x['selected']) for k in ('accounts','cards','networks')}
            await start.click()  # No manual selection confirmation or readiness button.
            await page.get_by_role('heading',name='Run #',exact=False).wait_for()
            runs=await records('runs');rid=runs[0]['id']
            for _ in range(240):
                result=await records('runs/'+str(rid))
                if result['status'] not in ('RUNNING','QUEUED'):break
                await asyncio.sleep(.25)
            assert len(result['results'])==expected,result
            assert {r['card_id'] for r in result['results']}==set(pools['cards'])
            assert {r['account_id'] for r in result['results']} <= set(pools['accounts'])
            assert {r['network_id'] for r in result['results']} <= set(pools['networks'])
            assert all(r['code'] in ('BOUND','DECLINED','INVALID_DATA') for r in result['results']),result
            await asyncio.sleep(1.6)
            return result
        await import_data('导入账号','ui@example.com | sandbox-pass\ndelay-ui@example.com----sandbox-pass')
        await import_data('导入测试数据','number,month,year,cvc\n4242424242424242,12,2035,123\n4000000000000002,12,2035,123\n4000000000000069,12,2035,123','cards.csv')
        await nav('设置')
        await import_data('粘贴导入节点','http://127.0.0.1:18891\nhttp://127.0.0.1:18892','nodes.txt')
        await selected('accounts',2);await selected('cards',3);await selected('networks',2)
        default=await run(3)
        print('PASS UI default import -> START: 3 real results',flush=True)
        pages={'accounts':'账号','cards':'测试数据','networks':'设置'}
        for kind,label in pages.items():
            await nav(label)
            boxes=page.locator('table input[type=checkbox]')
            total=await boxes.count()
            await page.get_by_role('button',name='全选',exact=True).click()
            await selected(kind,total)
            await page.get_by_role('button',name='取消全选',exact=True).click()
            await selected(kind,0)
            await nav('首页')
            assert not await page.get_by_role('button',name='START',exact=True).is_enabled()
            await nav(label)
            await boxes.first.check()
            await selected(kind,1)
            await boxes.nth(1).check()
            await selected(kind,2)
            await boxes.nth(1).uncheck()
            await selected(kind,1)
        single=await run(1)
        print('PASS UI single selections -> START: 1 real result',flush=True)
        for kind,label in pages.items():
            await nav(label)
            await page.get_by_role('button',name='取消全选',exact=True).click()
            await selected(kind,0)
            boxes=page.locator('table input[type=checkbox]')
            await boxes.first.check();await selected(kind,1)
            await boxes.nth(1).check();await selected(kind,2)
        multi=await run(2)
        print('PASS UI multiple selections -> START: 2 real results',flush=True)
        account=str(multi['results'][0]['account_id'])
        await page.get_by_label('按账号筛选',exact=False).select_option(account)
        assert await page.locator('tbody tr').count()==sum(str(r['account_id'])==account for r in multi['results'])
        await page.get_by_label('按账号筛选',exact=False).select_option('')
        await page.get_by_label('按节点筛选',exact=False).select_option(str(multi['results'][0]['network_id']))
        assert await page.locator('tbody tr').count()==1
        await page.get_by_label('按节点筛选',exact=False).select_option('')
        await page.screenshot(path='test-output/run-desktop.png',full_page=True)
        async with page.expect_download() as dl:
            await page.get_by_role('button',name='导出 CSV',exact=True).click()
        await (await dl.value).save_as('test-output/ui-export.csv')
        assert 'sandbox-pass' not in Path('test-output/ui-export.csv').read_text(encoding='utf-8')
        for label in ('账号','测试数据','任务','设置','首页'):await nav(label)
        await page.screenshot(path='test-output/home-desktop.png',full_page=True)
        await page.set_viewport_size({'width':820,'height':1100})
        await page.screenshot(path='test-output/home-tablet.png',full_page=True)
        await warning_test(page)
        assert not errors,errors
        await browser.close()
        report={'expired data warning visible and import allowed':'PASS','UI login':'PASS','UI paste / CSV / TXT import':'PASS','Default import -> automatic readiness -> START':len(default['results']),'All/none/single/multiple checkboxes in three pools':'PASS','Single selection actual RunItems':len(single['results']),'Multiple selection actual RunItems':len(multi['results']),'UI result filters / export / six menus':'PASS','page_errors':errors}
        Path('test-output/v02-ui-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))


def main():
    migrate()
    if not rows("SELECT * FROM settings WHERE key='admin_password'"): initialize('ui-acceptance-password')
    for table in ('results','runs','sessions','accounts','cards','previews'): execute(f'DELETE FROM {table}')
    env=dict(os.environ,BACKEND_URL='http://127.0.0.1:8001',NEXT_TELEMETRY_DISABLED='1')
    proxies=[Proxy(18891,18081).start(),Proxy(18892,18081).start()]
    processes=[]
    handles=[]
    try:
        commands=[([sys.executable,'-m','uvicorn','sandbox.app:app','--port','18081'],ROOT),([sys.executable,'-m','uvicorn','backend.main:app','--port','8001'],ROOT),(['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','3001'],ROOT/'frontend')]
        for index,(command,cwd) in enumerate(commands):
            handle=open(ROOT/f'test-output/ui-server-{index}.log','w',encoding='utf-8')
            handles.append(handle)
            processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=handle,stderr=handle))
        for _ in range(120):
            try:
                urllib.request.urlopen('http://127.0.0.1:3001',timeout=2)
                break
            except Exception: time.sleep(.5)
        asyncio.run(browser_test())
    finally:
        for proxy in proxies:proxy.stop()
        for proc in reversed(processes):
            if os.name=='nt': subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else: proc.terminate()
        for proc in processes: proc.wait(timeout=15)
        for handle in handles: handle.close()

if __name__=='__main__':main()
