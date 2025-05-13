import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.base import Base
from src.models.call import Call
from src.models.transcript import Transcript
from src.models.booking import Booking
from src.models.langgraph_state import LangGraphState

config = context.config

fileConfig(config.config_file_name)

connectable = engine_from_config(
    config.get_section(config.config_ini_section),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)

with connectable.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
    )

    with context.begin_transaction():
        context.run_migrations()