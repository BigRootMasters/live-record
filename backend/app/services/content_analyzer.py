import logging
import os
import subprocess
import tempfile
from datetime import datetime

import requests
from dotenv import load_dotenv

from app.models import Recording, Summary, db

load_dotenv()

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Convert completed recordings into plain-text transcripts."""

    def __init__(self):
        self.transcript_storage_path = os.getenv('SUMMARY_STORAGE_PATH', './data/summaries')
        self.transcription_provider = os.getenv('TRANSCRIPTION_PROVIDER', 'mock').lower()
        self.cleanup_source_video = os.getenv('CLEANUP_VIDEO', 'True').lower() == 'true'
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_transcription_model = os.getenv('OPENAI_TRANSCRIPTION_MODEL', 'gpt-4o-mini-transcribe')
        self.openai_transcription_url = os.getenv('OPENAI_TRANSCRIPTION_URL', 'https://api.openai.com/v1/audio/transcriptions')
        self.audio_chunk_minutes = int(os.getenv('AUDIO_CHUNK_MINUTES', '10'))
        self.transcription_language = os.getenv('TRANSCRIPTION_LANGUAGE', 'zh')
        self.whisper_model = None

    def analyze_recording(self, recording_id):
        """Generate a transcript for a completed recording."""
        logger.info('Generating transcript for recording %s', recording_id)

        recording = Recording.query.filter_by(id=recording_id).first()
        if not recording:
            logger.error('Recording not found: %s', recording_id)
            return False

        if not recording.video_path or not os.path.exists(recording.video_path):
            logger.error('Video file not found: %s', recording.video_path)
            recording.status = 'transcription_failed'
            db.session.commit()
            return False

        summary = self._ensure_summary_record(recording_id)

        try:
            summary.status = 'processing'
            recording.status = 'transcribing'
            db.session.commit()

            audio_path = self._extract_audio(recording.video_path)
            if not audio_path:
                raise RuntimeError('audio extraction failed')

            transcript = self._transcribe_audio(audio_path, recording)
            if not transcript:
                raise RuntimeError('transcription failed')

            self._cleanup_audio(audio_path)
            self._save_transcript(summary, transcript)

            recording.status = 'transcribed'
            db.session.commit()

            if self.cleanup_source_video:
                self._cleanup_video(recording)

            logger.info('Transcript generated successfully for recording %s', recording_id)
            return True
        except Exception as exc:
            logger.error('Failed to generate transcript for recording %s: %s', recording_id, exc)
            db.session.rollback()
            summary = self._ensure_summary_record(recording_id)
            summary.status = 'failed'
            recording = Recording.query.filter_by(id=recording_id).first()
            if recording:
                recording.status = 'transcription_failed'
            db.session.commit()
            return False

    def _ensure_summary_record(self, recording_id):
        summary = Summary.query.filter_by(recording_id=recording_id).first()
        if summary:
            return summary

        summary = Summary(
            recording_id=recording_id,
            content='',
            core_points='',
            market_analysis='',
            investment_advice='',
            keywords='',
            status='pending'
        )
        db.session.add(summary)
        db.session.commit()
        return summary

    def _extract_audio(self, video_path):
        logger.info('Extracting audio from %s', video_path)
        os.makedirs(self.transcript_storage_path, exist_ok=True)
        audio_path = os.path.join(
            self.transcript_storage_path,
            f'{os.path.splitext(os.path.basename(video_path))[0]}.mp3'
        )

        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'mp3',
            '-ab', '64k',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            '-loglevel', 'error',
            audio_path
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )
        if result.returncode != 0:
            logger.error('FFmpeg audio extraction failed: %s', result.stderr)
            return None
        return audio_path

    def _transcribe_audio(self, audio_path, recording):
        logger.info(
            'Transcribing audio with provider=%s for recording %s',
            self.transcription_provider,
            recording.id
        )

        if self.transcription_provider == 'local':
            return self._transcribe_with_local_whisper(audio_path)

        if self.transcription_provider == 'openai':
            return self._transcribe_with_openai(audio_path)

        if self.transcription_provider == 'mock':
            return self._mock_transcribe(recording)

        logger.warning(
            'Provider %s is not implemented yet, falling back to mock transcript',
            self.transcription_provider
        )
        return self._mock_transcribe(recording)

    def _transcribe_with_local_whisper(self, audio_path):
        try:
            if self.whisper_model is None:
                import whisper

                model_size = os.getenv('WHISPER_MODEL_SIZE', 'base')
                logger.info('Loading Whisper model: %s', model_size)
                self.whisper_model = whisper.load_model(model_size)

            result = self.whisper_model.transcribe(audio_path, language='zh')
            return result.get('text', '').strip()
        except Exception as exc:
            logger.error('Local Whisper transcription failed: %s', exc)
            return None

    def _transcribe_with_openai(self, audio_path):
        if not self.openai_api_key:
            logger.error('OPENAI_API_KEY is missing, cannot use OpenAI transcription provider')
            return None

        chunk_paths = self._split_audio_into_chunks(audio_path)
        if not chunk_paths:
            return None

        transcripts = []
        try:
            for chunk_path in chunk_paths:
                transcript = self._request_openai_transcription(chunk_path)
                if not transcript:
                    return None
                transcripts.append(transcript.strip())
            return '\n'.join(part for part in transcripts if part)
        finally:
            self._cleanup_chunk_files(chunk_paths)

    def _split_audio_into_chunks(self, audio_path):
        chunk_duration = max(self.audio_chunk_minutes, 1) * 60
        chunk_paths = []

        with tempfile.TemporaryDirectory(prefix='transcribe_chunks_') as chunk_dir:
            output_pattern = os.path.join(chunk_dir, 'chunk_%03d.mp3')
            cmd = [
                'ffmpeg',
                '-i', audio_path,
                '-f', 'segment',
                '-segment_time', str(chunk_duration),
                '-c', 'copy',
                '-reset_timestamps', '1',
                '-loglevel', 'error',
                output_pattern
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False
            )
            if result.returncode != 0:
                logger.error('FFmpeg audio chunking failed: %s', result.stderr)
                return None

            for file_name in sorted(os.listdir(chunk_dir)):
                source_path = os.path.join(chunk_dir, file_name)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as target_file:
                    with open(source_path, 'rb') as source_file:
                        target_file.write(source_file.read())
                    chunk_paths.append(target_file.name)

        if not chunk_paths:
            logger.error('No audio chunks were generated for %s', audio_path)
            return None

        return chunk_paths

    def _request_openai_transcription(self, audio_path):
        headers = {
            'Authorization': f'Bearer {self.openai_api_key}'
        }
        data = {
            'model': self.openai_transcription_model,
            'response_format': 'text',
            'language': self.transcription_language,
        }

        with open(audio_path, 'rb') as audio_file:
            files = {
                'file': (os.path.basename(audio_path), audio_file, 'audio/mpeg')
            }
            response = requests.post(
                self.openai_transcription_url,
                headers=headers,
                data=data,
                files=files,
                timeout=300
            )

        if response.status_code != 200:
            logger.error('OpenAI transcription request failed: %s %s', response.status_code, response.text)
            return None

        return response.text.strip()

    def _cleanup_chunk_files(self, chunk_paths):
        for chunk_path in chunk_paths:
            if os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                except OSError as exc:
                    logger.warning('Failed to remove chunk file %s: %s', chunk_path, exc)

    def _save_transcript(self, summary, transcript):
        summary.content = transcript
        summary.core_points = ''
        summary.market_analysis = ''
        summary.investment_advice = ''
        summary.keywords = ''
        summary.status = 'completed'
        summary.updated_at = datetime.now()
        db.session.commit()

    def _cleanup_audio(self, audio_path):
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError as exc:
                logger.warning('Failed to remove audio file %s: %s', audio_path, exc)

    def _cleanup_video(self, recording):
        if recording.video_path and os.path.exists(recording.video_path):
            try:
                os.remove(recording.video_path)
                recording.video_path = None
                db.session.commit()
            except OSError as exc:
                logger.warning('Failed to remove video file %s: %s', recording.video_path, exc)

    def _mock_transcribe(self, recording):
        anchor_name = recording.anchor.name if recording.anchor else '主播'
        started_at = recording.start_time.strftime('%Y-%m-%d %H:%M') if recording.start_time else '未知时间'
        return (
            f'{anchor_name} 在 {started_at} 的直播文字稿示例。\n'
            '这里会保存完整转写结果，第一版先把录播处理链和微信送达链跑通。\n'
            '后续接入真实转写服务后，这里会替换成整场直播的原始文字稿。'
        )


content_analyzer = ContentAnalyzer()
