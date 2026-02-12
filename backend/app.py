from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging
import traceback
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

# 加载环境变量
load_dotenv()

# 配置日志
log_file = os.getenv('LOG_FILE', './logs/app.log')
log_level = os.getenv('LOG_LEVEL', 'INFO')

# 确保日志目录存在
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# 设置日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(thread)d - %(message)s'
)

# 文件日志处理器（大小轮转）
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=10*1024*1024, 
    backupCount=5
)
file_handler.setLevel(getattr(logging, log_level))
file_handler.setFormatter(formatter)

# 控制台日志处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, log_level))
console_handler.setFormatter(formatter)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///./data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 启用CORS
CORS(app)

# 配置应用日志
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(getattr(logging, log_level))

# 配置根日志
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
root_logger.setLevel(getattr(logging, log_level))

# 导入数据库和模型
from app.models import db, Anchor, Recording, Summary
db.init_app(app)

# 创建数据库表
with app.app_context():
    db.create_all()

# 全局错误处理
@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f'404 Error: {request.path}')
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'500 Error: {traceback.format_exc()}')
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def general_error(error):
    app.logger.error(f'General Error: {traceback.format_exc()}')
    return jsonify({'error': 'An unexpected error occurred'}), 500

# 导入API路由
from app.api import routes
app.register_blueprint(routes.bp)

# 健康检查接口
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Service is running'}), 200

# 根路径
@app.route('/', methods=['GET'])
def index():
    return jsonify({'message': 'Welcome to Douyin Live Recorder API'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)