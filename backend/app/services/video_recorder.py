import subprocess
import logging
import os
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
    
    def start_recording(self, recording_id, stream_url, output_path):
        """开始录制视频"""
        logger.info(f'Starting video recording for recording ID: {recording_id}')
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 根据录制质量设置参数
        quality_params = self._get_quality_params()
        
        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-c:v', 'copy',  # 复制视频流，不重新编码
            '-c:a', 'copy',  # 复制音频流，不重新编码
            '-t', '3600',  # 最大录制时长1小时
            '-y',  # 覆盖已存在的文件
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
    
    def _get_quality_params(self):
        """根据录制质量获取参数"""
        quality_map = {
            '480p': {'video_bitrate': '1000k', 'audio_bitrate': '128k'},
            '720p': {'video_bitrate': '2000k', 'audio_bitrate': '192k'},
            '1080p': {'video_bitrate': '4000k', 'audio_bitrate': '256k'}
        }
        return quality_map.get(self.recording_quality, quality_map['720p'])
    
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
        
        # 获取录制记录
        db_session = next(db.get_db())
        try:
            recording = db_session.query(Recording).filter_by(id=recording_id).first()
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
            
            db_session.commit()
            logger.info(f'Recording {recording_id} processed successfully')
            return True
        except Exception as e:
            logger.error(f'Error processing recording: {e}')
            db_session.rollback()
            return False
        finally:
            db_session.close()

# 创建录制服务实例
video_recorder = VideoRecorder()