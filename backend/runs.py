import asyncio
import json
import secrets
import shutil
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
from backend.auth import require_admin
from backend.catalog import get_row, export_file, busy, Selection
from backend.store import rows, connect, execute, now, seal, DATA
from backend.runner import ARTIFACTS, proxy_config
from backend import runner

router = APIRouter(prefix='/api',dependencies=[Depends(require_admin)])
PROBES = {}

class Plan(BaseModel):
    task_id: int
    network_id: int = 1
    account_ids: list[int] = Field(default_factory=list,max_length=10000)
    card_ids: list[int] = Field(default_factory=list,max_length=10000)

def prepare(body):
    task = get_row('tasks',body.task_id)
    network = get_row('networks',body.network_id)
    reasons = []
    if not task['enabled']: reasons.append('任务已停用')
    if not all(task.get(k) for k in ('base_url','login_url','target_url')): reasons.append('Task 缺少必要 URL')
    if task['environment'] != 'Production' and not task['authorized']: reasons.append('请在任务中确认对测试环境的授权')
    if not body.account_ids: reasons.append('请先选择账号')
    if len(body.account_ids) != len(set(body.account_ids)): reasons.append('账号不能重复')
    if len(body.card_ids) != len(set(body.card_ids)): reasons.append('测试数据不能重复')
    account_ids = {a['id'] for a in rows('SELECT id FROM accounts')}
    available = {c['id'] for c in rows('SELECT id FROM cards WHERE used=0')}
    if not set(body.account_ids) <= account_ids: reasons.append('选择的账号已删除')
    if not set(body.card_ids) <= available: reasons.append('选择的测试数据已使用或已删除')
    binding = task['environment'] != 'Production'
    if binding and len(body.card_ids) < len(body.account_ids): reasons.append(f'测试数据不足，本次最多执行 {len(body.card_ids)} 条；请减少选择账号')
    if not runner.THREAD or not runner.THREAD.is_alive(): reasons.append('Worker 不可用')
    if shutil.disk_usage(DATA).free < 100*1024*1024: reasons.append('磁盘可用空间不足 100 MB')
    return task,network,reasons

async def probe_browser(task,network):
    started = time.monotonic()
    browser = None
    chromium = False
    try:
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(headless=True,proxy=proxy_config(network))
                chromium = True
                page = await browser.new_page()
                response = await page.goto(task['target_url'],wait_until='domcontentloaded',timeout=15000)
                if not response or response.status >= 400:
                    return {'chromium':True,'connected':False,'reason':f'目标返回 HTTP {response.status if response else "未知"}'}
                return {'chromium':True,'connected':True,'latency_ms':round((time.monotonic()-started)*1000),'reason':''}
            finally:
                if browser: await browser.close()
    except Exception:
        return {'chromium':chromium,'connected':False,'reason':'浏览器启动或连接目标失败，请检查 Chromium、地址及网络配置'}

@router.post('/preflight')
def preflight(body: Plan):
    task,network,reasons = prepare(body)
    probe = asyncio.run(probe_browser(task,network))
    if not probe['connected']: reasons.append(probe['reason'])
    key = secrets.token_urlsafe(24)
    # Short-lived proof tied to the exact account/data/task/network selection.
    PROBES[key] = (time.monotonic(),body.model_dump(),task,network)
    for old in list(PROBES):
        if time.monotonic()-PROBES[old][0] > 120: PROBES.pop(old,None)
    return dict(probe,ready=not reasons,reasons=reasons,proof=key if not reasons else '',executable=min(len(body.account_ids),len(body.card_ids)) if task['environment'] != 'Production' else len(body.account_ids))

class Start(Plan):
    proof: str

@router.post('/runs')
def start(body: Start):
    task,network,reasons = prepare(body)
    proof = PROBES.pop(body.proof,None)
    current = Plan(**body.model_dump()).model_dump()
    if not proof or time.monotonic()-proof[0] > 120 or proof[1:] != (current,task,network):
        reasons.append('准备检查已失效，请重新检查')
    if reasons: raise HTTPException(400,'；'.join(reasons))
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM runs WHERE status IN ('QUEUED','RUNNING')").fetchone():
            raise HTTPException(409,'已有运行中的任务')
        # Recheck under the same write transaction that creates the run.
        for aid in body.account_ids:
            if not db.execute('SELECT 1 FROM accounts WHERE id=?',(aid,)).fetchone(): raise HTTPException(409,'账号已删除')
        for cid in body.card_ids:
            if not db.execute('SELECT 1 FROM cards WHERE id=? AND used=0',(cid,)).fetchone(): raise HTTPException(409,'测试数据不可用')
        run_id = db.execute('INSERT INTO runs(task_id,task_version,task_snapshot,network_snapshot,status,started_at) VALUES(?,?,?,?,?,?)',(task['id'],task['version'],json.dumps(task),seal(network),'QUEUED',now())).lastrowid
        for index,aid in enumerate(body.account_ids):
            account = db.execute('SELECT email FROM accounts WHERE id=?',(aid,)).fetchone()
            card = db.execute('SELECT id,masked FROM cards WHERE id=?',(body.card_ids[index],)).fetchone() if task['environment'] != 'Production' else None
            db.execute('INSERT INTO results(run_id,account_id,card_id,email,masked,status) VALUES(?,?,?,?,?,?)',(run_id,aid,card['id'] if card else None,account['email'],card['masked'] if card else '—','WAITING'))
    return {'id':run_id}

