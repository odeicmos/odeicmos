"""Run explicit control-plane MongoDB index migration using migration credentials."""
import asyncio
from pymongo import AsyncMongoClient
from odei_api.config import get_settings
from odei_api.migrations.control_plane_indexes import apply_control_plane_indexes


async def _run() -> None:
    settings = get_settings()
    if not settings.mongodb_uri:
        raise RuntimeError("ODEI_MONGODB_URI must be injected for migrations")
    client = AsyncMongoClient(settings.mongodb_uri.get_secret_value(), appname="odei-migrations")
    try:
        await client.admin.command("ping")
        await apply_control_plane_indexes(client[settings.mongodb_database])
    finally:
        await client.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
