from flask import Blueprint, jsonify, request, send_file
from app.models import db, Anchor, Recording, Summary
from app.services.anchor_config_service import anchor_config_service
from app.services.content_analyzer import content_analyzer
from app.services.douyin_live_resolver import douyin_live_resolver
from app.services.live_monitor import live_monitor
from app.services.live_discovery_service import live_discovery_service
from app.services.notification_service import notification_service
from app.utils.features import is_transcription_enabled
from app.utils.signed_media import resolve_media_token
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from datetime import datetime, timedelta
import os

# 创建蓝图
bp = Blueprint('api', __name__, url_prefix='/api')

# 数据库会话直接使用db.session


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
        }
    }


@bp.route('/transcription-files/<token>', methods=['GET'])
def get_transcription_file(token):
    """提供限时有效的音频文件下载地址，供转写服务回拉。"""
    file_path = resolve_media_token(token, max_age=3600)
    if not file_path:
        return jsonify({'error': 'File not found or token expired'}), 404
    return send_file(file_path, as_attachment=False, conditional=True)

# 主播管理接口

@bp.route('/anchors', methods=['GET'])
def get_anchors():
    """获取所有主播列表"""
    # 支持分页和过滤
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    is_followed = request.args.get('is_followed', type=lambda x: x.lower() == 'true')
    
    # 构建查询
    query = Anchor.query
    if is_followed is not None:
        query = query.filter_by(is_followed=is_followed)
    
    # 执行查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    anchors = pagination.items
    
    return jsonify({
        'items': [serialize_anchor(anchor) for anchor in anchors],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200

@bp.route('/anchors', methods=['POST'])
def add_anchor():
    """添加新主播"""
    data = request.json
    if not data or not data.get('name') or not data.get('douyin_id'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # 检查是否已存在
    existing_anchor = Anchor.query.filter_by(douyin_id=data['douyin_id']).first()
    if existing_anchor:
        return jsonify({'error': 'Anchor already exists'}), 400
    
    # 创建新主播
    new_anchor = Anchor(
        name=data['name'],
        douyin_id=data['douyin_id'],
        room_id=data.get('room_id'),
        avatar_url=data.get('avatar_url'),
        is_followed=data.get('is_followed', True)
    )
    
    db.session.add(new_anchor)
    db.session.commit()
    
    return jsonify({
        **serialize_anchor(new_anchor)
    }), 201

@bp.route('/anchors/<int:anchor_id>', methods=['PUT'])
def update_anchor(anchor_id):
    """更新主播信息"""
    data = request.json
    
    anchor = Anchor.query.filter_by(id=anchor_id).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found'}), 404
    
    # 更新字段
    if 'name' in data:
        anchor.name = data['name']
    if 'room_id' in data:
        anchor.room_id = data['room_id']
    if 'avatar_url' in data:
        anchor.avatar_url = data['avatar_url']
    if 'is_followed' in data:
        anchor.is_followed = data['is_followed']
    
    db.session.commit()
    
    return jsonify(serialize_anchor(anchor)), 200

@bp.route('/anchors/<int:anchor_id>', methods=['DELETE'])
def delete_anchor(anchor_id):
    """删除主播"""
    anchor = Anchor.query.filter_by(id=anchor_id).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found'}), 404
    
    db.session.delete(anchor)
    db.session.commit()
    
    return jsonify({'message': 'Anchor deleted successfully'}), 200

@bp.route('/anchors/<int:anchor_id>/discover-live', methods=['GET'])
def discover_anchor_live(anchor_id):
    """根据固定主播身份自动发现当前直播入口"""
    anchor = Anchor.query.filter_by(id=anchor_id).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found'}), 404

    result = live_discovery_service.discover_for_anchor(anchor)
    status_code = 200 if not result.get('error') else 200
    return jsonify(result), status_code

@bp.route('/anchors/<int:anchor_id>/start-recording', methods=['POST'])
def start_anchor_recording(anchor_id):
    """手动触发主播的直播发现与录制启动"""
    anchor = Anchor.query.filter_by(id=anchor_id, is_followed=True).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found or not followed'}), 404

    existing_recording = Recording.query.filter_by(
        anchor_id=anchor.id,
        status='recording'
    ).order_by(desc(Recording.start_time)).first()
    if existing_recording:
        return jsonify({
            'success': True,
            'message': 'Recording already in progress',
            'anchor_id': anchor.id,
            'recording_id': existing_recording.id
        }), 200

    is_live, live_info = live_monitor._check_live_status(anchor)
    if not is_live:
        return jsonify({
            'success': False,
            'message': 'Anchor is not live',
            'anchor_id': anchor.id,
            'live_info': live_info
        }), 200

    recording = live_monitor.start_recording(anchor, live_info)
    if not recording:
        return jsonify({
            'success': False,
            'message': 'Failed to start recording',
            'anchor_id': anchor.id,
            'live_info': live_info
        }), 500

    return jsonify({
        'success': True,
        'message': 'Recording started',
        'anchor_id': anchor.id,
        'recording_id': recording.id,
        'live_info': live_info
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
            'status': recording.status
        }), 200

    stop_result = live_monitor.stop_recording(recording)
    refreshed = Recording.query.options(joinedload(Recording.summary)).filter_by(id=recording_id).first()

    if refreshed.status != 'completed':
        return jsonify({
            'success': False,
            'message': 'Recording stopped but post-processing did not complete',
            'recording_id': refreshed.id,
            'status': refreshed.status,
            'end_time': refreshed.end_time.isoformat() if refreshed.end_time else None,
            'video_duration': refreshed.video_duration
        }), 500

    if not is_transcription_enabled():
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
            'summary_status': None
        }), 200

    transcription_success = content_analyzer.analyze_recording(recording_id)
    refreshed = Recording.query.options(joinedload(Recording.summary)).filter_by(id=recording_id).first()

    return jsonify({
        'success': transcription_success,
        'message': 'Recording stopped and transcribed' if transcription_success else 'Recording stopped but transcription failed',
        'recording_id': refreshed.id,
        'status': refreshed.status,
        'end_time': refreshed.end_time.isoformat() if refreshed.end_time else None,
        'video_duration': refreshed.video_duration,
        'summary_id': refreshed.summary.id if refreshed.summary else None,
        'summary_status': refreshed.summary.status if refreshed.summary else None
    }), 200 if transcription_success else 500

# 录制管理接口

@bp.route('/recordings', methods=['GET'])
def get_recordings():
    """获取所有录制记录"""
    # 支持分页和过滤
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    anchor_id = request.args.get('anchor_id', type=int)
    status = request.args.get('status')
    
    # 构建查询
    query = Recording.query
    if anchor_id:
        query = query.filter_by(anchor_id=anchor_id)
    if status:
        query = query.filter_by(status=status)
    
    # 按开始时间倒序排列
    query = query.order_by(desc(Recording.start_time))
    
    # 执行查询
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
                'douyin_id': recording.anchor.douyin_id
            } if recording.anchor else None
        } for recording in recordings],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200

