import csv
import io
import json
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from backend.auth import require_admin
from backend.store import rows, execute, connect, seal

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
    return rows("SELECT a.id,email,status,last_result,created_at,COALESCE((SELECT CASE WHEN COUNT(*)=SUM(state='VALID') THEN 'VALID' ELSE 'EXPIRED' END FROM sessions WHERE account_id=a.id HAVING COUNT(*)>0),'NONE') AS session FROM accounts a ORDER BY a.id DESC")

@router.get('/cards')
def cards():
    return rows('SELECT id,masked,used,created_at FROM cards ORDER BY id DESC')

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

@router.post('/{kind}/delete')
def delete_data(kind: str, body: Selection):
    if kind not in ('accounts','cards'):
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

@router.post('/accounts/{account_id}/clear-session')
def clear_session(account_id: int):
    busy()
    get_row('accounts',account_id)
    execute('DELETE FROM sessions WHERE account_id=?',(account_id,))
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
    return 'preply_ui' if preply else 'generic_ui' if body.environment == 'Production' else 'sandbox'

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
    return rows('SELECT id,name,protocol,host,port,username FROM networks ORDER BY id')

@router.post('/networks')
def create_network(body: Network):
    if body.protocol not in ('HTTP','SOCKS5') or not body.host or any(c in body.host for c in '/@:#? '):
        raise HTTPException(400,'协议需为 HTTP/SOCKS5，Host 需为 IP 或域名')
    if body.protocol == 'SOCKS5' and (body.username or body.password):
        raise HTTPException(400,'Chromium 不支持 SOCKS5 用户名密码认证；请选择 HTTP 或无认证 SOCKS5')
    item_id = execute('INSERT INTO networks(name,protocol,host,port,username,secret) VALUES(?,?,?,?,?,?)',(body.name,body.protocol,body.host,body.port,body.username,seal(body.password)))
    return {'id':item_id}
