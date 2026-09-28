"""SQLite persistence; secrets stay encrypted, browser sessions scoped to task."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from cryptography.fernet import Fernet

DATA = Path(os.environ.get('PTR_DATA', 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'runner.db'

def now():
    return datetime.now(timezone.utc).isoformat()

def cipher():
    key = os.environ.get('PTR_SECRET')
    if not key:
        path = DATA / 'secret.key'
        if not path.exists():
            with path.open('xb') as f:
                f.write(Fernet.generate_key())
            path.chmod(0o600)
        key = path.read_text().strip()
    return Fernet(key.encode())

def seal(value):
    return cipher().encrypt(json.dumps(value).encode()).decode()

def unseal(value):
    return json.loads(cipher().decrypt(value.encode()))

@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

def rows(sql, params=()):
    with connect() as db:
        return [dict(x) for x in db.execute(sql, params)]

def execute(sql, params=()):
    with connect() as db:
        return db.execute(sql, params).lastrowid

SCHEMA = '''
CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE accounts(id INTEGER PRIMARY KEY,email TEXT UNIQUE COLLATE NOCASE NOT NULL,secret TEXT NOT NULL,status TEXT DEFAULT 'READY',last_result TEXT,created_at TEXT NOT NULL);
CREATE TABLE cards(id INTEGER PRIMARY KEY,fingerprint TEXT UNIQUE NOT NULL,masked TEXT NOT NULL,secret TEXT NOT NULL,used INTEGER DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE tasks(id INTEGER PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL,environment TEXT NOT NULL,base_url TEXT NOT NULL,login_url TEXT NOT NULL,target_url TEXT NOT NULL,enabled INTEGER NOT NULL,adapter TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,authorized INTEGER NOT NULL DEFAULT 0);
CREATE TABLE networks(id INTEGER PRIMARY KEY,name TEXT NOT NULL,protocol TEXT NOT NULL,host TEXT,port INTEGER,username TEXT,secret TEXT);
CREATE TABLE sessions(account_id INTEGER REFERENCES accounts ON DELETE CASCADE,task_id INTEGER REFERENCES tasks ON DELETE CASCADE,version INTEGER,state TEXT NOT NULL,secret TEXT,PRIMARY KEY(account_id,task_id));
CREATE TABLE previews(id TEXT PRIMARY KEY,kind TEXT NOT NULL,secret TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE runs(id INTEGER PRIMARY KEY,task_id INTEGER,task_version INTEGER,task_snapshot TEXT NOT NULL,network_snapshot TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT,stop INTEGER NOT NULL DEFAULT 0);
CREATE TABLE results(id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL REFERENCES runs ON DELETE CASCADE,account_id INTEGER,card_id INTEGER,email TEXT NOT NULL,masked TEXT NOT NULL,status TEXT NOT NULL,code TEXT NOT NULL DEFAULT '',step TEXT NOT NULL DEFAULT 'QUEUED',started_at TEXT,ended_at TEXT,duration REAL DEFAULT 0);
CREATE INDEX results_run ON results(run_id);
'''

def seed():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        if not db.execute('SELECT 1 FROM tasks LIMIT 1').fetchone():
            sandbox = os.environ.get('PTR_SANDBOX_URL', 'http://127.0.0.1:8080')
            db.executemany('INSERT INTO tasks(name,description,environment,base_url,login_url,target_url,enabled,adapter,authorized) VALUES(?,?,?,?,?,?,?,?,?)', [
                ('Local Sandbox Binding', '受控本地站点：真实填写、提交并解析结果', 'Sandbox',sandbox,sandbox+'/login',sandbox+'/settings/payments',1,'sandbox',1),
                ('Preply Payment UI', '仅登录、导航和 Add Card 界面验证；不会填写或提交卡片', 'Production','https://preply.com','https://preply.com/en/login','https://preply.com/en/settings/payments',1,'preply_ui',0),
            ])
        if not db.execute("SELECT 1 FROM networks WHERE protocol='Direct'").fetchone():
            db.execute("INSERT INTO networks(name,protocol,selected) SELECT 'Direct','Direct',NOT EXISTS(SELECT 1 FROM networks WHERE protocol!='Direct')")

def migrate():
    from alembic.config import Config
    from alembic import command
    cfg = Config(str(Path(__file__).parent / 'alembic.ini'))
    cfg.set_main_option('script_location', str(Path(__file__).parent / 'migrations'))
    command.upgrade(cfg, 'head')
    seed()
    cipher()  # Validate or create the encryption key before accepting requests.