@bp.route('/recordings/<int:recording_id>', methods=['GET'])
def get_recording(recording_id):
    """获取单个录制记录详情"""
    recording = Recording.query.options(
        joinedload(Recording.anchor),
        joinedload(Recording.summary)
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
            'douyin_id': recording.anchor.douyin_id
        } if recording.anchor else None,
        'summary': {
            'id': recording.summary.id,
            'content': recording.summary.content,
            'core_points': recording.summary.core_points,
            'market_analysis': recording.summary.market_analysis,
            'investment_advice': recording.summary.investment_advice,
            'keywords': recording.summary.keywords,
            'status': recording.summary.status,
            'transcript_length': len(recording.summary.content or '')
        } if recording.summary else None
    }), 200

@bp.route('/recordings/<int:recording_id>/transcribe', methods=['POST'])
def transcribe_recording(recording_id):
    """手动触发某条录制的转写流程"""
    if not is_transcription_enabled():
        return jsonify({
            'success': False,
            'message': 'Transcription is disabled in record-only mode'
        }), 409

    recording = Recording.query.filter_by(id=recording_id).first()
    if not recording:
        return jsonify({'error': 'Recording not found'}), 404

    if recording.status == 'recording':
        return jsonify({'error': 'Recording is still in progress'}), 400

    success = content_analyzer.analyze_recording(recording_id)
    if not success:
        db.session.refresh(recording)
        return jsonify({
            'success': False,
            'message': 'Transcription failed',
            'recording_id': recording.id,
            'status': recording.status
        }), 500

    updated_recording = Recording.query.options(joinedload(Recording.summary)).filter_by(id=recording_id).first()
    return jsonify({
        'success': True,
        'message': 'Transcription completed',
        'recording_id': updated_recording.id,
        'status': updated_recording.status,
        'summary_id': updated_recording.summary.id if updated_recording and updated_recording.summary else None
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
        status='completed'
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
        'status': recording.status
    }), 201

# 摘要管理接口

