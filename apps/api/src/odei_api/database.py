"""MongoDB access helpers. Collections are provisioned by versioned migrations."""

from pymongo.asynchronous.database import AsyncDatabase


def get_database(database: AsyncDatabase | None) -> AsyncDatabase:
    if database is None:
        raise RuntimeError("MongoDB is not available in this application context")
    return database
