import logging
import os
import requests
import traceback
from datetime import datetime
from app.models import db, Summary, Recording, Anchor
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务"""
    
    def __init__(self):
        # 企业微信配置
        self.wechat_webhook_url = os.getenv('WECHAT_WEBHOOK_URL')
        self.wechat_timeout = int(os.getenv('WECHAT_TIMEOUT', 10))
        self.wechat_retries = int(os.getenv('WECHAT_RETRIES', 3))
        
        # 发送时间配置
        self.summary_send_time = os.getenv('SUMMARY_SEND_TIME', '08:00')
    
    def send_summary(self, summary_id):
        """发送摘要通知"""
        logger.info(f'Sending summary notification for summary: {summary_id}')
        
        try:
            # 获取摘要信息
            summary = Summary.query.filter_by(id=summary_id).first()
            if not summary:
                logger.error(f'Summary not found: {summary_id}')
                return False
            
            # 获取录制信息
            recording = summary.recording
            if not recording:
                logger.error(f'Recording not found for summary: {summary_id}')
                return False
            
            # 获取主播信息
            anchor = recording.anchor
            if not anchor:
                logger.error(f'Anchor not found for recording: {recording.id}')
                return False
            
            # 生成通知内容
            notification_data = {
                'anchor_name': anchor.name,
                'date': recording.start_time.strftime('%Y-%m-%d'),
                'content': summary.content,
                'core_points': summary.core_points,
                'market_analysis': summary.market_analysis,
                'investment_advice': summary.investment_advice,
                'keywords': summary.keywords,
                'recording_id': recording.id
            }
            
            # 发送企业微信通知
            if self.wechat_webhook_url:
                wechat_sent = self._send_wechat(notification_data)
                if not wechat_sent:
                    logger.error('Failed to send wechat notification')
                    return False
            else:
                logger.warning('Wechat webhook URL not configured')
                return False
            
            logger.info(f'Summary {summary_id} notification sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending summary notification: {e}')
            return False
    
    def send_daily_summary(self):
        """发送每日摘要"""
        logger.info('Sending daily summary notifications')
        
        # 获取今天的日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 查询今天完成的摘要
            summaries = Summary.query.join(Recording).filter(
                Summary.status == 'completed',
                Recording.start_time >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ).all()
            
            if not summaries:
                logger.info('No summaries found for today')
                return False
            
            # 生成每日摘要内容
            daily_summary_data = {
                'date': today,
                'summary_count': len(summaries),
                'summaries': []
            }
            
            for summary in summaries:
                recording = summary.recording
                anchor = recording.anchor if recording else None
                
                summary_info = {
                    'anchor_name': anchor.name if anchor else 'Unknown',
                    'content': summary.content,
                    'core_points': summary.core_points,
                    'market_analysis': summary.market_analysis,
                    'investment_advice': summary.investment_advice,
                    'keywords': summary.keywords
                }
                daily_summary_data['summaries'].append(summary_info)
            
            # 发送企业微信通知
            if self.wechat_webhook_url:
                wechat_sent = self._send_daily_wechat(daily_summary_data)
                if not wechat_sent:
                    logger.error('Failed to send daily wechat summary')
                    return False
            else:
                logger.warning('Wechat webhook URL not configured')
                return False
            
            logger.info('Daily summary notifications sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending daily summary: {e}')
            return False
    
    def _send_wechat(self, notification_data):
        """发送微信通知"""
        logger.info(f'Sending wechat notification for anchor: {notification_data.get("anchor_name")}')
        
        # 构建Markdown内容
        markdown_content = f"""
## {notification_data.get('anchor_name')} 直播摘要 ({notification_data.get('date')})

### 核心观点
{notification_data.get('core_points')}

### 市场分析
{notification_data.get('market_analysis')}

### 投资建议
{notification_data.get('investment_advice')}

### 关键词
{notification_data.get('keywords')}

*此消息由抖音直播录制系统自动发送*
        """
        
        # 构建请求数据
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content
            }
        }
        
        # 发送请求，带重试机制
        for retry in range(self.wechat_retries):
            try:
                # 发送请求
                response = requests.post(
                    self.wechat_webhook_url, 
                    json=data,
                    timeout=self.wechat_timeout
                )
                response.raise_for_status()
                
                # 检查响应
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info('Wechat notification sent successfully')
                    return True
                else:
                    logger.error(f'Wechat API error: {result.get("errmsg", "Unknown error")}')
            except Exception as e:
                logger.warning(f'Error sending wechat notification (attempt {retry+1}/{self.wechat_retries}): {e}')
            
            if retry < self.wechat_retries - 1:
                logger.info(f'Retrying in 2 seconds...')
                import time
                time.sleep(2)
        
        logger.error('Failed to send wechat notification after all retries')
        return False
    
    def _send_daily_wechat(self, daily_summary_data):
        """发送每日微信摘要"""
        logger.info('Sending daily wechat summary')
        
        # 构建Markdown内容
        markdown_content = f"""
## 每日直播摘要 ({daily_summary_data.get('date')})

### 摘要统计
- 摘要数量: {daily_summary_data.get('summary_count')}

{''.join([f"""
### {summary.get('anchor_name')}

#### 核心观点
{summary.get('core_points')}

#### 投资建议
{summary.get('investment_advice')}

""" for summary in daily_summary_data.get('summaries', [])[:2]])}  # 只显示前两个摘要

{"\n... 更多摘要请查看系统" if len(daily_summary_data.get('summaries', [])) > 2 else ''}

*此消息由抖音直播录制系统自动发送*
        """
        
        # 构建请求数据
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content
            }
        }
        
        # 发送请求，带重试机制
        for retry in range(self.wechat_retries):
            try:
                # 发送请求
                response = requests.post(
                    self.wechat_webhook_url, 
                    json=data,
                    timeout=self.wechat_timeout
                )
                response.raise_for_status()
                
                # 检查响应
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info('Daily wechat summary sent successfully')
                    return True
                else:
                    logger.error(f'Wechat API error: {result.get("errmsg", "Unknown error")}')
            except Exception as e:
                logger.warning(f'Error sending daily wechat summary (attempt {retry+1}/{self.wechat_retries}): {e}')
            
            if retry < self.wechat_retries - 1:
                logger.info(f'Retrying in 2 seconds...')
                import time
                time.sleep(2)
        
        logger.error('Failed to send daily wechat summary after all retries')
        return False

# 创建通知服务实例
notification_service = NotificationService()