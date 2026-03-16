import logging
import os
import time

import requests
from dotenv import load_dotenv

from app.models import Recording, Summary, db

load_dotenv()

logger = logging.getLogger(__name__)


class NotificationService:
    """Deliver transcript availability notifications to WeCom."""

    def __init__(self):
        self.wechat_webhook_url = os.getenv('WECHAT_WEBHOOK_URL')
        self.wechat_timeout = int(os.getenv('WECHAT_TIMEOUT', 10))
        self.wechat_retries = int(os.getenv('WECHAT_RETRIES', 3))
        self.summary_send_time = os.getenv('SUMMARY_SEND_TIME', '08:00')
        self.transcript_base_url = os.getenv('TRANSCRIPT_BASE_URL', 'http://localhost:5173/summaries')

    def _get_transcript_link(self, summary_id):
        if not self.transcript_base_url:
            return None

        if 'your-server-ip-or-domain' in self.transcript_base_url:
            return None

        return f'{self.transcript_base_url.rstrip("/")}/{summary_id}'

    def send_summary(self, summary_id):
        summary = Summary.query.filter_by(id=summary_id).first()
        if not summary or summary.status != 'completed':
            logger.warning('Summary %s is not ready for notification', summary_id)
            return False
        return self._send_transcript_notification(summary)

    def send_daily_summary(self):
        logger.info('Sending pending transcript notifications')

        summaries = Summary.query.join(Recording).filter(
            Summary.status == 'completed',
            Recording.status == 'transcribed'
        ).all()

        if not summaries:
            logger.info('No completed transcripts waiting for delivery')
            return False

        delivered = 0
        for summary in summaries:
            if self._send_transcript_notification(summary):
                delivered += 1

        logger.info('Delivered %s transcript notifications', delivered)
        return delivered > 0

    def _send_transcript_notification(self, summary):
        recording = summary.recording
        anchor = recording.anchor if recording else None
        if not recording or not anchor:
            logger.error('Summary %s is missing related recording or anchor', summary.id)
            return False

        transcript_length = len(summary.content or '')
        preview = self._build_preview(summary.content or '')
        transcript_link = self._get_transcript_link(summary.id)

        notification_data = {
            'anchor_name': anchor.name,
            'date': recording.start_time.strftime('%Y-%m-%d') if recording.start_time else '未知日期',
            'transcript_length': transcript_length,
            'preview': preview,
            'transcript_link': transcript_link,
            'recording_id': recording.id,
        }

        if not self.wechat_webhook_url:
            logger.warning('Wechat webhook URL not configured, skipping delivery for summary %s', summary.id)
            return False

        if not self._send_wechat(notification_data):
            return False

        summary.status = 'notified'
        recording.status = 'notified'
        db.session.commit()
        return True

    def _send_wechat(self, notification_data):
        link_block = (
            f"[查看完整文字稿]({notification_data['transcript_link']})\n\n"
            if notification_data.get('transcript_link')
            else "未配置可访问的全文链接，如需打开全文，请先设置 TRANSCRIPT_BASE_URL。\n\n"
        )

        markdown_content = (
            f"## {notification_data['anchor_name']} 直播文字稿已生成\n\n"
            f"- 直播日期：{notification_data['date']}\n"
            f"- 录制编号：{notification_data['recording_id']}\n"
            f"- 文字长度：约 {notification_data['transcript_length']} 字\n\n"
            f"### 内容预览\n"
            f"{notification_data['preview']}\n\n"
            f"{link_block}"
            '此消息由直播转写系统自动发送'
        )

        data = {
            'msgtype': 'markdown',
            'markdown': {
                'content': markdown_content
            }
        }

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

    def _build_preview(self, transcript, limit=120):
        preview = transcript.replace('\n', ' ').strip()
        if len(preview) <= limit:
            return preview or '暂无文字稿内容'
        return f'{preview[:limit]}...'


notification_service = NotificationService()
