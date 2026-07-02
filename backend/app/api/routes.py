import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app.models import Anchor, Recording, db
from app.services.anchor_config_service import anchor_config_service
from app.services.anchor_sync_service import anchor_sync_service
from app.services.douyin_live_resolver import douyin_live_resolver
from app.services.live_discovery_service import live_discovery_service
from app.services.live_monitor import live_monitor
from app.services.notification_service import notification_service

bp = Blueprint('api', __name__, url_prefix='/api')
ALLOWED_LIVE_RESOLVE_HOSTS = (
    'douyin.com',
    '.douyin.com',
    'iesdouyin.com',
    '.iesdouyin.com',
)


def _get_api_auth_token():
    return (os.getenv('API_AUTH_TOKEN') or '').strip()


def _get_request_api_token():
    bearer_token = (request.headers.get('Authorization') or '').strip()
    if bearer_token.lower().startswith('bearer '):
        return bearer_token[7:].strip()
    return (request.headers.get('X-API-Token') or '').strip()


def _config_managed_anchor_response():
    return jsonify({
        'error': 'Anchors are managed by config file only',
        'message': 'Edit backend/config/anchors.json and call POST /api/anchors/reload to apply changes.',
        'config_path': anchor_config_service.config_path,
    }), 409


def _is_allowed_live_url(live_url):
    try:
        parsed = urlparse((live_url or '').strip())
    except Exception:
        return False

    if parsed.scheme not in {'http', 'https'}:
        return False

    hostname = (parsed.hostname or '').lower()
    if not hostname:
        return False

    return any(
        hostname == allowed.lstrip('.') or hostname.endswith(allowed)
        for allowed in ALLOWED_LIVE_RESOLVE_HOSTS
    )


def _get_allowed_live_resolve_hosts():
    return sorted({host.lstrip('.') for host in ALLOWED_LIVE_RESOLVE_HOSTS})


@bp.before_request
def require_api_auth():
    configured_token = _get_api_auth_token()
    if not configured_token or request.method == 'OPTIONS':
        return None

    request_token = _get_request_api_token()
    if request_token == configured_token:
        return None

    return jsonify({'error': 'Unauthorized'}), 401


def serialize_anchor(anchor):
    config = anchor_config_service.get_by_douyin_id(anchor.douyin_id) or {}
    return {
        'id': anchor.id,
        'name': anchor.name,
        'douyin_id': anchor.douyin_id,
        'room_id': anchor.room_id,
        'avatar_url': anchor.avatar_url,
        'is_followed': anchor.is_followed,
        'created_at': anchor.created_at.isoformat() if anchor.created_at else None,
        'updated_at': anchor.updated_at.isoformat() if anchor.updated_at else None,
        'config': {
            'anchor_id': config.get('anchor_id'),
            'profile_url': config.get('profile_url'),
            'live_url': config.get('live_url'),
            'notes': config.get('notes'),
        },
    }


