from celery import Celery
from celery.schedules import crontab
from celery_apps.utils import delete_expired_activation_tokens
from celery_apps import notification_app as app


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(
        crontab(hour="*/24"),
        delete_expired_activation_tokens()
    )
