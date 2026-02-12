from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler

# 加载环境变量
load_dotenv()

# 配置日志
log_file = os.getenv('LOG_FILE', './logs/app.log')
log_level = os.getenv('LOG_LEVEL', 'INFO')

# 确保日志目录存在
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# 设置日志
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
handler.setLevel(getattr(logging, log_level))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///./data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 启用CORS
CORS(app)

# 添加日志处理器
app.logger.addHandler(handler)
app.logger.setLevel(getattr(logging, log_level))

# 导入数据库和模型
from app.models import db, Anchor, Recording, Summary
db.init_app(app)

# 创建数据库表
with app.app_context():
    db.create_all()

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