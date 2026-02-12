import logging
import os
import time
import traceback
from datetime import datetime, timedelta
from threading import Thread
from app.services.live_monitor import live_monitor
from app.services.content_analyzer import content_analyzer
from app.services.notification_service import notification_service
from app.services.video_recorder import video_recorder
from app.models import db, Recording, Summary
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class TaskScheduler:
    """定时任务服务"""
    
    def __init__(self):
        self.is_running = False
        self.threads = []
        self.summary_send_time = os.getenv('SUMMARY_SEND_TIME', '08:00')
        self.backup_interval = int(os.getenv('BACKUP_INTERVAL', 86400))  # 24小时
        self.last_backup_time = datetime.now()
    
    def start(self):
        """启动定时任务服务"""
        logger.info('Starting task scheduler service')
        self.is_running = True
        
        # 启动直播监测线程
        monitor_thread = Thread(target=self._run_live_monitor, daemon=True)
        monitor_thread.start()
        self.threads.append(monitor_thread)
        
        # 启动内容分析线程
        analyzer_thread = Thread(target=self._run_content_analyzer, daemon=True)
        analyzer_thread.start()
        self.threads.append(analyzer_thread)
        
        # 启动通知发送线程
        notification_thread = Thread(target=self._run_notification_service, daemon=True)
        notification_thread.start()
        self.threads.append(notification_thread)
        
        # 启动维护任务线程
        maintenance_thread = Thread(target=self._run_maintenance_tasks, daemon=True)
        maintenance_thread.start()
        self.threads.append(maintenance_thread)
        
        logger.info('Task scheduler service started successfully')
    
    def stop(self):
        """停止定时任务服务"""
        logger.info('Stopping task scheduler service')
        self.is_running = False
        
        # 停止直播监测
        live_monitor.stop_monitoring()
        
        # 等待线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=10)
        
        logger.info('Task scheduler service stopped successfully')
    
    def _run_live_monitor(self):
        """运行直播监测任务"""
        logger.info('Starting live monitor task')
        # 直接调用直播监测服务的启动方法
        live_monitor.start_monitoring()
    
    def _run_content_analyzer(self):
        """运行内容分析任务"""
        logger.info('Starting content analyzer task')
        
        while self.is_running:
            try:
                # 查找需要分析的录制
                self._analyze_pending_recordings()
                # 每5分钟检查一次
                time.sleep(300)
            except Exception as e:
                logger.error(f'Error in content analyzer task: {e}')
                time.sleep(300)
    
    def _run_notification_service(self):
        """运行通知发送任务"""
        logger.info('Starting notification service task')
        
        while self.is_running:
            try:
                # 检查是否到了发送时间
                current_time = datetime.now().strftime('%H:%M')
                if current_time == self.summary_send_time:
                    # 发送每日摘要
                    notification_service.send_daily_summary()
                    # 避免重复发送，等待1分钟
                    time.sleep(60)
                else:
                    # 每分钟检查一次
                    time.sleep(60)
            except Exception as e:
                logger.error(f'Error in notification service task: {e}')
                time.sleep(60)
    
    def _run_maintenance_tasks(self):
        """运行维护任务"""
        logger.info('Starting maintenance tasks')
        
        while self.is_running:
            try:
                # 执行数据库备份
                self._backup_database()
                
                # 清理旧的录制文件
                self._cleanup_old_recordings()
                
                # 每小时执行一次维护任务
                time.sleep(3600)
            except Exception as e:
                logger.error(f'Error in maintenance tasks: {e}')
                time.sleep(3600)
    
    def _analyze_pending_recordings(self):
        """分析待处理的录制"""
        logger.info('Checking for pending recordings to analyze')
        
        try:
            # 查找已完成但未分析的录制
            pending_recordings = Recording.query.filter_by(
                status='completed'
            ).outerjoin(
                Summary
            ).filter(
                Summary.id == None
            ).all()
            
            logger.info(f'Found {len(pending_recordings)} pending recordings to analyze')
            
            for recording in pending_recordings:
                try:
                    # 分析录制内容
                    success = content_analyzer.analyze_recording(recording.id)
                    if success:
                        logger.info(f'Analyzed recording {recording.id} successfully')
                        # 分析完成后清理录制文件
                        video_recorder.cleanup_recording(recording.id)
                    else:
                        logger.error(f'Failed to analyze recording {recording.id}')
                except Exception as e:
                    logger.error(f'Error analyzing recording {recording.id}: {e}')
                
                # 避免同时分析太多录制，每次分析后休息一下
                time.sleep(5)
        except Exception as e:
            logger.error(f'Error checking pending recordings: {e}')
    
    def _backup_database(self):
        """备份数据库"""
        current_time = datetime.now()
        if (current_time - self.last_backup_time).total_seconds() >= self.backup_interval:
            logger.info('Running database backup')
            try:
                # 确保备份目录存在
                backup_dir = os.path.join(os.getcwd(), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                # 生成备份文件名
                backup_filename = f'db_backup_{current_time.strftime("%Y%m%d_%H%M%S")}.db'
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # 复制数据库文件
                db_path = os.path.join(os.getcwd(), 'instance', 'data.db')
                if os.path.exists(db_path):
                    import shutil
                    shutil.copy2(db_path, backup_path)
                    logger.info(f'Database backed up to: {backup_path}')
                    
                    # 清理旧备份（保留最近7个）
                    self._cleanup_old_backups(backup_dir, 7)
                    
                    self.last_backup_time = current_time
                else:
                    logger.warning('Database file not found')
            except Exception as e:
                logger.error(f'Error backing up database: {e}')
    
    def _cleanup_old_backups(self, backup_dir, keep_count):
        """清理旧的备份文件"""
        try:
            # 获取所有备份文件，按修改时间排序
            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith('db_backup_')],
                key=lambda x: os.path.getmtime(os.path.join(backup_dir, x))
            )
            
            # 删除超出保留数量的备份
            if len(backups) > keep_count:
                for backup in backups[:-keep_count]:
                    backup_path = os.path.join(backup_dir, backup)
                    os.remove(backup_path)
                    logger.info(f'Cleaned up old backup: {backup}')
        except Exception as e:
            logger.error(f'Error cleaning up old backups: {e}')
    
    def _cleanup_old_recordings(self):
        """清理旧的录制文件"""
        logger.info('Cleaning up old recordings')
        try:
            # 清理7天前的录制文件
            video_recorder.cleanup_old_recordings(days=7)
        except Exception as e:
            logger.error(f'Error cleaning up old recordings: {e}')

# 创建定时任务服务实例
task_scheduler = TaskScheduler()