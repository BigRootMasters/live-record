from flask import Blueprint, jsonify, request
from app.models import db, Anchor, Recording, Summary
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from datetime import datetime
import os

# 创建蓝图
bp = Blueprint('api', __name__, url_prefix='/api')

# 数据库会话直接使用db.session

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
        'items': [{
            'id': anchor.id,
            'name': anchor.name,
            'douyin_id': anchor.douyin_id,
            'room_id': anchor.room_id,
            'avatar_url': anchor.avatar_url,
            'is_followed': anchor.is_followed,
            'created_at': anchor.created_at.isoformat() if anchor.created_at else None,
            'updated_at': anchor.updated_at.isoformat() if anchor.updated_at else None
        } for anchor in anchors],
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
        'id': new_anchor.id,
        'name': new_anchor.name,
        'douyin_id': new_anchor.douyin_id,
        'room_id': new_anchor.room_id,
        'avatar_url': new_anchor.avatar_url,
        'is_followed': new_anchor.is_followed,
        'created_at': new_anchor.created_at.isoformat() if new_anchor.created_at else None
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
    
    return jsonify({
        'id': anchor.id,
        'name': anchor.name,
        'douyin_id': anchor.douyin_id,
        'room_id': anchor.room_id,
        'avatar_url': anchor.avatar_url,
        'is_followed': anchor.is_followed,
        'updated_at': anchor.updated_at.isoformat() if anchor.updated_at else None
    }), 200

@bp.route('/anchors/<int:anchor_id>', methods=['DELETE'])
def delete_anchor(anchor_id):
    """删除主播"""
    anchor = Anchor.query.filter_by(id=anchor_id).first()
    if not anchor:
        return jsonify({'error': 'Anchor not found'}), 404
    
    db.session.delete(anchor)
    db.session.commit()
    
    return jsonify({'message': 'Anchor deleted successfully'}), 200

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
            'updated_at': recording.updated_at.isoformat() if recording.updated_at else None
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
            'status': recording.summary.status
        } if recording.summary else None
    }), 200

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

# 系统状态接口

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