@bp.route('/anchors', methods=['GET'])
def get_anchors():
    """获取所有主播列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    is_followed = request.args.get('is_followed', type=lambda x: x.lower() == 'true')

    query = Anchor.query
    if is_followed is not None:
        query = query.filter_by(is_followed=is_followed)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    anchors = pagination.items

    return jsonify({
        'items': [serialize_anchor(anchor) for anchor in anchors],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    }), 200


@bp.route('/anchors', methods=['POST'])
def add_anchor():
    """主播由配置文件统一管理。"""
    return _config_managed_anchor_response()


@bp.route('/anchors/<int:anchor_id>', methods=['PUT'])
def update_anchor(anchor_id):
    """主播由配置文件统一管理。"""
    return _config_managed_anchor_response()


@bp.route('/anchors/<int:anchor_id>', methods=['DELETE'])
def delete_anchor(anchor_id):
    """主播由配置文件统一管理。"""
    return _config_managed_anchor_response()


@bp.route('/anchors/reload', methods=['POST'])
def reload_anchors():
    """重新同步 anchors.json 到运行时数据库。"""
    result = anchor_sync_service.sync()
    return jsonify({
        'success': True,
        'message': 'Anchor config reloaded successfully',
        **result,
    }), 200


@bp.route('/anchors/<int:anchor_id>/discover-live', methods=['GET'])
def discover_anchor_live(anchor_id):
    """根据固定主播身份自动发现当前直播入口"""
    anchor = Anchor.query.filter_by(id=anchor_id).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found'}), 404

    result = live_discovery_service.discover_for_anchor(anchor)
    return jsonify(result), 200


@bp.route('/anchors/<int:anchor_id>/start-recording', methods=['POST'])
def start_anchor_recording(anchor_id):
    """手动触发主播的直播发现与录制启动"""
    anchor = Anchor.query.filter_by(id=anchor_id, is_followed=True).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found or not followed'}), 404

    existing_recording = Recording.query.filter_by(
        anchor_id=anchor.id,
        status='recording',
    ).order_by(desc(Recording.start_time)).first()
    if existing_recording:
        return jsonify({
            'success': True,
            'message': 'Recording already in progress',
            'anchor_id': anchor.id,
            'recording_id': existing_recording.id,
        }), 200

    is_live, live_info = live_monitor._check_live_status(anchor)
    if not is_live:
        return jsonify({
            'success': False,
            'message': 'Anchor is not live',
            'anchor_id': anchor.id,
            'live_info': live_info,
        }), 200

    recording = live_monitor.start_recording(anchor, live_info)
    if not recording:
        return jsonify({
            'success': False,
            'message': 'Failed to start recording',
            'anchor_id': anchor.id,
            'live_info': live_info,
        }), 500

    return jsonify({
        'success': True,
        'message': 'Recording started',
        'anchor_id': anchor.id,
        'recording_id': recording.id,
        'live_info': live_info,
    }), 200


@bp.route('/recordings/<int:recording_id>/stop', methods=['POST'])
def stop_recording(recording_id):
    """手动停止一条正在进行的录制"""
    recording = Recording.query.filter_by(id=recording_id).first()
    if not recording:
        return jsonify({'error': 'Recording not found'}), 404

    if recording.status != 'recording':
        return jsonify({
            'success': False,
            'message': 'Recording is not active',
            'recording_id': recording.id,
            'status': recording.status,
        }), 200

    stop_result = live_monitor.stop_recording(recording)
    refreshed = Recording.query.filter_by(id=recording_id).first()

    if not refreshed or refreshed.status != 'completed':
        return jsonify({
            'success': False,
            'message': 'Recording stopped but post-processing did not complete',
            'recording_id': recording_id,
            'status': refreshed.status if refreshed else None,
            'end_time': refreshed.end_time.isoformat() if refreshed and refreshed.end_time else None,
            'video_duration': refreshed.video_duration if refreshed else None,
        }), 500

    audio_sent = bool((stop_result or {}).get('audio_sent'))
    return jsonify({
        'success': True,
        'message': 'Recording stopped and audio sent to Wechat' if audio_sent else 'Recording stopped successfully',
        'recording_id': refreshed.id,
        'status': refreshed.status,
        'end_time': refreshed.end_time.isoformat() if refreshed.end_time else None,
        'video_duration': refreshed.video_duration,
        'audio_notification_sent': audio_sent,
        'summary_id': None,
        'summary_status': None,
    }), 200


@bp.route('/recordings', methods=['GET'])
def get_recordings():
    """获取所有录制记录"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    anchor_id = request.args.get('anchor_id', type=int)
    status = request.args.get('status')

    query = Recording.query
    if anchor_id:
        query = query.filter_by(anchor_id=anchor_id)
    if status:
        query = query.filter_by(status=status)

    query = query.order_by(desc(Recording.start_time))
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    recordings = pagination.items

    return jsonify({
        'items': [{
            'id': recording.id,
            'anchor_id': recording.anchor_id,
            'video_path': recording.video_path,
            'video_duration': recording.video_duration,
            'start_time': recording.start_time.isoformat() if recording.start_time else None,
            'end_time': recording.end_time.isoformat() if recording.end_time else None,
            'status': recording.status,
            'created_at': recording.created_at.isoformat() if recording.created_at else None,
            'updated_at': recording.updated_at.isoformat() if recording.updated_at else None,
            'anchor': {
                'id': recording.anchor.id,
                'name': recording.anchor.name,
                'douyin_id': recording.anchor.douyin_id,
            } if recording.anchor else None,
        } for recording in recordings],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    }), 200


