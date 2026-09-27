"""Browser acceptance against Next.js and live FastAPI/Sandbox servers."""
import os
from pathlib import Path
os.environ['PTR_DATA']=str(Path('test-output/ui-data').resolve())
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from playwright.async_api import async_playwright
from backend.store import migrate,rows,execute
from backend.auth import initialize

ROOT=Path.cwd()

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
        async def import_data(button,text):
            await page.get_by_role('button',name=button,exact=True).first.click()
            dialog=page.get_by_role('dialog')
            await dialog.get_by_label('粘贴文本',exact=False).fill(text)
            await dialog.get_by_role('button',name='预览导入').click()
            await dialog.get_by_role('button',name='确认导入').click()
            await dialog.wait_for(state='hidden')
        await import_data('导入账号','ui@example.com | sandbox-pass\ndelay-ui@example.com----sandbox-pass')
        await import_data('导入测试数据','4242424242424242|12|2035|123\n4000000000000002|12|2035|123')
        for button in ('选择账号','选择数据'):
            await page.get_by_role('button',name=button,exact=True).click()
            await page.get_by_role('button',name='全选可用').click()
            await page.get_by_role('button',name='确认选择').click()
        await page.get_by_role('button',name='检查准备状态').click()
        await page.get_by_role('button',name='START',exact=True).wait_for()
        for _ in range(100):
            if await page.get_by_role('button',name='START',exact=True).is_enabled(): break
            await asyncio.sleep(.2)
        assert await page.get_by_role('button',name='START',exact=True).is_enabled()
        await page.screenshot(path='test-output/home-desktop.png',full_page=True)
        await page.get_by_role('button',name='START',exact=True).click()
        await page.get_by_role('heading',name='Run #',exact=False).wait_for()
        for _ in range(150):
            if await page.get_by_role('cell',name='BOUND',exact=True).count() and await page.get_by_role('cell',name='DECLINED',exact=True).count(): break
            await asyncio.sleep(.5)
        assert await page.get_by_role('cell',name='BOUND',exact=True).count()==1
        assert await page.get_by_role('cell',name='DECLINED',exact=True).count()==1
        await page.screenshot(path='test-output/run-desktop.png',full_page=True)
        async with page.expect_download() as dl:
            await page.get_by_role('button',name='导出 CSV',exact=True).click()
        download=await dl.value
        await download.save_as('test-output/ui-export.csv')
        assert 'sandbox-pass' not in Path('test-output/ui-export.csv').read_text(encoding='utf-8')
        for label in ('账号','测试数据','任务','设置','首页'):
            await page.locator('nav').get_by_role('button',name=label,exact=True).click()
            await asyncio.sleep(.15)
        await page.set_viewport_size({'width':820,'height':1100})
        await page.screenshot(path='test-output/home-tablet.png',full_page=True)
        assert not errors,errors
        await browser.close()
        print(json.dumps({'UI login':'PASS','UI import preview/confirm':'PASS','UI selection/preflight/start':'PASS','UI live results':'PASS','UI CSV download':'PASS','six menus':'PASS','page_errors':errors},indent=2))

def main():
    migrate()
    if not rows("SELECT * FROM settings WHERE key='admin_password'"): initialize('ui-acceptance-password')
    for table in ('results','runs','sessions','accounts','cards','previews'): execute(f'DELETE FROM {table}')
    env=dict(os.environ,BACKEND_URL='http://127.0.0.1:8001',NEXT_TELEMETRY_DISABLED='1')
    processes=[]
    handles=[]
    try:
        commands=[([sys.executable,'-m','uvicorn','sandbox.app:app','--port','8080'],ROOT),([sys.executable,'-m','uvicorn','backend.main:app','--port','8001'],ROOT),(['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','3001'],ROOT/'frontend')]
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
        for proc in reversed(processes):
            if os.name=='nt': subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else: proc.terminate()
        for proc in processes: proc.wait(timeout=15)
        for handle in handles: handle.close()

if __name__=='__main__':main()
