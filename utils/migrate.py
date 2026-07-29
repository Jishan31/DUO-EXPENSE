"""
A tiny, dependency-free schema upgrader. Real projects should use
Flask-Migrate/Alembic — this exists only so people who ran Phase 1 can pull
Phase 2 without deleting their database. It compares each model's declared
columns against what's actually in SQLite and ALTERs the table to add any
that are missing (SQLite can't drop/rename this way, but ADD COLUMN is safe).
"""
from sqlalchemy import inspect, text


def upgrade_schema(app, db):
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # brand-new table — db.create_all() already handles this
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                col_type = column.type.compile(db.engine.dialect)
                default_clause = ""
                if column.default is not None and column.default.is_scalar:
                    val = column.default.arg
                    if isinstance(val, str):
                        default_clause = f" DEFAULT '{val}'"
                    elif isinstance(val, bool):
                        default_clause = f" DEFAULT {int(val)}"
                    elif isinstance(val, (int, float)):
                        default_clause = f" DEFAULT {val}"
                with db.engine.begin() as conn:
                    conn.execute(text(
                        f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_clause}'
                    ))
                print(f"[migrate] added column {table.name}.{column.name}")
