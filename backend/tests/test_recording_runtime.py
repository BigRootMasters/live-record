import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


TEST_ROOT = tempfile.TemporaryDirectory(prefix='live_record_tests_')
TEST_PATH = Path(TEST_ROOT.name)
ANCHOR_CONFIG_PATH = TEST_PATH / 'anchors.json'
ANCHOR_CONFIG_PATH.write_text('[]', encoding='utf-8')

os.environ['DATABASE_URL'] = f'sqlite:///{TEST_PATH / "data.db"}'
os.environ['ANCHOR_CONFIG_PATH'] = str(ANCHOR_CONFIG_PATH)
os.environ['LOG_FILE'] = str(TEST_PATH / 'app.log')
os.environ['WECHAT_WEBHOOK_URL'] = ''
os.environ['AUTO_SEND_AUDIO_ON_RECORDING_COMPLETE'] = 'False'

from app import app
from app.models import Anchor, Recording, db
from app.services.douyin_live_resolver import DouyinLiveResolver
from app.services.live_monitor import LiveMonitor
from app.services.task_scheduler import TaskScheduler
from app.services.video_recorder import VideoRecorder, video_recorder


class RuntimeLogicTestCase(unittest.TestCase):
    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()

    def _create_recording(self, media_path, status='recording'):
        with app.app_context():
            anchor = Anchor(
                name='test-anchor',
                douyin_id='test-douyin-id',
                is_followed=True,
            )
            db.session.add(anchor)
            db.session.flush()
            recording = Recording(
                anchor_id=anchor.id,
                video_path=str(media_path),
                start_time=datetime.now(),
                status=status,
            )
            db.session.add(recording)
            db.session.commit()
            return recording.id

    def test_live_room_without_streams_is_offline(self):
        resolver = DouyinLiveResolver()
        page_html = '<html><title>anchor live room</title></html>'

        with patch.object(resolver, '_fetch_page', return_value=page_html):
            result = resolver.resolve('https://live.douyin.com/test-anchor')

        self.assertIsNotNone(result)
        self.assertEqual(result['status'], 'offline')
        self.assertIsNone(result['flv_url'])
        self.assertIsNone(result['hls_url'])

    def test_profile_page_without_streams_remains_resolution_error(self):
        resolver = DouyinLiveResolver()

        with patch.object(resolver, '_fetch_page', return_value='<html></html>'):
            result = resolver.resolve('https://www.douyin.com/user/test-anchor')

        self.assertIsNone(result)

    def test_backup_uses_flask_resolved_sqlite_path_and_runs_immediately(self):
        scheduler = TaskScheduler()
        scheduler.flask_app = app

        with app.app_context():
            expected_db_path = os.path.abspath(db.engine.url.database)
            self.assertEqual(scheduler._resolve_sqlite_db_path(), expected_db_path)

            with patch(
                'app.services.task_scheduler.os.getcwd',
                return_value=str(TEST_PATH),
            ):
                scheduler._backup_database()

        backups = list((TEST_PATH / 'backups').glob('db_backup_*.db'))
        self.assertEqual(len(backups), 1)
        self.assertIsNotNone(scheduler.last_backup_time)

    def test_startup_recovery_sends_completed_recording(self):
        media_path = TEST_PATH / 'recovered.mp3'
        media_path.write_bytes(b'recovered recording')
        recording_id = self._create_recording(media_path)
        scheduler = TaskScheduler()
        scheduler.flask_app = app

        with patch.object(
            video_recorder,
            'get_recording_status',
            return_value=False,
        ):
            duration_patch = patch.object(
                video_recorder,
                'get_video_duration',
                return_value=30,
            )
            notification_patch = patch(
                'app.services.task_scheduler.notification_service.send_recording_audio',
                return_value=True,
            )
            with duration_patch, notification_patch as send_audio:
                scheduler._recover_stale_recordings()

        with app.app_context():
            recording = db.session.get(Recording, recording_id)
            self.assertEqual(recording.status, 'completed')
            self.assertEqual(recording.video_duration, 30)
        send_audio.assert_called_once_with(recording_id)

    def test_shutdown_finalizes_every_active_recording(self):
        recording_id = self._create_recording(TEST_PATH / 'active.mp3')
        scheduler = TaskScheduler()
        scheduler.flask_app = app

        with patch(
            'app.services.task_scheduler.live_monitor.stop_recording',
            return_value={'stopped': True, 'processed': True, 'audio_sent': True},
        ) as stop_recording:
            scheduler._finalize_active_recordings()

        self.assertEqual(stop_recording.call_count, 1)
        self.assertEqual(stop_recording.call_args.args[0].id, recording_id)

    def test_recovered_live_chunk_is_sent_before_next_chunk(self):
        recording_id = self._create_recording(TEST_PATH / 'chunk.mp3', status='completed')
        monitor = LiveMonitor()

        notification_patch = patch(
            'app.services.live_monitor.notification_service.send_recording_audio',
            return_value=True,
        )
        with app.app_context():
            with notification_patch as send_audio:
                recording = db.session.get(Recording, recording_id)
                self.assertTrue(monitor._notify_recovered_recording(recording))

        send_audio.assert_called_once_with(recording_id)

    def test_ffmpeg_stderr_does_not_block_recording_process(self):
        recorder = VideoRecorder()
        recorder.startup_check_seconds = 0.1
        output_path = TEST_PATH / 'recordings' / 'pipe-test.mp3'
        command = [
            sys.executable,
            '-c',
            (
                'import sys; '
                'sys.stderr.write("x" * 200000); '
                'sys.stderr.flush(); '
                'sys.stdin.readline()'
            ),
        ]

        with patch.object(recorder, '_build_recording_command', return_value=command):
            self.assertTrue(
                recorder.start_recording('pipe-test', 'https://example.com/stream', str(output_path))
            )
            self.assertTrue(recorder.stop_recording('pipe-test'))

        self.assertNotIn('pipe-test', recorder.recording_processes)
        self.assertNotIn('pipe-test', recorder.recording_stderr_files)

    def test_naturally_finished_process_releases_temp_resources(self):
        recorder = VideoRecorder()
        recorder.startup_check_seconds = 0.05
        output_path = TEST_PATH / 'recordings' / 'natural-exit.mp3'
        command = [sys.executable, '-c', 'import time; time.sleep(0.1)']

        with patch.object(recorder, '_build_recording_command', return_value=command):
            self.assertTrue(
                recorder.start_recording(
                    'natural-exit',
                    'https://example.com/stream',
                    str(output_path),
                )
            )

        time.sleep(0.1)
        self.assertFalse(recorder.get_recording_status('natural-exit'))
        self.assertNotIn('natural-exit', recorder.recording_processes)
        self.assertNotIn('natural-exit', recorder.recording_stderr_files)


if __name__ == '__main__':
    unittest.main()
