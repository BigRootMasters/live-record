import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AnchorConfigService:
    """Load fixed anchor metadata from the repository config file."""

    def __init__(self):
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config',
            'anchors.json'
        )
        self.config_path = os.getenv('ANCHOR_CONFIG_PATH', default_path)

    def list_anchors(self):
        data = self._load_raw_config()
        if data is None:
            return []
        return [self._normalize_item(item) for item in data if isinstance(item, dict)]

    def get_by_douyin_id(self, douyin_id):
        if not douyin_id:
            return None
        for item in self.list_anchors():
            if item.get('douyin_id') == douyin_id:
                return item
        return None

    def _load_raw_config(self):
        if not os.path.exists(self.config_path):
            logger.warning('Anchor config file not found: %s', self.config_path)
            return []

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as exc:
            logger.error('Failed to load anchor config %s: %s', self.config_path, exc)
            return None

        if not isinstance(data, list):
            logger.error('Anchor config must be a JSON array: %s', self.config_path)
            return None
        return data

    def _normalize_item(self, item):
        return {
            'name': (item.get('name') or '').strip(),
            'douyin_id': (item.get('douyin_id') or '').strip(),
            'anchor_id': (item.get('anchor_id') or '').strip() or None,
            'profile_url': (item.get('profile_url') or '').strip() or None,
            'live_url': (item.get('live_url') or '').strip() or None,
            'room_id': (item.get('room_id') or '').strip() or None,
            'avatar_url': (item.get('avatar_url') or '').strip() or None,
            'is_followed': item.get('is_followed', True),
            'notes': (item.get('notes') or '').strip() or None,
        }


anchor_config_service = AnchorConfigService()
