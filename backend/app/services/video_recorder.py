import os
import subprocess
import time
import logging
import traceback
from datetime import datetime
from app.models import db, Recording
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class VideoRecorder:
    """视频录制服务"""
    
    def __init__(self):
        self.recording_quality = os.getenv('RECORDING_QUALITY', '720p')
        self.recording_processes = {}
        self.max_recording_duration = int(os.getenv('MAX_RECORDING_DURATION', 3600))  # 最大录制时长
        self.cleanup_video = os.getenv('CLEANUP_VIDEO', 'True').lower() == 'true'  # 是否清理视频文件
    
    def start_recording(self, recording_id, stream_url, output_path):
        """开始录制视频"""
        logger.info(f'Starting video recording for recording ID: {recording_id}')
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-c:v', 'copy',  # 复制视频流，不重新编码
            '-c:a', 'copy',  # 复制音频流，不重新编码
            '-t', str(self.max_recording_duration),  # 最大录制时长
            '-y',  # 覆盖已存在的文件
            '-loglevel', 'error',  # 只记录错误
            output_path
        ]
        
        try:
            # 启动录制进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
            
            # 记录进程
            self.recording_processes[recording_id] = process
            
            logger.info(f'Video recording started for recording ID: {recording_id}, output: {output_path}')
            return True
        except Exception as e:
            logger.error(f'Error starting video recording: {e}')
            return False
    
    def stop_recording(self, recording_id):
        """停止录制视频"""
        logger.info(f'Stopping video recording for recording ID: {recording_id}')
        
        if recording_id in self.recording_processes:
            process = self.recording_processes[recording_id]
            try:
                # 发送停止信号
                process.terminate()
                # 等待进程结束
                process.wait(timeout=10)
                # 从记录中移除
                del self.recording_processes[recording_id]
                logger.info(f'Video recording stopped for recording ID: {recording_id}')
                return True
            except Exception as e:
                logger.error(f'Error stopping video recording: {e}')
                return False
        else:
            logger.warning(f'No recording process found for recording ID: {recording_id}')
            return False
    
    def get_recording_status(self, recording_id):
        """获取录制状态"""
        if recording_id in self.recording_processes:
            process = self.recording_processes[recording_id]
            return process.poll() is None  # None表示进程仍在运行
        else:
            return False
    
    def get_video_duration(self, video_path):
        """获取视频时长（秒）"""
        if not os.path.exists(video_path):
            logger.warning(f'Video file not found: {video_path}')
            return 0
        
        try:
            # 使用FFprobe获取视频时长
            cmd = [
                'ffprobe',
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
            
            # 更新视频时长
            if os.path.exists(recording.video_path):
                duration = self.get_video_duration(recording.video_path)
                recording.video_duration = duration
                logger.info(f'Updated video duration for recording {recording_id}: {duration} seconds')
            
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
    
    def cleanup_recording(self, recording_id):
        """清理录制文件"""
        logger.info(f'Cleaning up recording: {recording_id}')
        
        try:
            # 获取录制记录
            recording = Recording.query.filter_by(id=recording_id).first()
            if not recording:
                logger.error(f'Recording not found: {recording_id}')
                return False
            
            # 清理视频文件
            if self.cleanup_video and recording.video_path and os.path.exists(recording.video_path):
                try:
                    os.remove(recording.video_path)
                    recording.video_path = None
                    db.session.commit()
                    logger.info(f'Cleaned up video file for recording {recording_id}')
                except Exception as e:
                    logger.error(f'Error cleaning up video file: {e}')
            
            return True
        except Exception as e:
            logger.error(f'Error cleaning up recording: {e}')
            db.session.rollback()
            return False
    
    def cleanup_old_recordings(self, days=7):
        """清理旧的录制文件"""
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