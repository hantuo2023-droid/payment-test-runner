import csv
import io
import json
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from backend.auth import require_admin
from backend.store import rows, execute, connect, seal, unseal

router = APIRouter(prefix='/api', dependencies=[Depends(require_admin)])

def get_row(table, item_id):
    found = rows(f'SELECT * FROM {table} WHERE id=?',(item_id,))
    if not found:
        raise HTTPException(404,'数据不存在')
    return found[0]

def busy():
    if rows("SELECT id FROM runs WHERE status IN ('QUEUED','RUNNING')"):
        raise HTTPException(409,'请先停止当前运行后再修改或删除数据')

def safe_cell(value):
    text = str(value if value is not None else '')
    return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text

def export_file(data, fields, filename, fmt='csv'):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',' if fmt == 'csv' else '\t')
    writer.writerow(fields)
    for item in data:
        writer.writerow([safe_cell(item.get(f,'')) for f in fields])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv' if fmt == 'csv' else 'text/plain',headers={'Content-Disposition':f'attachment; filename="{filename}.{fmt}"'})

@router.get('/accounts')
def accounts():
    return rows("SELECT a.id,email,status,last_result,created_at,selected,COALESCE((SELECT CASE WHEN COUNT(*)=SUM(state='VALID') THEN 'VALID' ELSE 'EXPIRED' END FROM sessions WHERE account_id=a.id HAVING COUNT(*)>0),'NONE') AS session FROM accounts a ORDER BY a.id DESC")

@router.get('/cards')
def cards():
    return rows('SELECT id,masked,used,created_at,selected,use_count,last_used_at,last_result FROM cards ORDER BY id DESC')

@router.get('/accounts/export')
def account_export():
    return export_file(accounts(),['email','status','session','last_result','created_at'],'accounts')

@router.get('/cards/export')
def card_export():
    return export_file(cards(),['masked','used','created_at'],'safe-test-data')

class Selection(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=10000)
    all: bool = False
    confirmed: bool = False

class PoolSelection(BaseModel):
    ids: list[int] = Field(default_factory=list,max_length=10000)
    selected: bool
    all: bool = False

@router.post('/pools/{kind}/selection')
def select_resources(kind: str, body: PoolSelection):
    if kind not in ('accounts','cards','networks'): raise HTTPException(404)
    with connect() as db:
        if body.all: db.execute(f'UPDATE {kind} SET selected=?',(body.selected,))
        else: db.executemany(f'UPDATE {kind} SET selected=? WHERE id=?',[(body.selected,i) for i in body.ids])
    return {'ok':True}

@router.post('/networks/delete')
def delete_networks(body: Selection):
    result = delete_data('networks',body)
    # Direct always remains available as a selectable fallback, never silently used
    # when proxies are explicitly selected for a run.
    if not rows("SELECT id FROM networks WHERE protocol='Direct'"):
        execute("INSERT INTO networks(name,protocol,selected) SELECT 'Direct','Direct',NOT EXISTS(SELECT 1 FROM networks WHERE protocol!='Direct')")
    if not rows("SELECT 1 FROM networks WHERE protocol!='Direct'"):
        execute("UPDATE networks SET selected=1 WHERE protocol='Direct'")
    return result

@router.get('/networks/export')
def network_export():
    return export_file(networks(),['name','protocol','host','port','username','status','latency_ms'],'networks-safe')

def delete_data(kind: str, body: Selection):
    if kind not in ('accounts','cards','networks'):
        raise HTTPException(404,'类型不存在')
    busy()
    if not body.confirmed:
        raise HTTPException(400,'删除需要二次确认')
    with connect() as db:
        if body.all:
            db.execute(f'DELETE FROM {kind}')
        elif body.ids:
            db.executemany(f'DELETE FROM {kind} WHERE id=?', [(i,) for i in body.ids])
    return {'ok':True}

@router.post('/accounts/delete')
def delete_accounts(body: Selection):
    return delete_data('accounts',body)

@router.post('/cards/delete')
def delete_cards(body: Selection):
    return delete_data('cards',body)

@router.post('/accounts/{account_id}/clear-session')
def clear_session(account_id: int):
    busy()
    get_row('accounts',account_id)
    execute('DELETE FROM sessions WHERE account_id=?',(account_id,))
    execute("UPDATE accounts SET status='READY' WHERE id=?",(account_id,))
    return {'ok':True}

def valid_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('请输入不含用户名、密码或片段的完整 HTTP(S) URL')
    if parsed.query:
        raise ValueError('任务地址不接受查询参数；登录跳转由页面处理')
    return parsed

