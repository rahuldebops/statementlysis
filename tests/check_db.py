from sqlalchemy import create_engine, text
from app.config import settings

e = create_engine(settings.DATABASE_URL_SYNC)
with e.connect() as c:
    r = c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'smtlysis' ORDER BY table_name"))
    tables = [row[0] for row in r]
    print(f"Tables in smtlysis ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")