@router.get('/runs')
def list_runs():
    output = []
    for run in rows('SELECT id,task_snapshot,task_version,status,started_at,ended_at FROM runs ORDER BY id DESC'):
        run['task'] = json.loads(run.pop('task_snapshot'))['name']
        run['counts'] = {x['status']:x['n'] for x in rows('SELECT status,COUNT(*) n FROM results WHERE run_id=? GROUP BY status',(run['id'],))}
        run['total'] = sum(run['counts'].values())
        output.append(run)
    return output

@router.get('/runs/{run_id}')
def detail(run_id: int):
    run = get_row('runs',run_id)
    from backend.store import unseal
    network = unseal(run.pop('network_snapshot'))
    run['network'] = network['name']
    run['task'] = json.loads(run.pop('task_snapshot'))
    run['results'] = rows('SELECT * FROM results WHERE run_id=? ORDER BY id',(run_id,))
    for result in run['results']:
        result['artifacts'] = [name for name in ('screenshot.png','trace.zip','log.jsonl') if (ARTIFACTS/str(run_id)/str(result['id'])/name).exists()]
    return run

@router.post('/runs/{run_id}/stop')
def stop(run_id: int):
    get_row('runs',run_id)
    execute('UPDATE runs SET stop=1 WHERE id=?',(run_id,))
    return {'ok':True}

@router.get('/runs/{run_id}/export')
def export_run(run_id: int, format: str = 'csv'):
    get_row('runs',run_id)
    if format not in ('csv','txt'): raise HTTPException(400,'格式错误')
    return export_file(rows('SELECT * FROM results WHERE run_id=?',(run_id,)),['run_id','email','masked','status','code','ended_at','duration'],f'run-{run_id}',format)

@router.get('/runs/{run_id}/results/{result_id}/artifacts/{name}')
def artifact(run_id: int,result_id: int,name: str):
    if name not in ('screenshot.png','trace.zip','log.jsonl'): raise HTTPException(404)
    if not rows('SELECT id FROM results WHERE run_id=? AND id=?',(run_id,result_id)): raise HTTPException(404)
    path = ARTIFACTS/str(run_id)/str(result_id)/name
    if not path.is_file(): raise HTTPException(404,'文件已清理或未生成')
    return FileResponse(path,filename=name if name == 'trace.zip' else None)

@router.post('/runs/{run_id}/results/delete')
def delete_results(run_id: int,body: Selection):
    busy()
    if not body.confirmed: raise HTTPException(400,'需要二次确认')
    for item in rows('SELECT id FROM results WHERE run_id=?',(run_id,)):
        if body.all or item['id'] in body.ids:
            folder = ARTIFACTS/str(run_id)/str(item['id'])
            if folder.exists(): shutil.rmtree(folder)
            execute('DELETE FROM results WHERE id=?',(item['id'],))
    return {'ok':True}

@router.post('/runs/delete')
def delete_runs(body: Selection):
    busy()
    if not body.confirmed: raise HTTPException(400,'需要二次确认')
    for run in rows('SELECT id FROM runs'):
        if body.all or run['id'] in body.ids:
            folder = ARTIFACTS/str(run['id'])
            if folder.exists(): shutil.rmtree(folder)
            execute('DELETE FROM runs WHERE id=?',(run['id'],))
    return {'ok':True}

@router.get('/data-management')
def stats():
    result = {name:rows(f'SELECT COUNT(*) n FROM {name}')[0]['n'] for name in ('accounts','cards','runs','results','sessions')}
    for key,extension in [('screenshots','*.png'),('traces','*.zip'),('logs','*.jsonl')]:
        result[key] = sum(p.stat().st_size for p in ARTIFACTS.rglob(extension))
    result['disk_bytes'] = sum(p.stat().st_size for p in DATA.rglob('*') if p.is_file())
    result['free_bytes'] = shutil.disk_usage(DATA).free
    return result

class Cleanup(BaseModel):
    kind: str
    days: int = 30
    confirmed: bool = False

@router.post('/data-management/cleanup')
def cleanup(body: Cleanup):
    busy()
    if not body.confirmed or body.days not in (0,7,30): raise HTTPException(400,'请确认删除并选择 7 天、30 天或全部')
    if body.kind == 'sessions':
        execute("DELETE FROM sessions WHERE state='EXPIRED'")
    elif body.kind in ('runs','screenshots','traces','logs'):
        cutoff = (datetime.now(timezone.utc)-timedelta(days=body.days)).isoformat()
        ids = [r['id'] for r in rows('SELECT id FROM runs WHERE started_at<?',(cutoff,))]
        if body.kind == 'runs': delete_runs(Selection(ids=ids,confirmed=True))
        else:
            extension = {'screenshots':'*.png','traces':'*.zip','logs':'*.jsonl'}[body.kind]
            for rid in ids:
                for path in (ARTIFACTS/str(rid)).rglob(extension): path.unlink()
    else: raise HTTPException(400,'清理类型错误')
    return stats()
