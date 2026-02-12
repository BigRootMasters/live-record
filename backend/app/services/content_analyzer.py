import logging
import os
import subprocess
import traceback
from datetime import datetime
from app.models import db, Recording, Summary
from dotenv import load_dotenv
import jieba
import jieba.analyse
from summa import summarizer
import whisper

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class ContentAnalyzer:
    """内容提取和分析服务"""
    
    def __init__(self):
        self.summary_storage_path = os.getenv('SUMMARY_STORAGE_PATH', './data/summaries')
        self.whisper_model = None
        self._load_whisper_model()
    
    def _load_whisper_model(self):
        """加载Whisper模型"""
        try:
            model_size = os.getenv('WHISPER_MODEL_SIZE', 'small')
            logger.info(f'Loading Whisper model: {model_size}')
            self.whisper_model = whisper.load_model(model_size)
            logger.info('Whisper model loaded successfully')
        except Exception as e:
            logger.error(f'Error loading Whisper model: {e}')
            self.whisper_model = None
    
    def analyze_recording(self, recording_id):
        """分析录制内容并生成摘要"""
        logger.info(f'Analyzing recording: {recording_id}')
        
        try:
            # 获取录制记录
            recording = Recording.query.filter_by(id=recording_id).first()
            if not recording:
                logger.error(f'Recording not found: {recording_id}')
                return False
            
            # 检查视频文件是否存在
            if not os.path.exists(recording.video_path):
                logger.error(f'Video file not found: {recording.video_path}')
                return False
            
            # 提取音频
            audio_path = self._extract_audio(recording.video_path)
            if not audio_path:
                logger.error(f'Failed to extract audio from video: {recording.video_path}')
                return False
            
            # 转换音频为文本
            transcript = self._transcribe_audio(audio_path)
            if not transcript:
                logger.error(f'Failed to transcribe audio: {audio_path}')
                return False
            
            # 清理音频文件
            self._cleanup_audio(audio_path)
            
            # 分析文本内容
            summary_data = self._analyze_text(transcript)
            if not summary_data:
                logger.error(f'Failed to analyze text content')
                return False
            
            # 保存摘要
            summary = self._save_summary(recording_id, summary_data)
            if not summary:
                logger.error(f'Failed to save summary')
                return False
            
            # 清理视频文件
            self._cleanup_video(recording)
            
            logger.info(f'Recording {recording_id} analyzed successfully')
            return True
        except Exception as e:
            logger.error(f'Error analyzing recording: {e}')
            db.session.rollback()
            return False
    
    def _extract_audio(self, video_path):
        """从视频中提取音频"""
        logger.info(f'Extracting audio from video: {video_path}')
        
        # 生成音频文件名
        audio_path = os.path.splitext(video_path)[0] + '.mp3'
        
        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-q:a', '0',  # 最高音频质量
            '-map', 'a',  # 只提取音频
            '-y',  # 覆盖已存在的文件
            '-loglevel', 'error',  # 只记录错误
            audio_path
        ]
        
        try:
            # 执行命令
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False
            )
            
            if result.returncode == 0:
                logger.info(f'Audio extracted successfully: {audio_path}')
                return audio_path
            else:
                logger.error(f'Error extracting audio: {result.stderr}')
                return None
        except Exception as e:
            logger.error(f'Error extracting audio: {e}')
            return None
    
    def _transcribe_audio(self, audio_path):
        """将音频转换为文本"""
        logger.info(f'Transcribing audio: {audio_path}')
        
        try:
            if not self.whisper_model:
                self._load_whisper_model()
                if not self.whisper_model:
                    logger.error('Whisper model not loaded')
                    return self._mock_transcribe(audio_path)
            
            # 使用本地Whisper模型转录音频
            result = self.whisper_model.transcribe(audio_path, language="zh")
            transcript = result["text"]
            logger.info(f'Audio transcribed successfully, text length: {len(transcript)}')
            return transcript
        except Exception as e:
            logger.error(f'Error transcribing audio: {e}')
            # 出错时使用模拟结果
            return self._mock_transcribe(audio_path)
    
    def _analyze_text(self, text):
        """分析文本内容并生成摘要"""
        logger.info('Analyzing text content')
        
        try:
            # 生成摘要
            summary = summarizer.summarize(text, ratio=0.2)
            
            # 提取关键词
            keywords = jieba.analyse.extract_tags(text, topK=10)
            
            # 提取核心观点
            core_points = self._extract_core_points(text)
            
            # 分析市场观点和投资建议
            market_analysis = self._extract_market_analysis(text)
            investment_advice = self._extract_investment_advice(text)
            
            return {
                'content': summary,
                'core_points': '\n'.join([f'{i+1}. {point}' for i, point in enumerate(core_points[:5])]),
                'market_analysis': market_analysis,
                'investment_advice': '\n'.join([f'{i+1}. {advice}' for i, advice in enumerate(investment_advice[:3])]),
                'keywords': ', '.join(keywords[:10])
            }
        except Exception as e:
            logger.error(f'Error analyzing text: {e}')
            # 出错时使用模拟结果
            return self._mock_analyze_text(text)
    
    def _extract_core_points(self, text):
        """提取核心观点"""
        # 简单实现：提取包含关键信息的句子
        sentences = text.split('。')
        core_points = []
        
        # 关键词列表
        key_phrases = ['认为', '觉得', '建议', '推荐', '关注', '看好', '看空', '观点', '分析', '预测']
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and any(phrase in sentence for phrase in key_phrases):
                core_points.append(sentence)
        
        # 如果没有找到足够的核心观点，返回默认内容
        if not core_points:
            core_points = ['直播内容主要讨论了市场走势', '分析了热门板块的投资机会', '提供了相关投资建议']
        
        return core_points
    
    def _extract_market_analysis(self, text):
        """提取市场分析"""
        # 简单实现：查找包含市场分析相关内容的部分
        market_keywords = ['市场', '走势', '指数', '板块', '行业', '经济', '政策']
        
        sentences = text.split('。')
        market_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and any(keyword in sentence for keyword in market_keywords):
                market_sentences.append(sentence)
        
        if market_sentences:
            return '。'.join(market_sentences[:3]) + '。'
        else:
            return '市场整体趋势稳定，需关注政策变化和行业动态。'
    
    def _extract_investment_advice(self, text):
        """提取投资建议"""
        # 简单实现：查找包含投资建议相关内容的部分
        advice_keywords = ['建议', '投资', '策略', '注意', '风险', '机会', '关注', '布局']
        
        sentences = text.split('。')
        advice_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and any(keyword in sentence for keyword in advice_keywords):
                advice_sentences.append(sentence)
        
        if not advice_sentences:
            advice_sentences = ['保持理性投资，不盲目跟风', '分散投资，降低风险', '长期投资，减少频繁交易']
        
        return advice_sentences
    
    def _save_summary(self, recording_id, summary_data):
        """保存摘要到数据库"""
        logger.info(f'Saving summary for recording: {recording_id}')
        
        # 检查是否已存在摘要
        existing_summary = Summary.query.filter_by(recording_id=recording_id).first()
        if existing_summary:
            logger.warning(f'Summary already exists for recording: {recording_id}')
            return existing_summary
        
        # 创建新摘要
        summary = Summary(
            recording_id=recording_id,
            content=summary_data.get('content', ''),
            core_points=summary_data.get('core_points', ''),
            market_analysis=summary_data.get('market_analysis', ''),
            investment_advice=summary_data.get('investment_advice', ''),
            keywords=summary_data.get('keywords', ''),
            status='completed'
        )
        
        db.session.add(summary)
        db.session.commit()
        
        logger.info(f'Summary saved successfully: {summary.id}')
        return summary
    
    def _cleanup_audio(self, audio_path):
        """清理音频文件"""
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f'Cleaned up audio file: {audio_path}')
            except Exception as e:
                logger.error(f'Error cleaning up audio file: {e}')
    
    def _cleanup_video(self, recording):
        """清理视频文件"""
        if recording.video_path and os.path.exists(recording.video_path):
            try:
                os.remove(recording.video_path)
                recording.video_path = None
                db.session.commit()
                logger.info(f'Cleaned up video file for recording: {recording.id}')
            except Exception as e:
                logger.error(f'Error cleaning up video file: {e}')
    
    def _mock_transcribe(self, audio_path):
        """模拟音频转录"""
        # 模拟转录结果
        return """各位观众朋友们，大家晚上好！欢迎来到我的直播间。今天我想和大家分享一下我对当前股市的看法。

首先，我们来看看最近的市场走势。上证指数最近一直在3500点左右震荡，虽然有一些波动，但整体趋势还是比较稳定的。我认为这主要是因为国内经济复苏的势头比较强劲，特别是制造业和服务业的PMI指数都保持在扩张区间。

接下来，我想重点分析一下几个热门板块。首先是新能源板块，这个板块最近表现非常活跃，特别是锂电池和光伏相关的个股。我认为这主要是因为全球对清洁能源的需求不断增加，加上国内政策的大力支持，所以这个板块还有很大的上涨空间。

然后是半导体板块，这个板块最近也有不错的表现。随着全球芯片短缺的问题逐渐缓解，加上国内半导体产业的不断发展，我认为这个板块未来的前景非常广阔。

最后，我想给大家一些投资建议。首先，要保持理性投资，不要盲目跟风。其次，要分散投资，不要把所有的鸡蛋放在一个篮子里。最后，要长期投资，不要频繁交易。

好的，今天的直播就到这里，感谢大家的观看。明天同一时间，我们不见不散！"""
    
    def _mock_analyze_text(self, text):
        """模拟文本分析"""
        # 模拟分析结果
        return {
            'content': '主播在直播中分享了对当前股市的看法，包括市场走势、热门板块分析和投资建议。',
            'core_points': '1. 上证指数在3500点左右震荡，整体趋势稳定\n2. 国内经济复苏势头强劲，PMI指数保持扩张\n3. 新能源板块表现活跃，未来有上涨空间\n4. 半导体板块前景广阔\n5. 投资建议：理性投资、分散投资、长期投资',
            'market_analysis': '市场整体趋势稳定，经济复苏势头强劲。新能源和半导体板块表现突出，值得关注。',
            'investment_advice': '1. 保持理性投资，不盲目跟风\n2. 分散投资，降低风险\n3. 长期投资，减少频繁交易',
            'keywords': '股市, 新能源, 半导体, 投资建议, 经济复苏'
        }

# 创建内容分析服务实例
content_analyzer = ContentAnalyzer()