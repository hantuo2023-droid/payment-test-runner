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

def proxy_config(network):
    if network['protocol'] == 'Direct': return None
    return {'server':f'{"http" if network["protocol"] == "HTTP" else "socks5"}://{network["host"]}:{network["port"]}',**({'username':network['username'],'password':unseal(network['secret'])} if network.get('username') else {})}

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

async def run_item(pw, run, result):
    task = json.loads(run['task_snapshot'])
    network = unseal(run['network_snapshot'])
    account = rows('SELECT * FROM accounts WHERE id=?',(result['account_id'],))[0]
    credentials = {'email':account['email'],'password':unseal(account['secret'])}
    card_rows = rows('SELECT secret FROM cards WHERE id=?',(result['card_id'],)) if result['card_id'] else []
    card = unseal(card_rows[0]['secret']) if card_rows else None
    folder = ARTIFACTS / str(run['id']) / str(result['id'])
    folder.mkdir(parents=True,exist_ok=True)
    started = time.monotonic()
    browser = context = page = watcher = None
    trace_started = False
    status,code = 'ERROR','UNKNOWN_RESULT'
    def cancelled():
        if SHUTDOWN.is_set() or rows('SELECT stop FROM runs WHERE id=?',(run['id'],))[0]['stop']:
            raise Outcome('STOPPED','CANCELLED')
    def step(state,action,page=None):
        execute('UPDATE results SET step=? WHERE id=?',(state,result['id']))
        event = {'time':now(),'run_id':run['id'],'account':result['email'],'step':state,'url':clean_url(page.url) if page else '', 'action':action}
        with (folder/'log.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(event,ensure_ascii=False)+'\n')
    execute("UPDATE results SET status='RUNNING',started_at=? WHERE id=?",(now(),result['id']))
    try:
        cancelled()
        step('STARTING_BROWSER','Chromium started')
        browser = await pw.chromium.launch(headless=True,proxy=proxy_config(network))
        session = rows("SELECT * FROM sessions WHERE account_id=? AND task_id=? AND state='VALID' AND version=?",(account['id'],task['id'],task['version']))
        storage = unseal(session[0]['secret']) if session else None
        context = await browser.new_context(storage_state=storage,viewport={'width':1280,'height':900})
        # Binding never navigates away from the explicitly authorized task origin.
        if task['environment'] != 'Production':
            allowed = urlsplit(task['base_url'])
            async def guard(route):
                url = urlsplit(route.request.url)
                if url.scheme in ('http','https') and (url.scheme,url.netloc) != (allowed.scheme,allowed.netloc):
                    await route.abort('blockedbyclient')
                else: await route.continue_()
            await context.route('**/*',guard)
        await context.tracing.start(screenshots=False,snapshots=False,sources=False)
        trace_started = True
        page = await context.new_page()
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
        status,code = await execute_task(page,task,credentials,card,step,cancelled,save_session,TIMEOUT)
        cancelled()
    except Outcome as exc:
        status,code = exc.status,exc.code
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
        evidence_error = False
        if page and not page.is_closed():
            try:
                await page.screenshot(path=str(folder/'screenshot.png'),mask=[page.locator('input,textarea,iframe')],timeout=5000)
            except Exception: evidence_error = True
        if context and trace_started:
            try:
                temporary = folder/'private-trace.zip'
                await context.tracing.stop(path=str(temporary))
                scrub_trace(temporary,folder/'trace.zip',[credentials['password']]+([card['number'],card['cvc']] if card else []))
            except Exception:
                (folder/'private-trace.zip').unlink(missing_ok=True)
                evidence_error = True
        if browser:
            await browser.close()
        if evidence_error:
            step('EVIDENCE_WARNING','Some browser evidence could not be saved')
        if code in ('BAD_CREDENTIALS','LOGIN_TIMEOUT'):
            execute("UPDATE sessions SET state='EXPIRED' WHERE account_id=? AND task_id=?",(account['id'],task['id']))
        step('CANCELLED' if status == 'CANCELLED' else 'ERROR' if status == 'ERROR' else 'COMPLETED',code)
        with connect() as db:
            db.execute('UPDATE results SET status=?,code=?,ended_at=?,duration=? WHERE id=?',(status,code,now(),round(time.monotonic()-started,3),result['id']))
            db.execute('UPDATE accounts SET last_result=? WHERE id=?',(code,account['id']))
            # Reserve-use semantics: once an item starts, never silently reuse it.
            if result['card_id']: db.execute('UPDATE cards SET used=1 WHERE id=?',(result['card_id'],))

async def run_batch(run):
    execute("UPDATE runs SET status='RUNNING' WHERE id=?",(run['id'],))
    try:
        async with async_playwright() as pw:
            for item in rows("SELECT * FROM results WHERE run_id=? AND status='WAITING' ORDER BY id",(run['id'],)):
                if SHUTDOWN.is_set() or rows('SELECT stop FROM runs WHERE id=?',(run['id'],))[0]['stop']: break
                await run_item(pw,run,item)
    except Exception:
        execute("UPDATE results SET status='ERROR',code='WORKER_ERROR',step='ERROR',ended_at=? WHERE run_id=? AND status='RUNNING'",(now(),run['id']))
    finally:
        execute("UPDATE results SET status='CANCELLED',code='NOT_EXECUTED',step='CANCELLED',ended_at=? WHERE run_id=? AND status='WAITING'",(now(),run['id']))
        stopped = SHUTDOWN.is_set() or rows('SELECT stop FROM runs WHERE id=?',(run['id'],))[0]['stop']
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
