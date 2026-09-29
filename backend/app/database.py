from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns(target_engine, metadata) -> list[str]:
    inspector = inspect(target_engine)
    tables = {name: {column["name"] for column in inspector.get_columns(name)} for name in inspector.get_table_names()}
    added = []
    with target_engine.begin() as connection:
        for table in metadata.tables.values():
            existing = tables.get(table.name)
            if existing is None:
                continue
            for column in table.columns:
                if column.name in existing:
                    continue
                column_type = column.type.compile(target_engine.dialect)
                if column.nullable or column.default is not None or column.server_default is not None:
                    connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
                else:
                    connection.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type} NOT NULL DEFAULT \'\'')
                    )
                added.append(f"{table.name}.{column.name}")
    return added
