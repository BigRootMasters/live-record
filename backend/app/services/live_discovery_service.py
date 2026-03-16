import logging

from app.models import Anchor
from app.services.anchor_config_service import anchor_config_service
from app.services.douyin_live_resolver import douyin_live_resolver

logger = logging.getLogger(__name__)


class LiveDiscoveryService:
    """Discover a stable live entry URL for a configured anchor."""

    def discover_for_anchor(self, anchor: Anchor):
        config = anchor_config_service.get_by_douyin_id(anchor.douyin_id) or {}
        candidate_url = self._build_candidate_url(config)

        result = {
            'anchor': {
                'id': anchor.id,
                'name': anchor.name,
                'douyin_id': anchor.douyin_id,
            },
            'candidate_url': candidate_url,
            'config': {
                'anchor_id': config.get('anchor_id'),
                'profile_url': config.get('profile_url'),
                'live_url': config.get('live_url'),
            },
            'resolved': None,
        }

        if not candidate_url:
            result['error'] = 'No candidate url available for this anchor'
            return result

        resolved = douyin_live_resolver.resolve(candidate_url)
        result['resolved'] = resolved
        if not resolved:
            result['error'] = 'Failed to resolve candidate live url'
        return result

    def _build_candidate_url(self, config):
        if config.get('live_url'):
            return config['live_url']
        if config.get('anchor_id'):
            return f"https://live.douyin.com/{config['anchor_id']}"
        if config.get('profile_url'):
            return config['profile_url']
        return None


live_discovery_service = LiveDiscoveryService()
