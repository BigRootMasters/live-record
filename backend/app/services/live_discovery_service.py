import logging

from app.models import Anchor
from app.services.anchor_config_service import anchor_config_service
from app.services.douyin_live_resolver import douyin_live_resolver

logger = logging.getLogger(__name__)


class LiveDiscoveryService:
    """Discover a stable live entry URL for a configured anchor."""

    def discover_for_anchor(self, anchor: Anchor):
        config = anchor_config_service.get_by_douyin_id(anchor.douyin_id) or {}
        unique_id = self._get_unique_id(anchor, config)
        candidate_urls = self._build_candidate_urls(anchor, config, unique_id=unique_id)
        attempts = []
        offline_resolved = None
        offline_candidate_url = None

        result = {
            'anchor': {
                'id': anchor.id,
                'name': anchor.name,
                'douyin_id': anchor.douyin_id,
            },
            'candidate_url': candidate_urls[0] if candidate_urls else None,
            'candidate_urls': candidate_urls,
            'config': {
                'anchor_id': config.get('anchor_id'),
                'profile_url': config.get('profile_url'),
                'live_url': config.get('live_url'),
            },
            'derived': {
                'unique_id': unique_id,
            },
            'attempts': attempts,
            'resolved': None,
        }

        if not candidate_urls:
            result['error'] = 'No candidate url available for this anchor'
            return result

        for candidate_url in candidate_urls:
            resolved = douyin_live_resolver.resolve(candidate_url)
            attempt = {
                'candidate_url': candidate_url,
                'resolved': bool(resolved),
                'status': resolved.get('status') if resolved else None,
                'has_stream': bool(resolved and any([
                    resolved.get('flv_url'),
                    resolved.get('hls_url'),
                    resolved.get('lls_url'),
                ])),
            }
            attempts.append(attempt)

            if resolved and attempt['has_stream']:
                result['resolved'] = resolved
                result['resolved_candidate_url'] = candidate_url
                return result

            if resolved and resolved.get('status') == 'offline' and offline_resolved is None:
                offline_resolved = resolved
                offline_candidate_url = candidate_url

        if offline_resolved:
            result['resolved'] = offline_resolved
            result['resolved_candidate_url'] = offline_candidate_url
            return result

        if attempts:
            last_attempt = attempts[-1]
            result['resolved_candidate_url'] = last_attempt['candidate_url']
        result['error'] = 'Failed to resolve candidate live url'
        return result

    def _build_candidate_urls(self, anchor, config, unique_id=None):
        candidates = []

        for candidate in [
            config.get('live_url'),
            f"https://live.douyin.com/{unique_id}" if unique_id else None,
            f"https://live.douyin.com/{anchor.douyin_id}" if anchor.douyin_id and not anchor.douyin_id.startswith('MS4') else None,
            f"https://live.douyin.com/{config['anchor_id']}" if config.get('anchor_id') else None,
            config.get('profile_url'),
            f"https://www.douyin.com/user/{anchor.douyin_id}" if anchor.douyin_id else None,
        ]:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        return candidates

    def _get_unique_id(self, anchor, config):
        profile_url = config.get('profile_url')
        return douyin_live_resolver.get_unique_id_from_profile(
            douyin_id=anchor.douyin_id,
            profile_url=profile_url,
        )


live_discovery_service = LiveDiscoveryService()
