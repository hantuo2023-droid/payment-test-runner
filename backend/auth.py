import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException, Request
from backend.store import rows, execute

TOKENS = {}
ATTEMPTS = {}

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()

def initialize(password):
    if len(password) < 12:
        raise ValueError('管理员密码至少 12 位')
    execute('INSERT INTO settings(key,value) VALUES(?,?)', ('admin_password', password_hash(password)))

def login(password, ip):
    attempts = [t for t in ATTEMPTS.get(ip, []) if time.time()-t < 300]
    ATTEMPTS[ip] = attempts
    if len(attempts) >= 10:
        raise HTTPException(429, '尝试过多，请 5 分钟后重试')
    existing = rows("SELECT value FROM settings WHERE key='admin_password'")
    if not existing:
        raise HTTPException(503, '请先通过终端初始化管理员')
    stored = existing[0]['value']
    if not hmac.compare_digest(stored, password_hash(password, stored.split(':')[0])):
        attempts.append(time.time())
        raise HTTPException(401, '管理员密码错误')
    token = secrets.token_urlsafe(32)
    TOKENS[token] = time.time()+28800
    ATTEMPTS.pop(ip, None)
    return token

def require_admin(request: Request):
    if request.method not in ('GET', 'HEAD') and request.headers.get('X-PTR-Client') != 'web':
        raise HTTPException(403, '缺少请求保护标记')
    token = request.cookies.get('ptr_session', '')
    if TOKENS.get(token, 0) < time.time():
        TOKENS.pop(token, None)
        raise HTTPException(401, '请登录管理员')
