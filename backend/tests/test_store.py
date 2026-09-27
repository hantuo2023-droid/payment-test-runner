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
