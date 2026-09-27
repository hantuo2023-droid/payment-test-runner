"""Bounded terminal polling and navigation recovery shared by task adapters."""
import asyncio
import time
from playwright.async_api import Error as BrowserError

def transient(exc):
    return any(x in str(exc).lower() for x in ('execution context','navigation','detached','cannot find context','err_aborted'))

async def wait_terminal(page, observe, timeout, cancelled, step):
    deadline=time.monotonic()+timeout
    last_url=page.url
    previous=None
    candidate=None
    since=0
    heartbeat=0
    while time.monotonic()<deadline:
        cancelled()
        if page.url!=last_url:
            step('POST_SUBMIT_NAVIGATION','URL changed',page)
            last_url=page.url
            candidate=None
        try:
            state=await observe()
        except BrowserError as exc:
            if not transient(exc): raise
            step('POST_SUBMIT_NAVIGATION','Navigation transient; rechecking new document',page)
            candidate=None
            await asyncio.sleep(.12)
            continue
        if state.get('terminal'):
            identity=(page.url,state['code'])
            if candidate!=identity:
                candidate=identity
                since=time.monotonic()
            elif time.monotonic()-since>=.3:
                step('FINAL_STATE_DETECTED',state['code'],page)
                return state
        else:
            candidate=None
            label='PROCESSING' if state.get('processing') else 'WAITING_RESULT'
            if previous!=label or time.monotonic()-heartbeat>2:
                step(label,'spinner/loading detected' if label=='PROCESSING' else 'still waiting for terminal state',page)
                previous=label
                heartbeat=time.monotonic()
        await asyncio.sleep(.15)
    step('RESULT_TIMEOUT','No recognized terminal result before timeout',page)
    return {'status':'ERROR','code':'UNKNOWN_RESULT','reason':'No recognized terminal result before timeout','terminal':False}

async def stable_visible(page, timeout=3):
    deadline=time.monotonic()+timeout
    previous=None
    stable=0
    while time.monotonic()<deadline:
        try:
            visible=await page.locator('body').is_visible() and bool((await page.locator('body').inner_text(timeout=500)).strip())
            if visible and page.url==previous: stable+=1
            else: stable=0
            previous=page.url
            if stable>=2: return True
        except BrowserError: stable=0
        await asyncio.sleep(.15)
    return False
