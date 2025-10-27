import os

from celery import Celery

from celery_apps import celery_config
from dotenv import load_dotenv

load_dotenv()


app = Celery(
    "notification_app",
    broker=os.getenv("REDIS_URL", "redis://localhost")
)

app.config_from_object(celery_config)

app.autodiscover_tasks()
