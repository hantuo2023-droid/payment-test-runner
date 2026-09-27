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
from backend.catalog import Task, validate_task
from backend.store import rows, connect, execute, now, seal, DATA
from backend.runner import ARTIFACTS, proxy_config
from backend import runner

router = APIRouter(prefix='/api',dependencies=[Depends(require_admin)])
PROBES = {}

@router.post('/tasks/test-address')
def test_address(body: Task, network_id: int = 1):
    validate_task(body)
    return asyncio.run(probe_browser(body.model_dump(),get_row('networks',network_id)))

class Plan(BaseModel):
    task_id: int
    network_ids: list[int] | None = Field(default=None,max_length=10000)
    network_id: int | None = None  # v0.1 client compatibility
    account_ids: list[int] | None = Field(default=None,max_length=10000)
    card_ids: list[int] | None = Field(default=None,max_length=10000)

def chosen(body):
    a = body.account_ids if body.account_ids is not None else [r['id'] for r in rows("SELECT id FROM accounts WHERE selected=1 AND status='READY'")]
    c = body.card_ids if body.card_ids is not None else [r['id'] for r in rows('SELECT id FROM cards WHERE selected=1')]
    n = body.network_ids if body.network_ids is not None else [body.network_id] if body.network_id is not None else [r['id'] for r in rows('SELECT id FROM networks WHERE selected=1')]
    return {'accounts':sorted(a),'cards':sorted(c),'networks':sorted(n)}

def prepare(body):
    from backend.store import unseal
    from backend.tasks.data_contract import validate_data
    task = get_row('tasks',body.task_id)
    ids = chosen(body)
    reasons = []
    resources = {kind:[get_row(kind,i) for i in selected] for kind,selected in ids.items()}
    if any(len(v) != len(set(v)) for v in ids.values()): reasons.append('同类资源不能重复选择')
    if not task['enabled']: reasons.append('任务已停用')
    if not all(task.get(k) for k in ('base_url','login_url','target_url')): reasons.append('Task 缺少必要 URL')
    if task['environment'] != 'Production' and not task['authorized']: reasons.append('请确认对测试环境的授权')
    resources['accounts'] = [a for a in resources['accounts'] if a['status']=='READY']
    if not resources['accounts']: reasons.append('请至少选择一个有效账号')
    if not resources['networks']: reasons.append('请至少选择一个节点（Direct 也可以）')
    if task['environment'] != 'Production':
        if not resources['cards']: reasons.append('请至少选择一条测试数据')
        for card in resources['cards']:
            error = validate_data(task,unseal(card['secret']))
            if error:
                reasons.append(f"数据 #{card['id']}: {error}")
                break
    if not runner.THREAD or not runner.THREAD.is_alive(): reasons.append('Worker 不可用')
    if shutil.disk_usage(DATA).free < 100*1024*1024: reasons.append('磁盘可用空间不足 100 MB')
    return task,resources,reasons

def signature(task, resources):
    # Health timestamps and usage counters are observations, not configuration.
    fields={'accounts':('id','email','secret','status'),'cards':('id','secret'),'networks':('id','name','protocol','host','port','username','secret')}
    return json.dumps([task,{k:[{f:r.get(f) for f in fields[k]} for r in v] for k,v in resources.items()}],sort_keys=True)

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
                response = await page.goto(task['target_url'],wait_until='domcontentloaded',timeout=10000)
                if not response or response.status >= 400:
                    return {'chromium':True,'connected':False,'reason':f'目标返回 HTTP {response.status if response else "未知"}'}
                return {'chromium':True,'connected':True,'latency_ms':round((time.monotonic()-started)*1000),'reason':''}
            finally:
                if browser: await browser.close()
    except Exception:
        return {'chromium':chromium,'connected':False,'reason':'浏览器启动或连接失败，请检查地址与网络配置'}

async def probe_pool(task, networks):
    reports=[]
    for network in networks:
        report=await probe_browser(task,network)
        execute('UPDATE networks SET status=?,latency_ms=?,checked_at=?,check_task_id=?,check_task_version=?,reason=? WHERE id=?',('CONNECTED' if report['connected'] else 'FAILED',report.get('latency_ms'),now(),task['id'],task['version'],report['reason'],network['id']))
        reports.append(dict(report,id=network['id'],name=network['name']))
    return reports

