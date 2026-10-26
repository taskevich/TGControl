import logging

from app.container import build_container
from app.infrastructure.config import settings
from app.presentation.http.app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("telethon").setLevel(logging.WARNING)

app = create_app(build_container(settings))
