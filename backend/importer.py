"""Two-step import. No secrets in preview responses or error messages."""
import csv
import hashlib
import io
import re
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.auth import require_admin
from backend.store import rows, connect, execute, now, seal, unseal

router = APIRouter(prefix='/api/import', dependencies=[Depends(require_admin)])
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
from backend.tasks.data_contract import FIXTURES
from backend.network_import import network_key, network_line

def parse(text, kind, existing=()):
    seen = set(existing)
    valid, errors, duplicate = [], [], 0
    count = 0
    for number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.lower().replace(' ', '') in ('email,password','number,month,year,cvc','name,protocol,host,port,username,password'):
            continue
        count += 1
        if kind == 'networks':
            try:
                item = network_line(line)
                key = network_key(item)
            except (ValueError,csv.Error):
                errors.append({'line':number,'raw':'[节点凭据已隐藏]','reason':'节点格式错误：HTTP/SOCKS5 + Host + 1–65535 端口；SOCKS5 不支持用户名密码认证'})
                continue
            if key in seen: duplicate += 1
            else:
                seen.add(key)
                valid.append(item)
            continue
        try:
            parts = [p.strip() for p in (line.split('----',1) if kind == 'accounts' and '----' in line and '|' not in line else line.split('|') if '|' in line else next(csv.reader([line],strict=True)))]
        except csv.Error:
            errors.append({'line':number,'raw':'[原始内容仅保留在输入框]','reason':'CSV 引号未闭合或格式错误，无法确定字段'})
            continue
        error = None
        if kind == 'accounts':
            safe = parts[0][:254] if EMAIL.fullmatch(parts[0]) else '[邮箱格式错误；原始内容仅保留在输入框]'
            if len(parts) != 2 or not parts[1]:
                error = '需要邮箱和密码，支持 |、---- 或两列 CSV；缺少密码或列数错误'
            elif not EMAIL.fullmatch(parts[0]) or len(parts[0]) > 254:
                error = '邮箱格式错误'
            else:
                key = parts[0].lower()
                item = {'email':key,'password':parts[1]}
        else:
            safe = '[支付数据已遮罩；原始内容仅保留在输入框]'
            if len(parts) != 4:
                error = '需要四列：测试卡号 | 月份 | 四位年份 | CVC'
            else:
                pan = re.sub(r'[ -]', '', parts[0])
                if not re.fullmatch(r'\d{12,19}',pan):
                    error = '需要 12–19 位官方测试卡号；仅用于授权非 Production 环境'
                elif not parts[1].isdigit() or not 1 <= int(parts[1]) <= 12 or not re.fullmatch(r'\d{4}',parts[2]) or not re.fullmatch(r'\d{3,4}',parts[3]):
                    error = '月份、四位年份或 CVC 格式错误'
                elif (int(parts[2]),int(parts[1])) < (datetime.now().year,datetime.now().month):
                    error = '有效期已过期'
                else:
                    item = {'number':pan,'month':f'{int(parts[1]):02d}','year':parts[2],'cvc':parts[3]}
                    key = hashlib.sha256(f'{pan}|{item["month"]}|{item["year"]}'.encode()).hexdigest()
                    item.update(fingerprint=key,masked='**** **** **** '+pan[-4:])
        if error:
            errors.append({'line':number,'raw':safe,'reason':error})
        elif key in seen:
            duplicate += 1
        else:
            seen.add(key)
            valid.append(item)
    return {'total':count,'valid':len(valid),'duplicates':duplicate,'errors':errors}, valid

class Preview(BaseModel):
    kind: str
    text: str = Field(max_length=2_000_000)

@router.post('/preview')
def preview(body: Preview):
    if body.kind not in ('accounts','cards','networks'):
        raise HTTPException(400,'不支持的数据类型')
    column = 'email' if body.kind == 'accounts' else 'fingerprint'
    existing = [network_key(r) for r in rows('SELECT * FROM networks')] if body.kind == 'networks' else [r[column] for r in rows(f'SELECT {column} FROM {body.kind}')]
    summary, valid = parse(body.text,body.kind,existing)
    token = secrets.token_urlsafe(24)
    execute("DELETE FROM previews WHERE created_at < datetime('now','-1 day')")
    execute('INSERT INTO previews VALUES(?,?,?,?)',(token,body.kind,seal(valid),now()))
    return dict(summary,preview_id=token)

class Confirm(BaseModel):
    preview_id: str

@router.post('/confirm')
def confirm(body: Confirm):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        preview = db.execute('SELECT * FROM previews WHERE id=?',(body.preview_id,)).fetchone()
        if not preview or (datetime.now(timezone.utc)-datetime.fromisoformat(preview['created_at'])).total_seconds() > 1800:
            raise HTTPException(400,'预览已失效，请重新预览')
        added = 0
        for item in unseal(preview['secret']):
            if preview['kind'] == 'accounts':
                cursor = db.execute('INSERT OR IGNORE INTO accounts(email,secret,created_at) VALUES(?,?,?)',(item['email'],seal(item['password']),now()))
            elif preview['kind'] == 'cards':
                cursor = db.execute('INSERT OR IGNORE INTO cards(fingerprint,masked,secret,created_at) VALUES(?,?,?,?)',(item['fingerprint'],item['masked'],seal(item),now()))
            else:
                if network_key(item) in {network_key(dict(n)) for n in db.execute('SELECT * FROM networks')}: continue
                cursor = db.execute('INSERT INTO networks(name,protocol,host,port,username,secret) VALUES(?,?,?,?,?,?)',(item['name'],item['protocol'],item['host'],item['port'],item['username'],seal(item['password'])))
            added += cursor.rowcount
        db.execute('DELETE FROM previews WHERE id=?',(body.preview_id,))
    return {'imported':added}
