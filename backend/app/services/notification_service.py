import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import requests
import json
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
        # 邮件配置
        self.email_smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.qq.com')
        self.email_smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 587))
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_recipients = os.getenv('EMAIL_RECIPIENTS', '').split(',')
        
        # 微信配置
        self.wechat_webhook_url = os.getenv('WECHAT_WEBHOOK_URL')
        
        # 发送时间配置
        self.summary_send_time = os.getenv('SUMMARY_SEND_TIME', '08:00')
    
    def send_summary(self, summary_id, send_email=True, send_wechat=True):
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
            
            # 发送邮件
            if send_email and self.email_sender and self.email_password:
                email_sent = self._send_email(notification_data)
                if not email_sent:
                    logger.error('Failed to send email notification')
            
            # 发送微信
            if send_wechat and self.wechat_webhook_url:
                wechat_sent = self._send_wechat(notification_data)
                if not wechat_sent:
                    logger.error('Failed to send wechat notification')
            
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
            
            # 发送邮件
            if self.email_sender and self.email_password:
                email_sent = self._send_daily_email(daily_summary_data)
                if not email_sent:
                    logger.error('Failed to send daily email summary')
            
            # 发送微信
            if self.wechat_webhook_url:
                wechat_sent = self._send_daily_wechat(daily_summary_data)
                if not wechat_sent:
                    logger.error('Failed to send daily wechat summary')
            
            logger.info('Daily summary notifications sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending daily summary: {e}')
            return False
    
    def _send_email(self, notification_data):
        """发送邮件通知"""
        logger.info(f'Sending email notification for anchor: {notification_data.get("anchor_name")}')
        
        # 构建邮件内容
        subject = f'{notification_data.get("anchor_name")} 直播摘要 ({notification_data.get("date")})'
        
        # 构建HTML邮件内容
        html_content = f"""
        <html>
        <body>
            <h2>{notification_data.get('anchor_name')} 直播摘要</h2>
            <p><strong>日期:</strong> {notification_data.get('date')}</p>
            
            <h3>核心观点</h3>
            <pre>{notification_data.get('core_points')}</pre>
            
            <h3>市场分析</h3>
            <p>{notification_data.get('market_analysis')}</p>
            
            <h3>投资建议</h3>
            <pre>{notification_data.get('investment_advice')}</pre>
            
            <h3>关键词</h3>
            <p>{notification_data.get('keywords')}</p>
            
            <p>此邮件由抖音直播录制系统自动发送，请勿直接回复。</p>
        </body>
        </html>
        """
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = Header('抖音直播摘要', 'utf-8')
        msg['To'] = Header(', '.join(self.email_recipients), 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 添加HTML内容
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        try:
            # 连接SMTP服务器
            server = smtplib.SMTP(self.email_smtp_server, self.email_smtp_port)
            server.starttls()
            server.login(self.email_sender, self.email_password)
            
            # 发送邮件
            server.sendmail(self.email_sender, self.email_recipients, msg.as_string())
            server.quit()
            
            logger.info('Email notification sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending email: {e}')
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

*此消息由抖音直播录制系统自动发送*"
        
        # 构建请求数据
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content
            }
        }
        
        try:
            # 发送请求
            response = requests.post(self.wechat_webhook_url, json=data)
            response.raise_for_status()
            
            logger.info('Wechat notification sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending wechat notification: {e}')
            return False
    
    def _send_daily_email(self, daily_summary_data):
        """发送每日邮件摘要"""
        logger.info('Sending daily email summary')
        
        # 构建邮件内容
        subject = f'每日直播摘要 ({daily_summary_data.get("date")})'
        
        # 构建HTML邮件内容
        html_content = f"""
        <html>
        <body>
            <h2>每日直播摘要</h2>
            <p><strong>日期:</strong> {daily_summary_data.get('date')}</p>
            <p><strong>摘要数量:</strong> {daily_summary_data.get('summary_count')}</p>
            
            {''.join([f"""
            <h3>{summary.get('anchor_name')}</h3>
            <h4>核心观点</h4>
            <pre>{summary.get('core_points')}</pre>
            <h4>市场分析</h4>
            <p>{summary.get('market_analysis')}</p>
            <h4>投资建议</h4>
            <pre>{summary.get('investment_advice')}</pre>
            <hr>
            """ for summary in daily_summary_data.get('summaries', [])])}
            
            <p>此邮件由抖音直播录制系统自动发送，请勿直接回复。</p>
        </body>
        </html>
        """
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = Header('抖音直播摘要', 'utf-8')
        msg['To'] = Header(', '.join(self.email_recipients), 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 添加HTML内容
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        try:
            # 连接SMTP服务器
            server = smtplib.SMTP(self.email_smtp_server, self.email_smtp_port)
            server.starttls()
            server.login(self.email_sender, self.email_password)
            
            # 发送邮件
            server.sendmail(self.email_sender, self.email_recipients, msg.as_string())
            server.quit()
            
            logger.info('Daily email summary sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending daily email summary: {e}')
            return False
    
    def _send_daily_wechat(self, daily_summary_data):
        """发送每日微信摘要"""
        logger.info('Sending daily wechat summary')
        
        # 构建Markdown内容
        markdown_content = f"""
## 每日直播摘要 ({daily_summary_data.get('date')})

### 摘要统计
- 摘要数量: {daily_summary_data.get('summary_count')}

{daily_summary_data.get('summaries', [])[0].get('anchor_name') if daily_summary_data.get('summaries') else '无'}

{''.join([f"""
### {summary.get('anchor_name')}

#### 核心观点
{summary.get('core_points')}

#### 投资建议
{summary.get('investment_advice')}

""" for summary in daily_summary_data.get('summaries', [])[:2]])}  # 只显示前两个摘要

{"\n... 更多摘要请查看邮件" if len(daily_summary_data.get('summaries', [])) > 2 else ''}

*此消息由抖音直播录制系统自动发送*"
        
        # 构建请求数据
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content
            }
        }
        
        try:
            # 发送请求
            response = requests.post(self.wechat_webhook_url, json=data)
            response.raise_for_status()
            
            logger.info('Daily wechat summary sent successfully')
            return True
        except Exception as e:
            logger.error(f'Error sending daily wechat summary: {e}')
            return False

# 创建通知服务实例
notification_service = NotificationService()