@bp.route('/recordings/<int:recording_id>', methods=['GET'])
def get_recording(recording_id):
    """获取单个录制记录详情"""
    recording = Recording.query.options(
        joinedload(Recording.anchor),
    ).filter_by(id=recording_id).first()
    if not recording:
        return jsonify({'error': 'Recording not found'}), 404

    return jsonify({
        'id': recording.id,
        'anchor_id': recording.anchor_id,
        'video_path': recording.video_path,
        'video_duration': recording.video_duration,
        'start_time': recording.start_time.isoformat() if recording.start_time else None,
        'end_time': recording.end_time.isoformat() if recording.end_time else None,
        'status': recording.status,
        'created_at': recording.created_at.isoformat() if recording.created_at else None,
        'updated_at': recording.updated_at.isoformat() if recording.updated_at else None,
        'anchor': {
            'id': recording.anchor.id,
            'name': recording.anchor.name,
            'douyin_id': recording.anchor.douyin_id,
        } if recording.anchor else None,
        'summary': None,
    }), 200


@bp.route('/recordings/test', methods=['POST'])
def create_test_recording():
    """创建一条用于自测的录制记录"""
    data = request.json or {}
    anchor_id = data.get('anchor_id')
    video_path = data.get('video_path')
    start_time_raw = data.get('start_time')
    duration_seconds = data.get('duration_seconds', 3600)

    if not anchor_id or not video_path:
        return jsonify({'error': 'anchor_id and video_path are required'}), 400

    anchor = Anchor.query.filter_by(id=anchor_id).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found'}), 404

    if not os.path.exists(video_path):
        return jsonify({'error': f'Video file not found: {video_path}'}), 400

    try:
        if start_time_raw:
            start_time = datetime.fromisoformat(start_time_raw)
        else:
            start_time = datetime.now() - timedelta(seconds=duration_seconds)
    except ValueError:
        return jsonify({'error': 'start_time must be ISO format'}), 400

    recording = Recording(
        anchor_id=anchor.id,
        video_path=video_path,
        video_duration=duration_seconds,
        start_time=start_time,
        end_time=start_time + timedelta(seconds=duration_seconds),
        status='completed',
    )

    db.session.add(recording)
    db.session.commit()

    return jsonify({
        'id': recording.id,
        'anchor_id': recording.anchor_id,
        'video_path': recording.video_path,
        'video_duration': recording.video_duration,
        'start_time': recording.start_time.isoformat() if recording.start_time else None,
        'end_time': recording.end_time.isoformat() if recording.end_time else None,
        'status': recording.status,
    }), 201


@bp.route('/live/resolve', methods=['POST'])
def resolve_live_url():
    """解析抖音直播间页面并返回可用流地址"""
    data = request.json or {}
    live_url = data.get('live_url')
    if not live_url:
        return jsonify({'error': 'live_url is required'}), 400
    if not _is_allowed_live_url(live_url):
        return jsonify({
            'error': 'live_url must be a Douyin live or profile URL',
            'allowed_hosts': _get_allowed_live_resolve_hosts(),
        }), 400

    result = douyin_live_resolver.resolve(live_url)
    if not result:
        return jsonify({'error': 'Failed to resolve live url'}), 500

    return jsonify(result), 200


@bp.route('/system/status', methods=['GET'])
def get_system_status():
    """获取系统状态"""
    video_storage_path = os.getenv('VIDEO_STORAGE_PATH', './data/recordings')

    def get_directory_size(path):
        total_size = 0
        if os.path.exists(path):
            for dirpath, _dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        return total_size

    video_size = get_directory_size(video_storage_path)
    anchor_count = Anchor.query.count()
    recording_count = Recording.query.count()

    return jsonify({
        'features': {
            'transcription_enabled': False,
            'recording_mode': os.getenv('RECORDING_MODE', 'video'),
            'audio_notification_enabled': notification_service.auto_send_recording_audio,
            'api_auth_enabled': bool(_get_api_auth_token()),
        },
        'storage': {
            'video_size': video_size,
            'summary_size': 0,
            'total_size': video_size,
            'unit': 'bytes',
        },
        'database': {
            'anchor_count': anchor_count,
            'recording_count': recording_count,
            'summary_count': 0,
        },
        'timestamp': datetime.now().isoformat(),
    }), 200
