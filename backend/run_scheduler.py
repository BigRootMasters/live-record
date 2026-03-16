import signal
import time

from app import app as flask_app
from app.services.task_scheduler import task_scheduler


def main():
    def _shutdown(signum, frame):
        task_scheduler.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    task_scheduler.start(flask_app)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
