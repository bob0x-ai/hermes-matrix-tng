import asyncio

from mautrix.crypto.store.asyncpg import PgCryptoStore
from mautrix.util.async_db import Database


def test_two_real_mautrix_sqlite_databases_are_independent(tmp_path):
    first_path = tmp_path / "first" / "crypto.db"
    second_path = tmp_path / "second" / "crypto.db"
    first_path.parent.mkdir()
    second_path.parent.mkdir()

    async def exercise():
        first = Database.create(
            f"sqlite:///{first_path}", upgrade_table=PgCryptoStore.upgrade_table
        )
        second = Database.create(
            f"sqlite:///{second_path}", upgrade_table=PgCryptoStore.upgrade_table
        )
        await first.start()
        await second.start()
        try:
            await first.execute("CREATE TABLE IF NOT EXISTS tng_marker (value TEXT)")
            await second.execute("CREATE TABLE IF NOT EXISTS tng_marker (value TEXT)")
            await first.execute("INSERT INTO tng_marker (value) VALUES ('first')")
            await second.execute("INSERT INTO tng_marker (value) VALUES ('second')")
            first_row = await first.fetchrow("SELECT value FROM tng_marker")
            second_row = await second.fetchrow("SELECT value FROM tng_marker")
            assert first_row["value"] == "first"
            assert second_row["value"] == "second"
        finally:
            await first.stop()
            await second.stop()

    asyncio.run(exercise())
    assert first_path.exists()
    assert second_path.exists()
    assert first_path.read_bytes() != second_path.read_bytes()

