"""Reusable selected resources and immutable run snapshots; preserves v0.1 data."""
from alembic import op
revision = '002'
down_revision = '001'

def upgrade():
    for table in ('accounts','cards','networks'):
        op.execute(f'ALTER TABLE {table} ADD COLUMN selected INTEGER NOT NULL DEFAULT 1')
    for name,definition in [('use_count','INTEGER NOT NULL DEFAULT 0'),('last_used_at','TEXT'),('last_result','TEXT')]:
        op.execute(f'ALTER TABLE cards ADD COLUMN {name} {definition}')
    op.execute('UPDATE cards SET use_count=used')
    # Previously used data requires an explicit new selection; newly imported defaults on.
    op.execute('UPDATE cards SET selected=0 WHERE used=1')
    for name,definition in [('status',"TEXT NOT NULL DEFAULT 'UNKNOWN'"),('latency_ms','INTEGER'),('checked_at','TEXT'),('check_task_id','INTEGER'),('check_task_version','INTEGER'),('reason',"TEXT NOT NULL DEFAULT ''")]:
        op.execute(f'ALTER TABLE networks ADD COLUMN {name} {definition}')
    op.execute("ALTER TABLE runs ADD COLUMN resources_snapshot TEXT")
    for name,definition in [('network_id','INTEGER'),('network_name',"TEXT NOT NULL DEFAULT ''"),('task_id','INTEGER'),('task_version','INTEGER'),('reason',"TEXT NOT NULL DEFAULT ''"),('final_url',"TEXT NOT NULL DEFAULT ''")]:
        op.execute(f'ALTER TABLE results ADD COLUMN {name} {definition}')
    op.execute('CREATE UNIQUE INDEX one_data_per_run ON results(run_id,card_id) WHERE card_id IS NOT NULL')

def downgrade():
    raise RuntimeError('Restore the pre-upgrade backup to downgrade safely')
