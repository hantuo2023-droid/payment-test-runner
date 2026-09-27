import os
from pathlib import Path
os.environ['PTR_DATA'] = str(Path('test-output/unit').resolve())
from backend.store import migrate, rows, seal, unseal
from backend.auth import password_hash

def test_migration_and_secret():
    migrate()
    migrate()
    assert len(rows('SELECT * FROM tasks')) == 2
    encrypted = seal({'password':'not-plaintext'})
    assert 'not-plaintext' not in encrypted
    assert unseal(encrypted)['password'] == 'not-plaintext'
    hashed = password_hash('long-password')
    assert hashed == password_hash('long-password', hashed.split(':')[0])


def test_upgrade_preserves_v01_resources(monkeypatch):
    import uuid
    tmp_path=Path("test-output")/("migration-"+uuid.uuid4().hex)
    tmp_path.mkdir(parents=True)
    from alembic.config import Config
    from alembic import command
    from backend import store
    monkeypatch.setattr(store,'DB',tmp_path/'upgrade.db')
    cfg=Config(str(Path('backend/alembic.ini').resolve()))
    cfg.set_main_option('script_location',str(Path('backend/migrations').resolve()))
    command.upgrade(cfg,'001')
    secret=seal('old-encrypted-secret')
    with store.connect() as db:
        db.execute("INSERT INTO accounts(email,secret,created_at) VALUES(?,?,?)",('legacy@example.com',secret,'2026-01-01'))
        db.execute("INSERT INTO cards(fingerprint,masked,secret,used,created_at) VALUES(?,?,?,1,?)",('legacy-fingerprint','****4242',secret,'2026-01-01'))
    store.migrate()
    account=store.rows('SELECT * FROM accounts')[0]
    card=store.rows('SELECT * FROM cards')[0]
    assert account['secret']==secret and account['selected']==1
    assert card['secret']==secret and card['use_count']==1 and card['selected']==0
    assert store.rows('SELECT version_num FROM alembic_version')[0]['version_num']=='002'
