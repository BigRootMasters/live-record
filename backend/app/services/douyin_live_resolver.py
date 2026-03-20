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
        self.profile_headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Cookie': 's_v_web_id=verify_lk07kv74_QZYCUApD_xhiB_405x_Ax51_GYO9bUIyZQVf',
        }
        self.share_headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Cookie': 'ttwid=1%7C4ejCkU2bKY76IySQENJwvGhg1IQZrgGEupSyTKKfuyk%7C1740470403%7Cbc9ad2ee341f1a162f9e27f4641778030d1ae91e31f9df6553a8f2efa3bdb7b4; __ac_nonce=0683e59f3009cc48fbab0; __ac_signature=_02B4Z6wo00f01mG6waQAAIDB9JUCzFb6.TZhmsUAAPBf34; __ac_referer=__ac_blank',
        }

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

    def get_unique_id_from_profile(self, douyin_id=None, profile_url=None):
        """Best-effort extraction of a stable unique_id from profile information."""
        profile_entry = profile_url or self._build_profile_url(douyin_id)
        if not profile_entry:
            return None

        try:
            session = requests.Session()
            profile_response = session.get(
                profile_entry,
                headers=self.profile_headers,
                timeout=self.timeout,
                allow_redirects=True,
            )
            profile_response.raise_for_status()

            sec_user_id = profile_response.url.split('?')[0].rsplit('/', maxsplit=1)[-1]
            if not sec_user_id:
                return None

            share_response = session.get(
                f'https://www.iesdouyin.com/share/user/{sec_user_id}',
                headers=self.share_headers,
                timeout=self.timeout,
                allow_redirects=True,
            )
            share_response.raise_for_status()
            return self._extract_unique_id(share_response.text)
        except Exception as exc:
            logger.warning('Failed to derive unique_id from profile %s: %s', profile_entry, exc)
            return None

    def _build_profile_url(self, douyin_id):
        if not douyin_id:
            return None
        return f'https://www.douyin.com/user/{douyin_id}'

    def _extract_unique_id(self, page_html):
        patterns = [
            r'unique_id":"(.*?)","verification_type',
            r'"unique_id":"(.*?)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, page_html)
            if match:
                unique_id = (match.group(1) or '').strip()
                if unique_id:
                    return unique_id
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
            cleaned = cleaned.replace('\\u0026', '&')
            cleaned = cleaned.replace('\\u003d', '=')
            cleaned = cleaned.replace('\\u002f', '/')
            cleaned = cleaned.replace('\\u002F', '/')
            cleaned = cleaned.replace('\\/', '/')
            cleaned = cleaned.replace('\\', '')
            if cleaned not in urls:
                urls.append(cleaned)
        return urls

    def _pick_preferred_url(self, urls):
        if not urls:
            return None

        quality_order = ['_origin', '_uhd', '_hd', '_sd', '_ld', '.m3u8?', '.flv?', '.m3u8', '.flv']

        def score(url):
            total = 0
            if '_session_id=' in url:
                total += 100
            if url.startswith('https://'):
                total += 40
            if 'admin.douyincdn.com' in url:
                total += 20
            for idx, marker in enumerate(quality_order):
                if marker in url:
                    total += max(0, 30 - idx)
                    break
            return total

        return max(urls, key=score)

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
