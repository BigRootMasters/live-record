import html
import json
import logging
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DouyinLiveResolver:
    """Resolve Douyin live page URLs into stream metadata."""

    def __init__(self):
        self.user_agent = os.getenv(
            'DOUYIN_USER_AGENT',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        )
        self.timeout = int(os.getenv('API_TIMEOUT', 10))

    def resolve(self, live_url):
        page_html = self._fetch_page(live_url)
        if not page_html:
            return None

        anchor_info = self._extract_json_attr(page_html, 'data-anchor-info')
        room_info = self._extract_json_attr(page_html, 'data-room-info')
        urls = self._extract_stream_urls(page_html)
        if not urls:
            logger.error('No stream urls found in Douyin live page')
            return None

        selected_hls = self._pick_preferred_url(urls.get('hls', []))
        selected_flv = self._pick_preferred_url(urls.get('flv', []))
        selected_lls = self._pick_preferred_url(urls.get('lls', []))
        title = self._extract_title(page_html)
        status = 'live' if any([selected_hls, selected_flv, selected_lls]) else 'offline'

        return {
            'anchor': anchor_info or {},
            'room': room_info or {},
            'title': title,
            'status': status,
            'selected_profile': self._infer_profile_name(selected_hls or selected_flv or selected_lls),
            'flv_url': selected_flv,
            'hls_url': selected_hls,
            'lls_url': selected_lls,
            'all_stream_urls': urls,
        }

    def _fetch_page(self, live_url):
        try:
            response = requests.get(
                live_url,
                headers={'User-Agent': self.user_agent},
                timeout=self.timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            logger.error('Failed to fetch Douyin live page %s: %s', live_url, exc)
            return None

    def _extract_json_attr(self, page_html, attr_name):
        pattern = rf'{attr_name}="([^"]+)"'
        match = re.search(pattern, page_html)
        if not match:
            return None

        raw_value = html.unescape(match.group(1))
        try:
            data = json.loads(raw_value)
        except json.JSONDecodeError:
            logger.warning('Failed to decode %s as JSON', attr_name)
            return None

        if attr_name == 'data-player':
            return self._normalize_player_data(data)
        return data

    def _extract_stream_urls(self, page_html):
        decoded_html = html.unescape(page_html)
        return {
            'hls': self._find_unique_urls(decoded_html, r'https?://[^"\'\s<>]+(?:_ld5|_sd5)?\.m3u8[^"\'\s<>]*'),
            'flv': self._find_unique_urls(decoded_html, r'https?://[^"\'\s<>]+(?:_ld5|_sd5)?\.flv[^"\'\s<>]*'),
            'lls': self._find_unique_urls(decoded_html, r'https?://[^"\'\s<>]+(?:_ld5|_sd5)?\.sdp[^"\'\s<>]*'),
        }

    def _find_unique_urls(self, text, pattern):
        urls = []
        for match in re.findall(pattern, text):
            cleaned = match.replace('&amp;', '&')
            if cleaned not in urls:
                urls.append(cleaned)
        return urls

    def _pick_preferred_url(self, urls):
        if not urls:
            return None

        quality_order = ['.m3u8?', '.flv?', '_origin', '.m3u8', '.flv', '_uhd', '_hd', '_sd5', '_ld5']
        for marker in quality_order:
            for url in urls:
                if marker in url:
                    return url
        return urls[0]

    def _infer_profile_name(self, url):
        if not url:
            return None
        lowered = url.lower()
        if '_ld' in lowered:
            return 'ld'
        if '_sd' in lowered:
            return 'sd'
        if '_hd' in lowered:
            return 'hd'
        if '_uhd' in lowered:
            return 'uhd'
        return 'origin'

    def _extract_title(self, page_html):
        decoded_html = html.unescape(page_html)
        title_match = re.search(r'"nickname":"([^"]+)"', decoded_html)
        if title_match:
            return title_match.group(1)
        og_match = re.search(r'<title>([^<]+)</title>', decoded_html)
        if og_match:
            return og_match.group(1)
        return None


douyin_live_resolver = DouyinLiveResolver()
