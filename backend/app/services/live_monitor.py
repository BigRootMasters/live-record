import time
import requests
import logging
import traceback
from datetime import datetime
from app.models import db, Anchor, Recording
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class LiveMonitor:
    """直播监测服务"""
    
    def __init__(self):
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 300))  # 默认5分钟检查一次
        self.user_agent = os.getenv('DOUYIN_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36')
        self.use_real_api = os.getenv('USE_REAL_API', 'False').lower() == 'true'
        self.api_timeout = int(os.getenv('API_TIMEOUT', 10))
        self.api_retries = int(os.getenv('API_RETRIES', 3))
        self.is_running = False
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def start_monitoring(self):
        """开始监测"""
        logger.info('Starting live monitor service')
        self.is_running = True
        
        while self.is_running:
            try:
                self.check_all_anchors()
                logger.info(f'Checked all anchors, sleeping for {self.check_interval} seconds')
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f'Error in live monitor: {e}')
                time.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """停止监测"""
        logger.info('Stopping live monitor service')
        self.is_running = False
    
    def check_all_anchors(self):
        """检查所有关注的主播"""
        try:
            # 获取所有关注的主播
            anchors = Anchor.query.filter_by(is_followed=True).all()
            logger.info(f'Checking {len(anchors)} anchors')
            
            for anchor in anchors:
                try:
                    self.check_anchor(anchor)
                    # 避免请求过快，添加短暂延迟
                    time.sleep(1)
                except Exception as e:
                    logger.error(f'Error checking anchor {anchor.name}: {e}')
                    time.sleep(1)
        except Exception as e:
            logger.error(f'Error checking all anchors: {e}')
    
    def check_anchor(self, anchor):
        """检查单个主播是否开播"""
        logger.info(f'Checking anchor: {anchor.name} (ID: {anchor.douyin_id})')
        
        try:
            # 检查直播状态
            is_live, live_info = self._check_live_status(anchor.douyin_id)
            
            if is_live:
                logger.info(f'Anchor {anchor.name} is live!')
                # 检查是否已经有正在进行的录制
                existing_recording = Recording.query.filter_by(
                    anchor_id=anchor.id,
                    status='recording'
                ).first()
                
                if not existing_recording:
                    # 开始新的录制
                    self.start_recording(anchor, live_info)
                else:
                    logger.info(f'Anchor {anchor.name} is already being recorded')
            else:
                logger.info(f'Anchor {anchor.name} is not live')
                # 检查是否有正在进行的录制需要停止
                existing_recording = Recording.query.filter_by(
                    anchor_id=anchor.id,
                    status='recording'
                ).first()
                
                if existing_recording:
                    # 停止录制
                    self.stop_recording(existing_recording)
        except Exception as e:
            logger.error(f'Error checking anchor {anchor.name}: {e}')
    
    def start_recording(self, anchor, live_info=None):
        """开始录制直播"""
        logger.info(f'Starting recording for anchor {anchor.name}')
        
        # 创建录制目录
        video_storage_path = os.getenv('VIDEO_STORAGE_PATH', './data/temp_videos')
        anchor_dir = os.path.join(video_storage_path, str(anchor.id))
        os.makedirs(anchor_dir, exist_ok=True)
        
        # 生成视频文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        video_filename = f'{anchor.id}_{timestamp}.mp4'
        video_path = os.path.join(anchor_dir, video_filename)
        
        # 创建录制记录
        recording = Recording(
            anchor_id=anchor.id,
            video_path=video_path,
            start_time=datetime.now(),
            status='recording'
        )
        
        db.session.add(recording)
        db.session.commit()
        
        # 启动录制进程
        # 这里需要实现实际的录制逻辑
        # 由于抖音API的限制，这里提供一个模拟实现
        # 实际项目中需要使用FFmpeg或其他工具来录制直播
        
        logger.info(f'Recording started for anchor {anchor.name}, recording ID: {recording.id}')
    
    def stop_recording(self, recording):
        """停止录制直播"""
        logger.info(f'Stopping recording for recording ID: {recording.id}')
        
        # 更新录制状态
        recording.end_time = datetime.now()
        recording.status = 'completed'
        
        # 计算视频时长
        # 这里需要实现实际的视频时长计算
        # 实际项目中可以使用FFprobe来获取视频时长
        recording.video_duration = 3600  # 模拟1小时
        
        db.session.commit()
        
        logger.info(f'Recording stopped for recording ID: {recording.id}')
    
    def _check_live_status(self, douyin_id):
        """检查直播状态"""
        if self.use_real_api:
            return self._real_check_live_status(douyin_id)
        else:
            return self._mock_check_live_status(douyin_id)
    
    def _real_check_live_status(self, douyin_id):
        """使用真实API检查直播状态"""
        # 这里需要实现真实的抖音API调用
        # 由于抖音API的限制，这里提供一个框架
        for retry in range(self.api_retries):
            try:
                logger.info(f'Checking live status via API for ID: {douyin_id}, retry: {retry+1}')
                # 构建API请求
                # 注意：实际项目中需要使用正确的API端点和参数
                # 这里只是一个示例框架
                api_url = f'https://api.example.com/douyin/live/status'
                params = {'douyin_id': douyin_id}
                
                response = requests.get(
                    api_url,
                    params=params,
                    headers=self.headers,
                    timeout=self.api_timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    is_live = data.get('is_live', False)
                    live_info = data.get('live_info', {})
                    return is_live, live_info
                else:
                    logger.warning(f'API returned non-200 status: {response.status_code}')
            except Exception as e:
                logger.warning(f'API request failed: {e}')
            
            if retry < self.api_retries - 1:
                logger.info(f'Retrying in 2 seconds...')
                time.sleep(2)
        
        # 如果所有重试都失败，返回模拟结果
        logger.warning('All API retries failed, using mock result')
        return self._mock_check_live_status(douyin_id)
    
    def _mock_check_live_status(self, douyin_id):
        """模拟检查直播状态"""
        # 这里只是一个模拟实现
        # 实际项目中需要使用真实的API或方法来检查
        import random
        is_live = random.choice([True, False, False, False, False])  # 模拟20%的概率开播
        live_info = {
            'room_id': f'room_{douyin_id}_{int(time.time())}',
            'stream_url': 'https://example.com/stream',
            'title': '模拟直播标题',
            'viewer_count': random.randint(100, 10000)
        }
        return is_live, live_info

# 创建监测服务实例
live_monitor = LiveMonitor()