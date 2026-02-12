from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, deferred

from flask_sqlalchemy import SQLAlchemy

# 创建数据库实例
db = SQLAlchemy()

class Anchor(db.Model):
    """主播信息模型"""
    __tablename__ = 'anchors'
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String(100), nullable=False)  # 主播名称
    douyin_id = db.Column(db.String(100), unique=True, nullable=False, index=True)  # 抖音ID
    room_id = db.Column(db.String(100), nullable=True, index=True)  # 直播间ID
    avatar_url = db.Column(db.String(255), nullable=True)
    is_followed = db.Column(db.Boolean, default=True, index=True)  # 是否关注
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    
    # 关系
    recordings = db.relationship('Recording', back_populates='anchor', lazy='dynamic')

class Recording(db.Model):
    """录制记录模型"""
    __tablename__ = 'recordings'
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    anchor_id = db.Column(db.Integer, db.ForeignKey('anchors.id'), nullable=False, index=True)
    video_path = db.Column(db.String(255), nullable=False)
    video_duration = db.Column(db.Integer, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    status = db.Column(db.String(20), default='pending', index=True)  # 状态：pending, recording, completed, failed
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    
    # 关系
    anchor = db.relationship('Anchor', back_populates='recordings', lazy='joined')
    summary = db.relationship('Summary', back_populates='recording', uselist=False, lazy='joined')

class Summary(db.Model):
    """内容摘要模型"""
    __tablename__ = 'summaries'
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    recording_id = db.Column(db.Integer, db.ForeignKey('recordings.id'), nullable=False, index=True)
    content = deferred(db.Column(db.Text, nullable=False))  # 延迟加载大文本
    core_points = deferred(db.Column(db.Text, nullable=True))  # 延迟加载大文本
    market_analysis = deferred(db.Column(db.Text, nullable=True))  # 延迟加载大文本
    investment_advice = deferred(db.Column(db.Text, nullable=True))  # 延迟加载大文本
    keywords = db.Column(db.String(255), nullable=True, index=True)
    status = db.Column(db.String(20), default='pending', index=True)  # 状态：pending, processing, completed, failed
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    
    # 关系
    recording = db.relationship('Recording', back_populates='summary', lazy='joined')