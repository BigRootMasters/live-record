from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from flask_sqlalchemy import SQLAlchemy

# 创建数据库实例
db = SQLAlchemy()

class Anchor(db.Model):
    """主播信息模型"""
    __tablename__ = 'anchors'
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String(100), nullable=False)  # 主播名称
    douyin_id = db.Column(db.String(100), unique=True, nullable=False)  # 抖音ID
    room_id = db.Column(db.String(100), nullable=True)  # 直播间ID
    avatar_url = db.Column(db.String(255), nullable=True)  # 头像URL
    is_followed = db.Column(db.Boolean, default=True)  # 是否关注
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    
    # 关系
    recordings = db.relationship('Recording', back_populates='anchor')

class Recording(db.Model):
    """录制记录模型"""
    __tablename__ = 'recordings'
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    anchor_id = db.Column(db.Integer, db.ForeignKey('anchors.id'), nullable=False)
    video_path = db.Column(db.String(255), nullable=False)  # 视频存储路径
    video_duration = db.Column(db.Integer, nullable=True)  # 视频时长（秒）
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)  # 开始录制时间
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)  # 结束录制时间
    status = db.Column(db.String(20), default='pending')  # 状态：pending, recording, completed, failed
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    
    # 关系
    anchor = db.relationship('Anchor', back_populates='recordings')
    summary = db.relationship('Summary', back_populates='recording', uselist=False)

class Summary(db.Model):
    """内容摘要模型"""
    __tablename__ = 'summaries'
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    recording_id = db.Column(db.Integer, db.ForeignKey('recordings.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)  # 摘要内容
    core_points = db.Column(db.Text, nullable=True)  # 核心观点
    market_analysis = db.Column(db.Text, nullable=True)  # 市场分析
    investment_advice = db.Column(db.Text, nullable=True)  # 投资建议
    keywords = db.Column(db.String(255), nullable=True)  # 关键词
    status = db.Column(db.String(20), default='pending')  # 状态：pending, processing, completed, failed
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    
    # 关系
    recording = db.relationship('Recording', back_populates='summary')