@bp.route('/summaries', methods=['GET'])
def get_summaries():
    """获取所有摘要列表"""
    # 支持分页和过滤
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    anchor_id = request.args.get('anchor_id', type=int)
    
    # 构建查询
    query = Summary.query.join(Recording)
    if anchor_id:
        query = query.filter(Recording.anchor_id == anchor_id)
    
    # 按创建时间倒序排列
    query = query.order_by(desc(Summary.created_at))
    
    # 执行查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    summaries = pagination.items
    
    return jsonify({
        'items': [{
            'id': summary.id,
            'recording_id': summary.recording_id,
            'content': summary.content,
            'content_preview': (summary.content or '')[:120],
            'transcript_length': len(summary.content or ''),
            'core_points': summary.core_points,
            'market_analysis': summary.market_analysis,
            'investment_advice': summary.investment_advice,
            'keywords': summary.keywords,
            'status': summary.status,
            'created_at': summary.created_at.isoformat() if summary.created_at else None,
            'updated_at': summary.updated_at.isoformat() if summary.updated_at else None,
            'recording': {
                'id': summary.recording.id,
                'start_time': summary.recording.start_time.isoformat() if summary.recording.start_time else None,
                'anchor': {
                    'id': summary.recording.anchor.id,
                    'name': summary.recording.anchor.name
                } if summary.recording.anchor else None
            } if summary.recording else None
        } for summary in summaries],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200

@bp.route('/summaries/<int:summary_id>', methods=['GET'])
def get_summary(summary_id):
    """获取单个摘要详情"""
    summary = Summary.query.options(
        joinedload(Summary.recording).joinedload(Recording.anchor)
    ).filter_by(id=summary_id).first()
    if not summary:
        return jsonify({'error': 'Summary not found'}), 404
    
    return jsonify({
        'id': summary.id,
        'recording_id': summary.recording_id,
        'content': summary.content,
        'transcript_length': len(summary.content or ''),
        'core_points': summary.core_points,
        'market_analysis': summary.market_analysis,
        'investment_advice': summary.investment_advice,
        'keywords': summary.keywords,
        'status': summary.status,
        'created_at': summary.created_at.isoformat() if summary.created_at else None,
        'updated_at': summary.updated_at.isoformat() if summary.updated_at else None,
        'recording': {
            'id': summary.recording.id,
            'start_time': summary.recording.start_time.isoformat() if summary.recording.start_time else None,
            'end_time': summary.recording.end_time.isoformat() if summary.recording.end_time else None,
            'anchor': {
                'id': summary.recording.anchor.id,
                'name': summary.recording.anchor.name,
                'douyin_id': summary.recording.anchor.douyin_id
            } if summary.recording.anchor else None
        } if summary.recording else None
    }), 200

@bp.route('/summaries/<int:summary_id>/notify', methods=['POST'])
def notify_summary(summary_id):
    """手动发送某份文字稿的企业微信通知"""
    summary = Summary.query.filter_by(id=summary_id).first()
    if not summary:
        return jsonify({'error': 'Summary not found'}), 404

    success = notification_service.send_summary(summary_id)
    if not success:
        db.session.refresh(summary)
        return jsonify({
            'success': False,
            'message': 'Notification failed',
            'summary_id': summary.id,
            'status': summary.status
        }), 500

    refreshed_summary = Summary.query.filter_by(id=summary_id).first()
    return jsonify({
        'success': True,
        'message': 'Notification sent',
        'summary_id': refreshed_summary.id,
        'status': refreshed_summary.status
    }), 200

# 系统状态接口

@bp.route('/live/resolve', methods=['POST'])
def resolve_live_url():
    """解析抖音直播间页面并返回可用流地址"""
    data = request.json or {}
    live_url = data.get('live_url')
    if not live_url:
        return jsonify({'error': 'live_url is required'}), 400

    result = douyin_live_resolver.resolve(live_url)
    if not result:
        return jsonify({'error': 'Failed to resolve live url'}), 500

    return jsonify(result), 200

@bp.route('/system/status', methods=['GET'])
def get_system_status():
    """获取系统状态"""
    # 检查存储使用情况
    video_storage_path = os.getenv('VIDEO_STORAGE_PATH', './data/temp_videos')
    summary_storage_path = os.getenv('SUMMARY_STORAGE_PATH', './data/summaries')
    
    # 计算存储使用情况
    def get_directory_size(path):
        total_size = 0
        if os.path.exists(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        return total_size
    
    video_size = get_directory_size(video_storage_path)
    summary_size = get_directory_size(summary_storage_path)
    total_size = video_size + summary_size
    
    # 获取数据库统计信息
    anchor_count = Anchor.query.count()
    recording_count = Recording.query.count()
    summary_count = Summary.query.count()
    
    return jsonify({
        'features': {
            'transcription_enabled': is_transcription_enabled()
        },
        'storage': {
            'video_size': video_size,
            'summary_size': summary_size,
            'total_size': total_size,
            'unit': 'bytes'
        },
        'database': {
            'anchor_count': anchor_count,
            'recording_count': recording_count,
            'summary_count': summary_count
        },
        'timestamp': datetime.now().isoformat()
    }), 200