@router.post('/networks/test')
def test_networks(body: Plan):
    task=get_row('tasks',body.task_id)
    nodes=[get_row('networks',i) for i in chosen(body)['networks']]
    return asyncio.run(probe_pool(task,nodes))

@router.post('/preflight')
def preflight(body: Plan):
    task,resources,reasons = prepare(body)
    reports = asyncio.run(probe_pool(task,resources['networks'])) if not reasons else []
    healthy = [r['id'] for r in reports if r['connected']]
    if not healthy and not reasons: reasons.append('没有可用节点，请选择节点并检查连接')
    key = secrets.token_urlsafe(24)
    PROBES[key]=(time.monotonic(),signature(task,resources),healthy)
    for old in list(PROBES):
        if time.monotonic()-PROBES[old][0] > 120: PROBES.pop(old,None)
    return {'chromium':any(r['chromium'] for r in reports),'connected':bool(healthy),'networks':reports,'ready':not reasons,'reasons':reasons,'reason':'；'.join(reasons),'proof':key if not reasons else '', 'executable':len(resources['cards']) if task['environment'] != 'Production' else len(resources['accounts'])}

class Start(Plan):
    proof: str

@router.post('/runs')
def start(body: Start):
    task,resources,reasons = prepare(body)
    proof=PROBES.pop(body.proof,None)
    if not proof or time.monotonic()-proof[0]>120 or proof[1]!=signature(task,resources): reasons.append('准备检查已失效，请重新检查')
    if reasons: raise HTTPException(400,'；'.join(reasons))
    resources['networks']=[n for n in resources['networks'] if n['id'] in proof[2]]
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM runs WHERE status IN ('QUEUED','RUNNING')").fetchone(): raise HTTPException(409,'已有运行中的任务')
        current_task=dict(db.execute('SELECT * FROM tasks WHERE id=?',(task['id'],)).fetchone())
        if current_task!=task: raise HTTPException(409,'任务已修改，请重新检查')
        for kind,items in resources.items():
            for item in items:
                current=db.execute(f'SELECT * FROM {kind} WHERE id=?',(item['id'],)).fetchone()
                if not current or dict(current).get('secret')!=item.get('secret'): raise HTTPException(409,'资源已修改，请重新检查')
        run_id=db.execute('INSERT INTO runs(task_id,task_version,task_snapshot,network_snapshot,resources_snapshot,status,started_at) VALUES(?,?,?,?,?,?,?)',(task['id'],task['version'],json.dumps(task),seal(resources['networks']),seal(resources),'QUEUED',now())).lastrowid
        items=resources['cards'] if task['environment']!='Production' else resources['accounts']
        for item in items:
            binding=task['environment']!='Production'
            db.execute('INSERT INTO results(run_id,account_id,card_id,email,masked,status,task_id,task_version) VALUES(?,?,?,?,?,?,?,?)',(run_id,None if binding else item['id'],item['id'] if binding else None,'' if binding else item['email'],item['masked'] if binding else '—','WAITING',task['id'],task['version']))
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
    run['network'] = ', '.join(n['name'] for n in network) if isinstance(network,list) else network['name']
    if run.get('resources_snapshot'):
        saved=unseal(run.pop('resources_snapshot'))
        run['resources']={k:[{f:r[f] for f in ('id','email','masked','name') if f in r} for r in v] for k,v in saved.items()}
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
    return export_file(rows('SELECT * FROM results WHERE run_id=?',(run_id,)),['run_id','account_id','email','card_id','masked','network_id','network_name','task_id','task_version','status','code','reason','step','final_url','started_at','ended_at','duration'],f'run-{run_id}',format)

@router.get('/runs/{run_id}/logs')
def live_logs(run_id: int):
    get_row('runs',run_id)
    events = []
    for result in rows('SELECT id FROM results WHERE run_id=? ORDER BY id DESC LIMIT 10',(run_id,)):
        path = ARTIFACTS/str(run_id)/str(result['id'])/'log.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                try: events.append(json.loads(line))
                except json.JSONDecodeError: pass
    return sorted(events,key=lambda e:e['time'])[-200:]

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
