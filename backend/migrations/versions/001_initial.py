"""Initial schema."""
from alembic import op
from backend.store import SCHEMA
revision = '001'
down_revision = None

def upgrade():
    for statement in SCHEMA.split(';'):
        if statement.strip():
            op.execute(statement)

def downgrade():
    for name in ['results','runs','previews','sessions','networks','tasks','cards','accounts','settings']:
        op.drop_table(name)
