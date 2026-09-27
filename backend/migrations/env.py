from alembic import context
from sqlalchemy import create_engine
from backend.store import DB

engine = create_engine('sqlite:///' + str(DB))
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
