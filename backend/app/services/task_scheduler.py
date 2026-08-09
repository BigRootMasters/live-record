import logging
import os
import sqlite3
from datetime import datetime
from threading import Event, RLock, Thread

from dotenv import load_dotenv

from app.services.live_monitor import live_monitor
from app.services.notification_service import notification_service
from app.services.video_recorder import video_recorder
from app.models import Recording, db

load_dotenv()

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务服务"""

    def __init__(self):
        self.is_running = False
        self.threads = []
        self.flask_app = None
        self.stop_event = Event()
        self.stop_lock = RLock()
        self.backup_interval = int(os.getenv("BACKUP_INTERVAL", 86400))
        self.last_backup_time = None

    def start(self, flask_app=None):
        """启动定时任务服务"""
        if self.is_running:
            logger.info("Task scheduler service is already running")
            return

        logger.info("Starting task scheduler service")
        self.is_running = True
        self.flask_app = flask_app
        self.stop_event.clear()
        live_monitor.reset_stop_signal()

        self._recover_stale_recordings()

        monitor_thread = Thread(
            target=self._run_with_app_context,
            args=(self._run_live_monitor,),
            daemon=True,
        )
        monitor_thread.start()
        self.threads.append(monitor_thread)

        maintenance_thread = Thread(
            target=self._run_with_app_context,
            args=(self._run_maintenance_tasks,),
            daemon=True,
        )
        maintenance_thread.start()
        self.threads.append(maintenance_thread)

        logger.info("Task scheduler is running in record-only mode")
        logger.info("Task scheduler service started successfully")

    def stop(self):
        """停止定时任务服务"""
        with self.stop_lock:
            if not self.is_running:
                return

            logger.info("Stopping task scheduler service")
            self.is_running = False
            self.stop_event.set()
            live_monitor.stop_monitoring()

            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=15)
                if thread.is_alive():
                    logger.warning("Scheduler thread did not stop before timeout: %s", thread.name)

            self._finalize_active_recordings()
            self.threads = []
            logger.info("Task scheduler service stopped successfully")

    def _run_with_app_context(self, target):
        if self.flask_app is None:
            target()
            return

        with self.flask_app.app_context():
            target()

    def _run_live_monitor(self):
        logger.info("Starting live monitor task")
        live_monitor.start_monitoring()

    def _run_maintenance_tasks(self):
        logger.info("Starting maintenance tasks")

        while self.is_running:
            try:
                self._backup_database()
                self._cleanup_old_recordings()
                self.stop_event.wait(3600)
            except Exception as exc:
                logger.error("Error in maintenance tasks: %s", exc)
                self.stop_event.wait(3600)

    def _recover_stale_recordings(self):
        if self.flask_app is None:
            return

        try:
            with self.flask_app.app_context():
                stale_ids = [
                    recording.id
                    for recording in Recording.query.filter_by(status='recording').all()
                ]
                recovered = video_recorder.recover_stale_recordings()
                if recovered:
                    logger.info("Recovered %s stale recordings during scheduler startup", recovered)
                for recording_id in stale_ids:
                    recording = Recording.query.filter_by(id=recording_id).first()
                    if recording and recording.status == 'completed':
                        notification_service.send_recording_audio(recording.id)
        except Exception as exc:
            logger.error("Error recovering stale recordings on startup: %s", exc)

    def _finalize_active_recordings(self):
        if self.flask_app is None:
            return

        try:
            with self.flask_app.app_context():
                active_recordings = Recording.query.filter_by(status='recording').all()
                for recording in active_recordings:
                    logger.info(
                        "Finalizing active recording %s during scheduler shutdown",
                        recording.id,
                    )
                    live_monitor.stop_recording(recording)
        except Exception as exc:
            logger.error("Error finalizing active recordings during shutdown: %s", exc)

    def _backup_database(self):
        current_time = datetime.now()
        if (
            self.last_backup_time is not None
            and (current_time - self.last_backup_time).total_seconds() < self.backup_interval
        ):
            return

        logger.info("Running database backup")
        source_conn = None
        backup_conn = None
        try:
            database_url = os.getenv("DATABASE_URL", "sqlite:///./data.db")
            if not database_url.startswith("sqlite:///"):
                logger.info("Skipping database backup because DATABASE_URL is not SQLite")
                self.last_backup_time = current_time
                return

            backup_dir = os.path.join(os.getcwd(), "backups")
            os.makedirs(backup_dir, exist_ok=True)

            backup_filename = f"db_backup_{current_time.strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            db_path = self._resolve_sqlite_db_path(database_url)

            if not db_path or not os.path.exists(db_path):
                logger.warning("Database file not found: %s", db_path)
                return

            source_conn = sqlite3.connect(
                f"file:{db_path}?mode=ro",
                uri=True,
                timeout=30,
            )
            backup_conn = sqlite3.connect(backup_path, timeout=30)
            with backup_conn:
                source_conn.backup(backup_conn)
            logger.info("Database backed up to: %s", backup_path)
            self._cleanup_old_backups(backup_dir, 7)
            self.last_backup_time = current_time
        except Exception as exc:
            logger.error("Error backing up database: %s", exc)
        finally:
            if source_conn is not None:
                source_conn.close()
            if backup_conn is not None:
                backup_conn.close()

    def _resolve_sqlite_db_path(self, database_url=None):
        database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./data.db")
        if not database_url.startswith("sqlite:///"):
            return None

        try:
            engine_path = db.engine.url.database
            if engine_path and engine_path != ':memory:':
                return os.path.abspath(engine_path)
        except RuntimeError:
            # Allow the helper to be used outside an application context.
            pass

        db_path = database_url.replace("sqlite:///", "", 1)

        if os.path.isabs(db_path):
            return db_path

        base_path = self.flask_app.instance_path if self.flask_app else os.getcwd()
        return os.path.join(base_path, db_path)

    def _cleanup_old_backups(self, backup_dir, keep_count):
        try:
            backups = sorted(
                [name for name in os.listdir(backup_dir) if name.startswith("db_backup_")],
                key=lambda name: os.path.getmtime(os.path.join(backup_dir, name)),
            )

            if len(backups) <= keep_count:
                return

            for backup in backups[:-keep_count]:
                os.remove(os.path.join(backup_dir, backup))
                logger.info("Cleaned up old backup: %s", backup)
        except Exception as exc:
            logger.error("Error cleaning up old backups: %s", exc)

    def _cleanup_old_recordings(self):
        logger.info("Cleaning up old recordings")
        try:
            video_recorder.cleanup_old_recordings(
                days=video_recorder.recording_retention_days
            )
        except Exception as exc:
            logger.error("Error cleaning up old recordings: %s", exc)


task_scheduler = TaskScheduler()
