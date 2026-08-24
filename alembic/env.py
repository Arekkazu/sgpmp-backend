"""Configuración de entorno de Alembic.

target_metadata apunta a la única Base declarativa compartida
(src.shared.base_model.Base). Se importan todos los modelos ORM de cada
módulo dinámicamente (en vez de listarlos a mano) para que su metadata
quede registrada antes de correr una migración.

Nota: el módulo `prediction` declara su propia `DeclarativeBase` separada
(src/prediction/infrastructure/models/base_model.py) en vez de reexportar
la compartida — inconsistencia preexistente, no introducida por esta
migración. Sus tablas no aparecen en target_metadata; no afecta a las
migraciones escritas a mano (no autogenerate), pero un futuro
`--autogenerate` no las va a detectar hasta que se corrija.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv()
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"


def _import_all_models() -> None:
    for module_dir in sorted(SRC_ROOT.iterdir()):
        models_pkg = module_dir / "infrastructure" / "models"
        if not models_pkg.is_dir():
            continue
        package_name = f"src.{module_dir.name}.infrastructure.models"
        for _, mod_name, _ in pkgutil.iter_modules([str(models_pkg)]):
            importlib.import_module(f"{package_name}.{mod_name}")


_import_all_models()

from src.shared.base_model import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
