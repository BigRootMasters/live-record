import os
import signal
import subprocess
import time
import logging
from datetime import datetime, timedelta
from app.models import db, Recording
from app.utils.media_tools import get_ffmpeg_bin, get_ffprobe_bin
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class VideoRecorder:
    """视频录制服务"""
    
    def __init__(self):
        self.recording_quality = os.getenv('RECORDING_QUALITY', '720p')
        self.recording_mode = (os.getenv('RECORDING_MODE', 'video') or 'video').strip().lower()
        self.recording_processes = {}
        self.max_recording_duration = int(os.getenv('MAX_RECORDING_DURATION', 9000))  # 最大录制时长
        self.cleanup_video = os.getenv('CLEANUP_VIDEO', 'True').lower() == 'true'  # 是否清理视频文件
        self.recording_retention_days = int(os.getenv('RECORDING_RETENTION_DAYS', 7))
        self.audio_recording_bitrate = os.getenv('AUDIO_RECORDING_BITRATE', '64k')
        self.audio_recording_sample_rate = int(os.getenv('AUDIO_RECORDING_SAMPLE_RATE', '16000'))
        self.audio_recording_channels = int(os.getenv('AUDIO_RECORDING_CHANNELS', '1'))
        self.user_agent = os.getenv(
            'DOUYIN_USER_AGENT',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        )
        self.startup_check_seconds = int(os.getenv('FFMPEG_STARTUP_CHECK_SECONDS', 2))
        self.ffmpeg_bin = get_ffmpeg_bin()
        self.ffprobe_bin = get_ffprobe_bin()

        if self.recording_mode not in {'video', 'audio'}:
            logger.warning('Unknown RECORDING_MODE=%s, falling back to video', self.recording_mode)
            self.recording_mode = 'video'

    def get_recording_extension(self):
        return 'mp3' if self.recording_mode == 'audio' else 'mp4'

    def get_recording_media_type(self):
        return 'audio' if self.recording_mode == 'audio' else 'video'

    def _build_recording_command(self, stream_url, output_path):
        cmd = [
            self.ffmpeg_bin,
            '-user_agent', self.user_agent,
            '-rw_timeout', '15000000',
        ]

        if '.m3u8' in stream_url:
            # Douyin HLS often requires a browser-like referer/origin.
            cmd.extend([
                '-headers',
                'Referer: https://live.douyin.com/\r\nOrigin: https://live.douyin.com\r\n'
            ])

        cmd.extend(['-i', stream_url])

        if self.recording_mode == 'audio':
            cmd.extend([
                '-vn',
                '-c:a', 'libmp3lame',
                '-b:a', self.audio_recording_bitrate,
                '-ar', str(self.audio_recording_sample_rate),
                '-ac', str(self.audio_recording_channels),
            ])
        else:
            cmd.extend([
                '-c:v', 'copy',  # 复制视频流，不重新编码
                '-c:a', 'copy',  # 复制音频流，不重新编码
            ])

        cmd.extend([
            '-t', str(self.max_recording_duration),  # 最大录制时长
            '-y',  # 覆盖已存在的文件
            '-loglevel', 'error',  # 只记录错误
            output_path
        ])
        return cmd

    def start_recording(self, recording_id, stream_url, output_path):
        """开始录制视频"""
        logger.info(
            'Starting %s recording for recording ID: %s',
            self.recording_mode,
            recording_id
        )

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        cmd = self._build_recording_command(stream_url, output_path)
        
        try:
            if not stream_url:
                logger.error('Missing stream url for recording %s', recording_id)
                return False

            # 启动录制进程
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False
            )

            # Quick health-check: if ffmpeg exits immediately, record the real reason.
            time.sleep(self.startup_check_seconds)
            if process.poll() is not None:
                error_output = (process.stderr.read() or '').strip()
                logger.error(
                    'ffmpeg exited early for recording %s (code=%s): %s',
                    recording_id,
                    process.returncode,
                    error_output or 'no stderr output'
                )
                return False

            self.recording_processes[recording_id] = process
            
            logger.info(
                '%s recording started for recording ID: %s, output: %s',
                self.recording_mode.capitalize(),
                recording_id,
                output_path
            )
            return True
        except FileNotFoundError:
            logger.error('ffmpeg not found, cannot start recording')
            return False
        except Exception as e:
            logger.error(f'Error starting video recording: {e}')
            return False

    def _read_process_stderr(self, process):
        if not process.stderr or process.stderr.closed:
            return ''

        try:
            return (process.stderr.read() or '').strip()
        except Exception:
            return ''

    def stop_recording(self, recording_id):
        """停止录制视频"""
        logger.info(f'Stopping recording for recording ID: {recording_id}')

        if recording_id in self.recording_processes:
            process = self.recording_processes[recording_id]
            try:
                if process.poll() is not None:
                    self.recording_processes.pop(recording_id, None)
                    if process.returncode == 0:
                        logger.info(
                            'Recording had already finished naturally for recording ID: %s',
                            recording_id
                        )
                        return True

                    error_output = self._read_process_stderr(process)
                    logger.warning(
                        'Recording process had already exited for recording ID %s (code=%s): %s',
                        recording_id,
                        process.returncode,
                        error_output or 'no stderr output'
                    )
                    return False

                # Ask ffmpeg to finish writing container metadata before exiting.
                if process.stdin and not process.stdin.closed:
                    try:
                        process.stdin.write('q\n')
                        process.stdin.flush()
                    except BrokenPipeError:
                        if process.poll() is not None and process.returncode == 0:
                            self.recording_processes.pop(recording_id, None)
                            logger.info(
                                'Recording finished before stop signal was delivered for recording ID: %s',
                                recording_id
                            )
                            return True
                        raise

                process.wait(timeout=15)
                # 从记录中移除
                self.recording_processes.pop(recording_id, None)
                if process.returncode not in (0, None):
                    error_output = self._read_process_stderr(process)
                    logger.warning(
                        'Recording exited with non-zero code for recording ID %s (code=%s): %s',
                        recording_id,
                        process.returncode,
                        error_output or 'no stderr output'
                    )
                    return False
                logger.info(f'Recording stopped for recording ID: {recording_id}')
                return True
            except Exception as e:
                try:
                    process.terminate()
                    process.wait(timeout=10)
                except Exception:
                    pass
                self.recording_processes.pop(recording_id, None)
                logger.error(f'Error stopping video recording: {e}')
                return False
        else:
            recording = Recording.query.filter_by(id=recording_id).first()
            external_pid = self._find_external_recording_pid(recording)
            if not external_pid:
                logger.warning(f'No recording process found for recording ID: {recording_id}')
                return False

            try:
                os.kill(external_pid, signal.SIGINT)
                if self._wait_for_process_exit(external_pid, timeout=15):
                    logger.info(
                        'Stopped external recording process %s for recording ID: %s',
                        external_pid,
                        recording_id
                    )
                    return True

                logger.warning(
                    'Timed out waiting for external recording process %s to stop for recording ID: %s',
                    external_pid,
                    recording_id
                )
                return False
            except ProcessLookupError:
                logger.info(
                    'External recording process already exited for recording ID: %s',
                    recording_id
                )
                return True
            except Exception as e:
                logger.error(f'Error stopping external video recording: {e}')
                return False
    
    def get_recording_status(self, recording_id):
        """获取录制状态"""
        if recording_id in self.recording_processes:
            process = self.recording_processes[recording_id]
            return process.poll() is None  # None表示进程仍在运行
        try:
            recording = Recording.query.filter_by(id=recording_id).first()
        except Exception:
            return False
        return bool(self._find_external_recording_pid(recording))
    
    def get_video_duration(self, video_path):
        """获取视频时长（秒）"""
        if not os.path.exists(video_path):
            logger.warning(f'Video file not found: {video_path}')
            return 0
        
        try:
            # 使用FFprobe获取视频时长
            cmd = [
                self.ffprobe_bin,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False
            )
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return int(duration)
            else:
                logger.error(f'Error getting video duration: {result.stderr}')
                return 0
        except Exception as e:
            logger.error(f'Error getting video duration: {e}')
            return 0
    
    def process_recording(self, recording_id):
        """处理录制完成的视频"""
        logger.info(f'Processing recording: {recording_id}')
        
        try:
            # 获取录制记录
            recording = Recording.query.filter_by(id=recording_id).first()
            if not recording:
                logger.error(f'Recording not found: {recording_id}')
                return False
            
            if not recording.video_path or not os.path.exists(recording.video_path):
                logger.error('Recording file does not exist for %s', recording_id)
                recording.status = 'failed'
                recording.end_time = datetime.now()
                db.session.commit()
                return False

            duration = self.get_video_duration(recording.video_path)
            recording.video_duration = duration
            logger.info(f'Updated recording duration for recording {recording_id}: {duration} seconds')
            
            # 更新录制状态
            recording.status = 'completed'
            recording.end_time = datetime.now()
            
            db.session.commit()
            logger.info(f'Recording {recording_id} processed successfully')
            return True
        except Exception as e:
            logger.error(f'Error processing recording: {e}')
            db.session.rollback()
            return False

    def recover_stale_recording(self, recording_id):
        """回收重启后遗留的录制状态，避免卡在 recording。"""
        logger.info('Recovering stale recording state for recording ID: %s', recording_id)

        try:
            recording = Recording.query.filter_by(id=recording_id).first()
            if not recording:
                logger.error('Recording not found while recovering stale state: %s', recording_id)
                return False

            if recording.status != 'recording':
                logger.info(
                    'Recording %s is no longer active during stale recovery (status=%s)',
                    recording_id,
                    recording.status
                )
                return True

            if self.get_recording_status(recording_id):
                logger.info('Recording %s is still attached to a live ffmpeg process', recording_id)
                return True

            if recording.video_path and os.path.exists(recording.video_path):
                duration = self.get_video_duration(recording.video_path)
                recording.video_duration = duration
                recording.status = 'completed' if duration > 0 else 'failed'
                recording.end_time = datetime.fromtimestamp(os.path.getmtime(recording.video_path))
                logger.info(
                    'Recovered stale recording %s as status=%s duration=%s',
                    recording_id,
                    recording.status,
                    duration
                )
            else:
                recording.status = 'failed'
                recording.end_time = datetime.now()
                logger.warning(
                    'Recovered stale recording %s as failed because output file is missing',
                    recording_id
                )

            db.session.commit()
            return True
        except Exception as e:
            logger.error(f'Error recovering stale recording: {e}')
            db.session.rollback()
            return False

    def _find_external_recording_pid(self, recording):
        if not recording or not recording.video_path:
            return None

        path_candidates = {
            recording.video_path,
            os.path.abspath(recording.video_path),
        }

        try:
            result = subprocess.run(
                ['ps', '-eo', 'pid=,args='],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
        except Exception as exc:
            logger.warning('Failed to inspect process table for recording %s: %s', recording.id, exc)
            return None

        if result.returncode != 0:
            logger.warning(
                'Failed to inspect process table for recording %s: %s',
                recording.id,
                result.stderr.strip()
            )
            return None

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or 'ffmpeg' not in line:
                continue

            pid_text, _, args = line.partition(' ')
            if not args:
                continue

            try:
                pid = int(pid_text)
            except ValueError:
                continue

            if any(candidate and candidate in args for candidate in path_candidates):
                return pid

        return None

    def _wait_for_process_exit(self, pid, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._pid_exists(pid):
                return True
            time.sleep(0.5)
        return not self._pid_exists(pid)

    def _pid_exists(self, pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def recover_stale_recordings(self):
        """批量回收遗留的录制状态。"""
        try:
            stale_recordings = Recording.query.filter_by(status='recording').all()
            recovered_count = 0

            for recording in stale_recordings:
                if self.recover_stale_recording(recording.id):
                    refreshed = Recording.query.filter_by(id=recording.id).first()
                    if refreshed and refreshed.status != 'recording':
                        recovered_count += 1

            logger.info('Recovered %s stale recording rows', recovered_count)
            return recovered_count
        except Exception as e:
            logger.error(f'Error recovering stale recordings: {e}')
            return 0

    def cleanup_recording(self, recording_id):
        """清理录制文件"""
        logger.info(f'Cleaning up recording: {recording_id}')
        
        try:
            # 获取录制记录
            recording = Recording.query.filter_by(id=recording_id).first()
            if not recording:
                logger.error(f'Recording not found: {recording_id}')
                return False
            
            # 清理录制文件
            if self.cleanup_video and recording.video_path and os.path.exists(recording.video_path):
                try:
                    os.remove(recording.video_path)
                    logger.info(f'Cleaned up recording file for recording {recording_id}')
                except Exception as e:
                    logger.error(f'Error cleaning up recording file: {e}')
            
            return True
        except Exception as e:
            logger.error(f'Error cleaning up recording: {e}')
            db.session.rollback()
            return False
    
    def cleanup_old_recordings(self, days=None):
        """清理旧的录制文件"""
        days = self.recording_retention_days if days is None else days
        logger.info(f'Cleaning up recordings older than {days} days')
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            old_recordings = Recording.query.filter(
                Recording.end_time < cutoff_date,
                Recording.status == 'completed'
            ).all()
            
            cleaned_count = 0
            for recording in old_recordings:
                if self.cleanup_recording(recording.id):
                    cleaned_count += 1
            
            logger.info(f'Cleaned up {cleaned_count} old recordings')
            return cleaned_count
        except Exception as e:
            logger.error(f'Error cleaning up old recordings: {e}')
            return 0

# 创建录制服务实例
video_recorder = VideoRecorder()
