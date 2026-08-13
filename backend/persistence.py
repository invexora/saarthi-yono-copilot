from backend.database import DatabaseManager
from backend.postgres_database import PostgresDatabaseManager


def create_database(settings):
    if settings.database_url:
        return PostgresDatabaseManager(settings.database_url)
    return DatabaseManager(settings.db_path)
