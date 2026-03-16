import logging
import os
import time
from datetime import datetime
from threading import Thread

from dotenv import load_dotenv

from app.models import Recording, Summary
from app.services.content_analyzer import content_analyzer
from app.services.live_monitor import live_monitor
from app.services.notification_service import notification_service
from app.services.video_recorder import video_recorder

load_dotenv()

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务服务"""

    def __init__(self):
        self.is_running = False
        self.threads = []
        self.flask_app = None
        self.summary_send_time = os.getenv("SUMMARY_SEND_TIME", "08:00")
        self.backup_interval = int(os.getenv("BACKUP_INTERVAL", 86400))
        self.last_backup_time = datetime.now()

    def start(self, flask_app=None):
        """启动定时任务服务"""
        if self.is_running:
            logger.info("Task scheduler service is already running")
            return

        logger.info("Starting task scheduler service")
        self.is_running = True
        self.flask_app = flask_app

        monitor_thread = Thread(
            target=self._run_with_app_context,
            args=(self._run_live_monitor,),
            daemon=True,
        )
        monitor_thread.start()
        self.threads.append(monitor_thread)

        analyzer_thread = Thread(
            target=self._run_with_app_context,
            args=(self._run_content_analyzer,),
            daemon=True,
        )
        analyzer_thread.start()
        self.threads.append(analyzer_thread)

        notification_thread = Thread(
            target=self._run_with_app_context,
            args=(self._run_notification_service,),
            daemon=True,
        )
        notification_thread.start()
        self.threads.append(notification_thread)

        maintenance_thread = Thread(
            target=self._run_with_app_context,
            args=(self._run_maintenance_tasks,),
            daemon=True,
        )
        maintenance_thread.start()
        self.threads.append(maintenance_thread)

        logger.info("Task scheduler service started successfully")

    def stop(self):
        """停止定时任务服务"""
        logger.info("Stopping task scheduler service")
        self.is_running = False
        live_monitor.stop_monitoring()

        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=10)

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

    def _run_content_analyzer(self):
        logger.info("Starting content analyzer task")

        while self.is_running:
            try:
                self._analyze_pending_recordings()
                time.sleep(300)
            except Exception as exc:
                logger.error("Error in content analyzer task: %s", exc)
                time.sleep(300)

    def _run_notification_service(self):
        logger.info("Starting notification service task")

        while self.is_running:
            try:
                current_time = datetime.now().strftime("%H:%M")
                if current_time == self.summary_send_time:
                    notification_service.send_daily_summary()
                    time.sleep(60)
                else:
                    time.sleep(60)
            except Exception as exc:
                logger.error("Error in notification service task: %s", exc)
                time.sleep(60)

    def _run_maintenance_tasks(self):
        logger.info("Starting maintenance tasks")

        while self.is_running:
            try:
                self._backup_database()
                self._cleanup_old_recordings()
                time.sleep(3600)
            except Exception as exc:
                logger.error("Error in maintenance tasks: %s", exc)
                time.sleep(3600)

    def _analyze_pending_recordings(self):
        logger.info("Checking for completed recordings that need transcription")

        try:
            pending_recordings = (
                Recording.query.filter_by(status="completed")
                .outerjoin(Summary)
                .filter(Summary.id == None)
                .all()
            )

            logger.info(
                "Found %s recordings waiting for transcription",
                len(pending_recordings),
            )

            for recording in pending_recordings:
                try:
                    success = content_analyzer.analyze_recording(recording.id)
                    if success:
                        logger.info(
                            "Transcribed recording %s successfully",
                            recording.id,
                        )
                        video_recorder.cleanup_recording(recording.id)
                    else:
                        logger.error(
                            "Failed to transcribe recording %s",
                            recording.id,
                        )
                except Exception as exc:
                    logger.error(
                        "Error transcribing recording %s: %s",
                        recording.id,
                        exc,
                    )

                time.sleep(5)
        except Exception as exc:
            logger.error("Error checking pending recordings: %s", exc)

    def _backup_database(self):
        current_time = datetime.now()
        if (current_time - self.last_backup_time).total_seconds() < self.backup_interval:
            return

        logger.info("Running database backup")
        try:
            backup_dir = os.path.join(os.getcwd(), "backups")
            os.makedirs(backup_dir, exist_ok=True)

            backup_filename = f"db_backup_{current_time.strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            db_path = self._resolve_sqlite_db_path()

            if not os.path.exists(db_path):
                logger.warning("Database file not found: %s", db_path)
                return

            import shutil

            shutil.copy2(db_path, backup_path)
            logger.info("Database backed up to: %s", backup_path)
            self._cleanup_old_backups(backup_dir, 7)
            self.last_backup_time = current_time
        except Exception as exc:
            logger.error("Error backing up database: %s", exc)

    def _resolve_sqlite_db_path(self):
        database_url = os.getenv("DATABASE_URL", "sqlite:///./data.db")
        if not database_url.startswith("sqlite:///"):
            return os.path.join(os.getcwd(), "instance", "data.db")

        db_path = database_url.replace("sqlite:///", "", 1)
        if database_url.startswith("sqlite:////"):
            db_path = f"/{db_path}"

        if os.path.isabs(db_path):
            return db_path

        return os.path.join(os.getcwd(), db_path)

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
            video_recorder.cleanup_old_recordings(days=7)
        except Exception as exc:
            logger.error("Error cleaning up old recordings: %s", exc)


task_scheduler = TaskScheduler()
