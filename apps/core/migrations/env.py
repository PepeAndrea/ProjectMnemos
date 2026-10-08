import os

from alembic import context
from mnemos.storage import Base
from sqlalchemy import create_engine

url = os.environ.get(
    "MNEMOS_DATABASE_URL", "postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos"
)
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
