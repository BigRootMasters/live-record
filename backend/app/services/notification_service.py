import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from dotenv import load_dotenv

from app.models import Recording
from app.utils.media_tools import get_ffmpeg_bin

load_dotenv()

logger = logging.getLogger(__name__)


class NotificationService:
    """Deliver recording audio notifications to WeCom."""

    def __init__(self):
        self.wechat_webhook_url = os.getenv('WECHAT_WEBHOOK_URL')
        self.wechat_timeout = int(os.getenv('WECHAT_TIMEOUT', 10))
        self.wechat_retries = int(os.getenv('WECHAT_RETRIES', 3))
        self.auto_send_recording_audio = os.getenv('AUTO_SEND_AUDIO_ON_RECORDING_COMPLETE', 'True').lower() == 'true'
        self.wechat_audio_bitrate = os.getenv('WECHAT_AUDIO_BITRATE', '16k')
        self.wechat_audio_sample_rate = int(os.getenv('WECHAT_AUDIO_SAMPLE_RATE', '16000'))
        self.wechat_audio_channels = int(os.getenv('WECHAT_AUDIO_CHANNELS', '1'))
        self.wechat_audio_max_mb = int(os.getenv('WECHAT_AUDIO_MAX_MB', '20'))
        self.ffmpeg_bin = get_ffmpeg_bin()

    def send_recording_audio(self, recording_id):
        if not self.auto_send_recording_audio:
            logger.info('Recording audio notification is disabled, skipping recording %s', recording_id)
            return False

        if not self.wechat_webhook_url:
            logger.warning('Wechat webhook URL not configured, skipping audio delivery for recording %s', recording_id)
            return False

        recording = Recording.query.filter_by(id=recording_id).first()
        if not recording:
            logger.error('Recording %s not found for audio delivery', recording_id)
            return False

        anchor = recording.anchor
        if not anchor:
            logger.error('Recording %s has no anchor, cannot send audio notification', recording_id)
            return False

        if not recording.video_path or not os.path.exists(recording.video_path):
            logger.error('Recording %s media file not found: %s', recording_id, recording.video_path)
            return False

        audio_path = None
        try:
            audio_path = self._extract_audio(recording)
            if not audio_path:
                return False

            file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
            if file_size_mb > self.wechat_audio_max_mb:
                logger.error(
                    'Audio file for recording %s is too large for Wechat robot upload: %.2f MB > %s MB',
                    recording_id,
                    file_size_mb,
                    self.wechat_audio_max_mb,
                )
                return False

            if not self._send_wechat_audio_intro(recording, file_size_mb):
                return False

            media_id = self._upload_wechat_file(audio_path)
            if not media_id:
                return False

            if not self._send_wechat_file(media_id):
                return False

            logger.info('Recording audio delivered successfully for recording %s', recording_id)
            return True
        except Exception as exc:
            logger.warning('Failed to send recording audio for %s: %s', recording_id, exc)
            return False
        finally:
            self._cleanup_temp_audio(audio_path)

    def _extract_audio(self, recording):
        logger.info('Extracting audio for Wechat delivery from %s', recording.video_path)
        temp_dir = tempfile.mkdtemp(prefix='wechat_audio_')
        audio_filename = self._build_audio_filename(recording)
        audio_path = os.path.join(temp_dir, audio_filename)

        cmd = [
            self.ffmpeg_bin,
            '-i', recording.video_path,
            '-vn',
            '-acodec', 'mp3',
            '-ab', self.wechat_audio_bitrate,
            '-ar', str(self.wechat_audio_sample_rate),
            '-ac', str(self.wechat_audio_channels),
            '-y',
            '-loglevel', 'error',
            audio_path,
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
        if result.returncode != 0:
            logger.error('FFmpeg audio extraction for Wechat failed: %s', result.stderr)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        return audio_path

    def _build_wechat_upload_url(self):
        parsed = urlparse(self.wechat_webhook_url or '')
        query = parse_qs(parsed.query)
        key = (query.get('key') or [None])[0]
        if not key:
            logger.error('Wechat webhook url does not contain a key: %s', self.wechat_webhook_url)
            return None

        upload_query = urlencode({'key': key, 'type': 'file'})
        upload_path = parsed.path.replace('/send', '/upload_media')
        return urlunparse((parsed.scheme, parsed.netloc, upload_path, '', upload_query, ''))

    def _upload_wechat_file(self, file_path):
        upload_url = self._build_wechat_upload_url()
        if not upload_url:
            return None

        for retry in range(self.wechat_retries):
            try:
                with open(file_path, 'rb') as file_obj:
                    response = requests.post(
                        upload_url,
                        files={'media': (os.path.basename(file_path), file_obj, 'audio/mpeg')},
                        timeout=self.wechat_timeout,
                    )
                response.raise_for_status()
                result = response.json()
                if result.get('errcode') == 0 and result.get('media_id'):
                    return result['media_id']
                logger.error('Wechat upload API error: %s', result.get('errmsg', 'Unknown error'))
            except Exception as exc:
                logger.warning(
                    'Failed to upload wechat audio file (%s/%s): %s',
                    retry + 1,
                    self.wechat_retries,
                    exc,
                )

            if retry < self.wechat_retries - 1:
                time.sleep(2)

        return None

    def _send_wechat_audio_intro(self, recording, file_size_mb):
        anchor = recording.anchor
        duration_text = f'{recording.video_duration} 秒' if recording.video_duration else '未知'
        end_time = recording.end_time.strftime('%Y-%m-%d %H:%M:%S') if recording.end_time else '未知'
        data = {
            'msgtype': 'markdown',
            'markdown': {
                'content': (
                    f"## {anchor.name} 录制已结束\n\n"
                    f"- 录制编号：{recording.id}\n"
                    f"- 结束时间：{end_time}\n"
                    f"- 录制时长：{duration_text}\n"
                    f"- 音频大小：约 {file_size_mb:.2f} MB\n\n"
                    '音频文件如下，请查收。'
                )
            }
        }
        return self._post_wechat_message(data)

    def _send_wechat_file(self, media_id):
        data = {
            'msgtype': 'file',
            'file': {
                'media_id': media_id
            }
        }
        return self._post_wechat_message(data)

    def _post_wechat_message(self, data):
        if not self.wechat_webhook_url:
            return False

        for retry in range(self.wechat_retries):
            try:
                response = requests.post(
                    self.wechat_webhook_url,
                    json=data,
                    timeout=self.wechat_timeout
                )
                response.raise_for_status()
                result = response.json()
                if result.get('errcode') == 0:
                    return True
                logger.error('Wechat API error: %s', result.get('errmsg', 'Unknown error'))
            except Exception as exc:
                logger.warning(
                    'Failed to send wechat notification (%s/%s): %s',
                    retry + 1,
                    self.wechat_retries,
                    exc
                )

            if retry < self.wechat_retries - 1:
                time.sleep(2)

        return False

    def _cleanup_temp_audio(self, audio_path):
        if not audio_path:
            return

        temp_dir = os.path.dirname(audio_path)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _build_audio_filename(self, recording):
        anchor_name = self._sanitize_filename_part(recording.anchor.name if recording.anchor else f'recording_{recording.id}')
        timestamp = (recording.end_time or recording.start_time or datetime.now()).strftime('%Y%m%d_%H%M%S')
        return f'{anchor_name}_{timestamp}.mp3'

    def _sanitize_filename_part(self, value):
        cleaned = re.sub(r'[\\\\/:*?\"<>|]+', '_', (value or '').strip())
        cleaned = re.sub(r'\\s+', '_', cleaned)
        return cleaned or 'recording'


notification_service = NotificationService()
