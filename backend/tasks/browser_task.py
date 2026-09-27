"""Internal adapters. Custom binding sites implement the documented DOM contract."""
import asyncio
import re
import time
from urllib.parse import urlsplit
from playwright.async_api import Error as BrowserError
from backend.result_wait import wait_terminal

class Outcome(Exception):
    def __init__(self, code, status='ERROR'):
        self.code, self.status = code, status

async def wait_for(check, timeout, cancelled, code='TARGET_NOT_FOUND'):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        cancelled()
        try:
            result = await check()
            if result:
                return result
        except BrowserError as exc:
            text = str(exc).lower()
            if not any(x in text for x in ('execution context','navigation','detached','cannot find context')):
                raise
        await asyncio.sleep(.15)
    raise Outcome(code)

async def execute_task(page, config, credentials, card, step, cancelled, save_session, timeout=30):
    async def has(locator):
        return await locator.count() > 0 and await locator.first.is_visible()
    email = page.get_by_role('textbox', name=re.compile('email',re.I))
    if config['adapter'] in ('sandbox','contract_binding'):
        email = page.locator('input[name="email"]')
    password = page.locator('input[type="password"]')
    add = page.get_by_role('button',name=re.compile(r'^Add card$',re.I))
    heading = page.get_by_text(re.compile(r'^Payment methods$',re.I))
    async def page_state():
        if await has(heading) and await has(add): return 'target'
        if await has(email) and await has(password): return 'login'
        return None
    async def navigate(url):
        cancelled()
        try:
            response = await page.goto(url,wait_until='domcontentloaded',timeout=timeout*1000)
        except BrowserError as exc:
            if any(text in str(exc).lower() for text in ('err_aborted','execution context was destroyed','interrupted by another navigation')):
                return  # Continue bounded state detection through normal navigation.
            raise
        if response and response.status in (403,429):
            raise Outcome('ACCESS_BLOCKED')
        if response and response.status >= 500:
            raise Outcome('NETWORK_ERROR')
    step('NAVIGATING','Opening target page',page)
    await navigate(config['target_url'])
    step('WAITING_PAGE','Waiting for target or login',page)
    state = await wait_for(page_state,timeout,cancelled)
    if state == 'login':
        step('AUTH_REQUIRED','Login required',page)
        step('AUTHENTICATING','Filling credentials',page)
        await email.first.fill(credentials['email'])
        await password.first.fill(credentials['password'])
        await page.get_by_role('button',name=re.compile(r'^Log\s*in$',re.I)).first.click()
        async def authenticated():
            if await has(page.get_by_text(re.compile(r'BAD_CREDENTIALS|incorrect password|invalid credentials',re.I))):
                raise Outcome('BAD_CREDENTIALS')
            return await has(heading) and await has(add)
        await wait_for(authenticated,timeout,cancelled,'LOGIN_TIMEOUT')
        step('AUTH_SUCCESS','Login successful',page)
        await save_session()
        step('TARGET_LOADING','Opening Payment Methods',page)
        await navigate(config['target_url'])
        async def target_ready(): return await has(heading) and await has(add)
        await wait_for(target_ready,timeout,cancelled)
    else:
        await save_session()
    step('TARGET_READY','Payment Methods ready',page)
    await add.first.click()
    async def form_ready():
        return await has(page.get_by_text(re.compile(r'^Save a payment card$',re.I)))
    await wait_for(form_ready,timeout,cancelled)
    step('FORM_OPEN','Add Card opened',page)
    if config['environment'] == 'Production':
        step('FINAL_STATE_DETECTED','UI_VERIFIED',page)
        return {'status':'SUCCESS','code':'UI_VERIFIED','reason':'Add Card form visibly verified'}
    if not config['authorized'] or not card:
        raise Outcome('INVALID_CONFIGURATION')
    from backend.tasks.data_contract import validate_data
    if validate_data(config,card): raise Outcome('INVALID_DATA','FAIL')
    # Strict adapter contract; never guess selectors or infer success from absence of errors.
    step('FILLING','Filling synthetic test data',page)
    for field,key in [('card_number','number'),('month','month'),('year','year'),('cvc','cvc')]:
        cancelled()
        await page.locator(f'input[name="{field}"]').fill(card[key],timeout=timeout*1000)
    blocked = False
    def response_received(response):
        nonlocal blocked
        if response.status in (403,429) and urlsplit(response.url).netloc == urlsplit(config['target_url']).netloc:
            blocked = True
    page.on('response',response_received)
    async def parse_result():
        if blocked or await has(page.locator('[data-result="ACCESS_BLOCKED"], [data-security="captcha"]')):
            return {'terminal':True,'status':'ERROR','code':'ACCESS_BLOCKED','reason':'Site access/security restriction; no IP rotation'}
        if await has(page.locator('[aria-busy="true"], [data-processing="true"], [role="progressbar"]')):
            return {'processing':True}
        for code in ('3DS_REQUIRED','DECLINED','INVALID_DATA','BOUND'):
            if await has(page.locator(f'[data-result="{code}"]')):
                return {'terminal':True,'status':'SUCCESS' if code=='BOUND' else 'FAIL','code':code,'reason':f'Visible adapter terminal marker: {code}'}
        for frame in page.frames[1:]:
            marker=frame.locator('[data-result="3DS_REQUIRED"]')
            if await marker.count() and await marker.first.is_visible() and await (await frame.frame_element()).is_visible():
                return {'terminal':True,'status':'FAIL','code':'3DS_REQUIRED','reason':'Verification iframe loaded with visible challenge marker'}
        return {'processing':False}
    try:
        step('SUBMITTING','Submitting',page)
        await page.get_by_role('button',name='Submit',exact=True).click()
        step('WAITING_RESULT','waiting for terminal state',page)
        return await wait_terminal(page,parse_result,timeout,cancelled,step)
    finally:
        page.remove_listener('response',response_received)
