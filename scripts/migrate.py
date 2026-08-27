from pathlib import Path

import psycopg

from app.config import DATABASE_URL


def main() -> None:
    """Apply every idempotent SQL migration in lexical order."""
    migrations = sorted(Path("migrations").glob("*.sql"))
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration.read_text(encoding="utf-8"))
                print(f"Applied {migration}")


if __name__ == "__main__":
    main()
