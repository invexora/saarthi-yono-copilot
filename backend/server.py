import sys
from pathlib import Path

import uvicorn

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api import create_app
from backend.settings import Settings


def create_application():
    return create_app(Settings.from_env())


def run():
    settings = Settings.from_env()
    settings.validate()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    run()
