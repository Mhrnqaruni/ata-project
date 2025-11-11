# /ata-backend/alembic/env.py (MODIFIED AND APPROVED)

import os
import sys
from logging.config import fileConfig

# --- [CRITICAL MODIFICATION FOR .env LOADING] ---
# Import the load_dotenv function from the dotenv library.
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- [CRITICAL MODIFICATION FOR .env LOADING] ---
# Explicitly load the .env file from the project's root directory.
# This ensures that the DATABASE_URL is available when Alembic runs.
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


# --- [CONFIGURATION - PART 1: MODEL PATH] ---
# This is the first critical piece. We add our project's 'app' directory
# to the Python path so Alembic can find our models.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

# Now we can import our Base from our application's code.
from app.db.base import Base

# --- [END OF PART 1] ---


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# --- [CONFIGURATION - PART 2: DATABASE URL] ---
# This is the second critical piece. We get the DATABASE_URL from the
# environment and inject it into the Alembic config.
# This will now work because we loaded the .env file above.
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable not set.")

config.set_main_option("sqlalchemy.url", database_url)
# --- [END OF PART 2] ---


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- [CONFIGURATION - PART 3: TARGET METADATA] ---
# This is the third critical piece. We tell Alembic that our models' metadata
# is the target for the 'autogenerate' process.
target_metadata = Base.metadata
# --- [END OF PART 3] ---


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    (The rest of this file is the standard Alembic template and is correct)
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()