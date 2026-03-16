import time
import logging
from datetime import datetime
from app.models import db, Anchor, Recording
from app.services.live_discovery_service import live_discovery_service
from app.services.video_recorder import video_recorder
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
            is_live, live_info = self._check_live_status(anchor)
            
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

        stream_candidates = []
        for key in ['stream_url', 'hls_url', 'flv_url']:
            value = (live_info or {}).get(key)
            if value and value not in stream_candidates:
                stream_candidates.append(value)

        if not stream_candidates:
            logger.error('No stream url available for anchor %s', anchor.name)
            recording.status = 'failed'
            recording.end_time = datetime.now()
            db.session.commit()
            return None

        started = False
        for candidate_url in stream_candidates:
            started = video_recorder.start_recording(recording.id, candidate_url, video_path)
            if started:
                break

        if not started:
            logger.error(
                'Failed to start recording for anchor %s using %d stream candidates',
                anchor.name,
                len(stream_candidates)
            )
            recording.status = 'failed'
            recording.end_time = datetime.now()
            db.session.commit()
            return None

        logger.info(f'Recording started for anchor {anchor.name}, recording ID: {recording.id}')
        return recording
    
    def stop_recording(self, recording):
        """停止录制直播"""
        logger.info(f'Stopping recording for recording ID: {recording.id}')

        stopped = video_recorder.stop_recording(recording.id)
        if not stopped:
            logger.warning('Recording process was not running for ID: %s', recording.id)

        processed = video_recorder.process_recording(recording.id)
        if not processed:
            logger.warning('Post-processing failed for recording ID: %s', recording.id)
        
        logger.info(f'Recording stopped for recording ID: {recording.id}')
    
    def _check_live_status(self, anchor):
        """检查直播状态"""
        if self.use_real_api:
            return self._real_check_live_status(anchor)
        else:
            return self._mock_check_live_status(anchor.douyin_id)
    
    def _real_check_live_status(self, anchor):
        """通过固定主播配置自动发现当前直播与流地址"""
        discovery = live_discovery_service.discover_for_anchor(anchor)
        resolved = discovery.get('resolved') or {}
        is_live = resolved.get('status') == 'live'
        stream_url = resolved.get('flv_url') or resolved.get('hls_url')

        live_info = {
            'room_id': (resolved.get('room') or {}).get('roomId') or anchor.room_id,
            'stream_url': stream_url,
            'title': resolved.get('title') or anchor.name,
            'anchor_id': (resolved.get('anchor') or {}).get('id_str'),
            'flv_url': resolved.get('flv_url'),
            'hls_url': resolved.get('hls_url'),
            'lls_url': resolved.get('lls_url'),
        }
        return is_live, live_info
    
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
