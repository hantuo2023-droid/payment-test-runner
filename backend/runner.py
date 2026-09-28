import asyncio
import json
import os
import threading
import time
import zipfile
from urllib.parse import urlsplit
from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
from backend.store import rows, execute, seal, unseal, now, DATA, connect
from backend.tasks.browser_task import execute_task, Outcome

ARTIFACTS = DATA / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
SHUTDOWN = threading.Event()
THREAD = None
TIMEOUT = int(os.getenv('PTR_TIMEOUT','30'))

from backend.network_transport import BrowserNetwork, close_browser_network


def clean_url(value):
    parsed = urlsplit(value)
    return parsed.scheme+'://'+parsed.netloc+parsed.path if parsed.hostname else ''

def scrub_trace(source, destination, secrets):
    def clean(value):
        if isinstance(value,dict):
            return {k:('[REDACTED]' if k in ('value','password','postData','cookies','headers') else clean(v)) for k,v in value.items()}
        if isinstance(value,list): return [clean(v) for v in value]
        if isinstance(value,str):
            for secret in secrets:
                if secret: value = value.replace(secret,'[REDACTED]')
        return value
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as target:
        for name in original.namelist():
            if name.endswith(('.trace','.network','.stacks')):
                content = original.read(name).decode()
                target.writestr(name,'\n'.join(json.dumps(clean(json.loads(line))) for line in content.splitlines() if line.strip()))
    source.unlink(missing_ok=True)

