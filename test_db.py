
import asyncio
from app.db.session import async_engine
from sqlalchemy import text

async def test_conn():
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("Successfully connected to the database!")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_conn())