class Task(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    description: str = Field(default='',max_length=500)
    environment: str
    base_url: str
    login_url: str
    target_url: str
    enabled: bool = True
    authorized: bool = False

def validate_task(body):
    if body.environment not in ('Production','Sandbox','QA','Staging','Internal'):
        raise HTTPException(400,'环境类型错误')
    try:
        urls = [valid_url(x) for x in (body.base_url,body.login_url,body.target_url)]
        origins = {(u.scheme,u.netloc) for u in urls}
        if len(origins) != 1:
            raise ValueError('Base、Login 和 Target URL 必须属于同一站点')
        preply = any(u.hostname == 'preply.com' or u.hostname.endswith('.preply.com') for u in urls)
        if preply and body.environment != 'Production':
            raise ValueError('Preply 真实站点必须使用 Production UI 验证')
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    local = urls[0].hostname in ('127.0.0.1','localhost','sandbox')
    return 'preply_ui' if preply else 'generic_ui' if body.environment == 'Production' else 'sandbox' if local else 'contract_binding'

@router.get('/tasks')
def tasks():
    return rows('SELECT * FROM tasks ORDER BY id')

@router.post('/tasks')
def create_task(body: Task):
    adapter = validate_task(body)
    values = body.model_dump()
    values['adapter'] = adapter
    item_id = execute(f'INSERT INTO tasks({",".join(values)}) VALUES({",".join("?" for _ in values)})',tuple(values.values()))
    return get_row('tasks',item_id)

@router.put('/tasks/{task_id}')
def update_task(task_id: int, body: Task):
    busy()
    get_row('tasks',task_id)
    values = body.model_dump()
    values['adapter'] = validate_task(body)
    execute(f'UPDATE tasks SET {",".join(k+"=?" for k in values)},version=version+1 WHERE id=?',tuple(values.values())+(task_id,))
    execute("UPDATE sessions SET state='EXPIRED' WHERE task_id=?",(task_id,))
    return get_row('tasks',task_id)

class Network(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    protocol: str
    host: str = ''
    port: int = Field(default=8080,ge=1,le=65535)
    username: str = ''
    password: str = ''

@router.get('/networks')
def networks():
    return rows('SELECT id,name,protocol,host,port,username,selected,status,latency_ms,checked_at,reason FROM networks ORDER BY id')

class NetworkEdit(Network):
    # Omitted/null preserves the encrypted password; explicit empty string clears.
    password: str | None = None


def normalized_network(body, password):
    from backend.network_import import validate_network
    try:
        return validate_network(dict(body.model_dump(),password=password))
    except ValueError as exc:
        raise HTTPException(400,str(exc))


@router.post('/networks')
def create_network(body: Network):
    from backend.network_import import network_key, proxy_added
    item=normalized_network(body,body.password)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        items=[dict(r) for r in db.execute('SELECT * FROM networks')]
        duplicate=next((r for r in items if network_key(r)==network_key(item)),None)
        if duplicate: return {'id':duplicate['id'],'duplicate':True}
        item_id=db.execute('INSERT INTO networks(name,protocol,host,port,username,secret) VALUES(?,?,?,?,?,?)',(item['name'],item['protocol'],item['host'],item['port'],item['username'],seal(item['password']))).lastrowid
        proxy_added(db,any(n['protocol']!='Direct' for n in items))
    return {'id':item_id}


@router.put('/networks/{network_id}')
def edit_network(network_id: int, body: NetworkEdit):
    from backend.network_import import network_key
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM runs WHERE status IN ('QUEUED','RUNNING')").fetchone():
            raise HTTPException(409,'请先停止当前运行后再编辑节点')
        saved=db.execute('SELECT * FROM networks WHERE id=?',(network_id,)).fetchone()
        if not saved: raise HTTPException(404,'节点不存在')
        if saved['protocol']=='Direct': raise HTTPException(400,'Direct 无代理配置可编辑')
        password=unseal(saved['secret']) if body.password is None else body.password
        item=normalized_network(body,password)
        if any(network_key(dict(n))==network_key(item) for n in db.execute('SELECT * FROM networks WHERE id!=?',(network_id,))):
            raise HTTPException(409,'已有相同协议、Host、端口和用户名的节点')
        # Changing credentials invalidates readiness via the secret signature.
        # Existing immutable Run snapshots remain untouched.
        encrypted=saved['secret'] if body.password is None else seal(password)
        db.execute("UPDATE networks SET name=?,protocol=?,host=?,port=?,username=?,secret=?,status='UNKNOWN',latency_ms=NULL,checked_at=NULL,check_task_id=NULL,check_task_version=NULL,reason='' WHERE id=?",(item['name'],item['protocol'],item['host'],item['port'],item['username'],encrypted,network_id))
    return {'id':network_id}