async def run_item(pw, run, result, account, network, card, cache):
    task = json.loads(run['task_snapshot'])
    credentials = {'email':account['email'],'password':unseal(account['secret'])}
    folder = ARTIFACTS / str(run['id']) / str(result['id'])
    folder.mkdir(parents=True,exist_ok=True)
    started = time.monotonic()
    browser = context = page = watcher = lease = None
    trace_started = False
    status,code = 'ERROR','UNKNOWN_RESULT'
    reason=''
    final_url=''
    pair=(account['id'],network['id'])
    def cancelled():
        if SHUTDOWN.is_set() or rows('SELECT stop FROM runs WHERE id=?',(run['id'],))[0]['stop']:
            raise Outcome('STOPPED','CANCELLED')
    def step(state,action,page=None):
        execute('UPDATE results SET step=? WHERE id=?',(state,result['id']))
        event = {'time':now(),'run_id':run['id'],'account':account['email'],'network':network['name'],'test_data_id':result['card_id'],'step':state,'url':clean_url(page.url) if page else '', 'action':action,'result':action if state in ('COMPLETED','ERROR','CANCELLED') else '', 'error':action if state == 'ERROR' else ''}
        with (folder/'log.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(event,ensure_ascii=False)+'\n')
    execute("UPDATE results SET status='RUNNING',started_at=?,account_id=?,email=?,network_id=?,network_name=? WHERE id=?",(now(),account['id'],account['email'],network['id'],network['name'],result['id']))
    if result['card_id']:
        execute('UPDATE cards SET used=1,selected=0,use_count=use_count+1,last_used_at=? WHERE id=?',(now(),result['card_id']))
    try:
        cancelled()
        if pair in cache:
            browser,context,page,lease=cache[pair]
            step('REUSING_CONTEXT','Reusing current Browser Context and Session',page)
        else:
            for old_browser,_,_,old_lease in cache.values(): await close_browser_network(old_browser,old_lease)
            cache.clear()
            step('STARTING_BROWSER','Chromium started')
            lease = BrowserNetwork(network)
            proxy = await lease.start()
            browser = await pw.chromium.launch(headless=True,proxy=proxy)
            session = rows("SELECT * FROM sessions WHERE account_id=? AND task_id=? AND state='VALID' AND version=?",(account['id'],task['id'],task['version']))
            storage = unseal(session[0]['secret']) if session else None
            context = await browser.new_context(storage_state=storage,viewport={'width':1280,'height':900})
            if task['environment'] != 'Production':
                allowed = urlsplit(task['base_url'])
                async def guard(route):
                    url = urlsplit(route.request.url)
                    if url.scheme in ('http','https') and (url.scheme,url.netloc) != (allowed.scheme,allowed.netloc): await route.abort('blockedbyclient')
                    else: await route.continue_()
                await context.route('**/*',guard)
            page = await context.new_page()
            cache[pair]=(browser,context,page,lease)
        await context.tracing.start(screenshots=False,snapshots=False,sources=False)
        trace_started = True
        page.set_default_timeout(TIMEOUT*1000)
        async def watch_stop():
            while True:
                await asyncio.sleep(.2)
                try: cancelled()
                except Outcome:
                    await page.close()
                    return
        watcher = asyncio.create_task(watch_stop())
        async def save_session():
            state = await context.storage_state()
            execute('INSERT OR REPLACE INTO sessions(account_id,task_id,version,state,secret) VALUES(?,?,?,?,?)',(account['id'],task['id'],task['version'],'VALID',seal(state)))
        outcome = await execute_task(page,task,credentials,card,step,cancelled,save_session,TIMEOUT)
        status,code,reason=outcome['status'],outcome['code'],outcome['reason']
        cancelled()
    except Outcome as exc:
        status,code,reason = exc.status,exc.code,exc.code
    except BrowserTimeout:
        code = 'LOGIN_TIMEOUT' if rows('SELECT step FROM results WHERE id=?',(result['id'],))[0]['step'] == 'AUTHENTICATING' else 'TARGET_NOT_FOUND'
    except Exception:
        # Browser exception strings can contain filled values and URLs. Never persist them.
        try: cancelled()
        except Outcome: status,code = 'CANCELLED','STOPPED'
        else: code = 'NETWORK_ERROR'
    finally:
        if watcher:
            watcher.cancel()
            try: await watcher
            except asyncio.CancelledError: pass
            except Exception: pass
        evidence_error = False
        if page and not page.is_closed():
            final_url=clean_url(page.url)
            try:
                from backend.result_wait import stable_visible
                if not await stable_visible(page): raise RuntimeError('No stable visible document')
                await page.screenshot(path=str(folder/'screenshot.png'),full_page=True,mask=[frame.locator('input,textarea') for frame in page.frames],timeout=5000)
                step('EVIDENCE_SAVED','Screenshot captured after terminal detection or true timeout',page)
            except Exception: evidence_error = True
        if context and trace_started:
            try:
                temporary = folder/'private-trace.zip'
                await context.tracing.stop(path=str(temporary))
                scrub_trace(temporary,folder/'trace.zip',[credentials['password']]+([card['number'],card['cvc']] if card else []))
            except Exception:
                (folder/'private-trace.zip').unlink(missing_ok=True)
                evidence_error = True
        if browser and (status=='CANCELLED' or code in ('NETWORK_ERROR','BAD_CREDENTIALS','LOGIN_TIMEOUT')):
            try: await close_browser_network(browser,lease)
            except Exception: evidence_error = True
            cache.pop(pair,None)
        if lease and pair not in cache:
            try: await close_browser_network(browser,lease)
            except Exception: evidence_error = True
        if evidence_error:
            step('EVIDENCE_WARNING','Some browser evidence could not be saved')
        if code in ('BAD_CREDENTIALS','LOGIN_TIMEOUT'):
            execute("UPDATE sessions SET state='EXPIRED' WHERE account_id=? AND task_id=?",(account['id'],task['id']))
        reason=reason or code
        step('RESULT',f'{status} / {code}: {reason}',page)
        step('CANCELLED' if status == 'CANCELLED' else 'ERROR' if status == 'ERROR' else 'COMPLETED',code)
        with connect() as db:
            db.execute('UPDATE results SET status=?,code=?,reason=?,final_url=?,ended_at=?,duration=? WHERE id=?',(status,code,reason,final_url,now(),round(time.monotonic()-started,3),result['id']))
            db.execute('UPDATE accounts SET last_result=? WHERE id=?',(code,account['id']))
            if result['card_id']: db.execute('UPDATE cards SET last_result=? WHERE id=?',(code,result['card_id']))
    return code

async def run_batch(run):
    execute("UPDATE runs SET status='RUNNING' WHERE id=?",(run['id'],))
    resources=unseal(run['resources_snapshot'])
    accounts=resources['accounts'][:]
    networks=resources['networks'][:]
    cards={c['id']:unseal(c['secret']) for c in resources['cards']}
    cache={}
    account_cursor=network_cursor=0
    try:
        async with async_playwright() as pw:
            try:
                for item in rows("SELECT * FROM results WHERE run_id=? AND status='WAITING' ORDER BY id",(run['id'],)):
                    if SHUTDOWN.is_set() or rows('SELECT stop FROM runs WHERE id=?',(run['id'],))[0]['stop']: break
                    exhaustion='NO_AVAILABLE_ACCOUNT' if not accounts else 'NO_AVAILABLE_NETWORK' if not networks else None
                    if exhaustion:
                        execute("UPDATE results SET status='ERROR',code=?,reason=?,step='NOT_EXECUTED',ended_at=? WHERE run_id=? AND status='WAITING'",(exhaustion,exhaustion,now(),run['id']))
                        break
                    account=accounts[account_cursor % len(accounts)]
                    if not item['card_id']:
                        account=next((a for a in accounts if a['id']==item['account_id']),account)
                    network=networks[network_cursor % len(networks)]
                    code=await run_item(pw,run,item,account,network,cards.get(item['card_id']),cache)
                    account_cursor+=1
                    network_cursor+=1
                    if code in ('BAD_CREDENTIALS','LOGIN_TIMEOUT'):
                        accounts=[a for a in accounts if a['id']!=account['id']]
                        execute("UPDATE accounts SET status='UNAVAILABLE' WHERE id=?",(account['id'],))
                    if code=='NETWORK_ERROR':
                        networks=[n for n in networks if n['id']!=network['id']]
                        execute("UPDATE networks SET status='FAILED',reason='NETWORK_ERROR' WHERE id=?",(network['id'],))
                    if code=='ACCESS_BLOCKED':
                        # End this run instead of moving the blocked activity to a new IP.
                        execute("UPDATE results SET status='CANCELLED',code='ACCESS_BLOCKED',reason='Site restriction; no node rotation',step='NOT_EXECUTED',ended_at=? WHERE run_id=? AND status='WAITING'",(now(),run['id']))
                        break
            finally:
                for browser,_,_,lease in cache.values():
                    try: await close_browser_network(browser,lease)
                    except Exception: pass
    except Exception:
        execute("UPDATE results SET status='ERROR',code='WORKER_ERROR',reason='Worker interrupted',step='ERROR',ended_at=? WHERE run_id=? AND status='RUNNING'",(now(),run['id']))
    finally:
        execute("UPDATE results SET status='CANCELLED',code='NOT_EXECUTED',step='CANCELLED',ended_at=? WHERE run_id=? AND status='WAITING'",(now(),run['id']))
        stopped=SHUTDOWN.is_set() or rows('SELECT stop FROM runs WHERE id=?',(run['id'],))[0]['stop']
        execute('UPDATE runs SET status=?,ended_at=? WHERE id=?',('CANCELLED' if stopped else 'COMPLETED',now(),run['id']))

def worker_loop():
    while not SHUTDOWN.wait(.3):
        pending = rows("SELECT * FROM runs WHERE status='QUEUED' ORDER BY id LIMIT 1")
        if pending: asyncio.run(run_batch(pending[0]))

def start_worker():
    global THREAD
    # Restart recovery: never repeat a possibly submitted transaction.
    execute("UPDATE results SET status='ERROR',code='INTERRUPTED',step='ERROR',ended_at=? WHERE status='RUNNING'",(now(),))
    execute("UPDATE results SET status='CANCELLED',code='INTERRUPTED',step='CANCELLED',ended_at=? WHERE status='WAITING'",(now(),))
    execute("UPDATE runs SET status='INTERRUPTED',ended_at=? WHERE status IN ('QUEUED','RUNNING')",(now(),))
    SHUTDOWN.clear()
    THREAD = threading.Thread(target=worker_loop,daemon=True,name='chromium-worker')
    THREAD.start()

def stop_worker():
    SHUTDOWN.set()
    if THREAD: THREAD.join(timeout=15)
