# 阿里云服务器部署指南

本文档详细说明如何将抖音财经主播直播录制系统部署到阿里云服务器。

## 一、服务器准备

### 1. 登录阿里云服务器

使用SSH工具（如PuTTY、Xshell等）登录到您的阿里云服务器。

```bash
ssh root@your_server_ip
```

### 2. 安装必要的系统依赖

```bash
# 更新系统
apt update && apt upgrade -y

# 安装必要的软件包
apt install -y python3 python3-pip python3-venv ffmpeg git

# 安装FFmpeg（用于视频处理）
apt install -y ffmpeg
```

## 二、项目部署

### 1. 克隆项目代码

```bash
# 进入合适的目录
cd /opt

# 克隆项目代码
git clone https://github.com/your_username/live-record.git

# 进入项目目录
cd live-record/backend
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制.env文件
cp .env.example .env

# 编辑.env文件，填写相关配置
nano .env
```

在.env文件中填写以下配置：

```
# 系统配置
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your_secret_key_here

# 数据库配置
DATABASE_URL=sqlite:///./data.db

# 视频存储配置
VIDEO_STORAGE_PATH=./data/videos
SUMMARY_STORAGE_PATH=./data/summaries

# 抖音配置
DOUYIN_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36

# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo

# 邮件配置
EMAIL_SMTP_SERVER=smtp.qq.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=your_email@qq.com
EMAIL_PASSWORD=your_email_password_here
EMAIL_RECIPIENTS=your_recipient_email@example.com

# 微信机器人配置
WECHAT_WEBHOOK_URL=your_wechat_webhook_url_here

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# 定时任务配置
CHECK_INTERVAL=300  # 检查主播是否开播的间隔（秒）
RECORDING_QUALITY=720p  # 录制质量
SUMMARY_SEND_TIME=08:00  # 摘要发送时间
```

### 4. 创建必要的目录

```bash
# 创建数据存储目录
mkdir -p data/videos data/summaries logs

# 设置目录权限
chmod -R 755 data logs
```

### 5. 配置Gunicorn（生产环境WSGI服务器）

```bash
# 安装Gunicorn
pip install gunicorn

# 创建Gunicorn配置文件
nano gunicorn.conf.py
```

在gunicorn.conf.py文件中添加以下内容：

```python
# Gunicorn配置文件
import multiprocessing

bind = "0.0.0.0:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 2
timeout = 300
accesslog = "./logs/gunicorn_access.log"
errorlog = "./logs/gunicorn_error.log"
loglevel = "info"
```

## 三、服务管理

### 1. 创建Systemd服务文件

```bash
# 创建服务文件
nano /etc/systemd/system/live-record.service
```

在live-record.service文件中添加以下内容：

```ini
[Unit]
Description=Douyin Live Recorder Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/live-record/backend
Environment="PATH=/opt/live-record/backend/venv/bin"
ExecStart=/opt/live-record/backend/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2. 启动服务

```bash
# 重新加载Systemd配置
systemctl daemon-reload

# 启动服务
systemctl start live-record

# 查看服务状态
systemctl status live-record

# 设置服务开机自启
systemctl enable live-record
```

### 3. 查看服务日志

```bash
# 查看服务日志
journalctl -u live-record -f

# 查看应用日志
tail -f ./logs/app.log
```

## 四、Nginx配置（可选）

如果您希望使用Nginx作为反向代理，可以按照以下步骤配置：

### 1. 安装Nginx

```bash
apt install -y nginx
```

### 2. 创建Nginx配置文件

```bash
# 创建配置文件
nano /etc/nginx/sites-available/live-record
```

在live-record文件中添加以下内容：

```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. 启用配置并重启Nginx

```bash
# 启用配置
ln -s /etc/nginx/sites-available/live-record /etc/nginx/sites-enabled/

# 测试配置
nginx -t

# 重启Nginx
systemctl restart nginx
```

## 五、安全配置

### 1. 配置防火墙

```bash
# 查看当前防火墙状态
ufw status

# 允许SSH访问
ufw allow ssh

# 允许HTTP访问（如果使用Nginx）
ufw allow http

# 允许应用端口访问
ufw allow 5000

# 启用防火墙
ufw enable
```

### 2. 设置HTTPS（可选）

如果您有域名，可以使用Let's Encrypt免费证书配置HTTPS：

```bash
# 安装Certbot
apt install -y certbot python3-certbot-nginx

# 获取证书
certbot --nginx -d your_domain.com

# 自动续期配置
certbot renew --dry-run
```

## 六、系统监控

### 1. 安装监控工具

```bash
# 安装htop（系统资源监控）
apt install -y htop

# 安装netdata（实时性能监控）
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

### 2. 配置日志监控

```bash
# 安装logrotate
apt install -y logrotate

# 创建logrotate配置
nano /etc/logrotate.d/live-record
```

在live-record文件中添加以下内容：

```
/opt/live-record/backend/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
}
```

## 七、使用指南

### 1. 添加主播

```bash
# 使用curl命令添加主播
curl -X POST http://your_server_ip:5000/api/anchors \
  -H "Content-Type: application/json" \
  -d '{"name": "财经主播张三", "douyin_id": "zhangsan123", "room_id": "123456789"}'
```

### 2. 查看主播列表

```bash
# 使用curl命令查看主播列表
curl http://your_server_ip:5000/api/anchors
```

### 3. 查看系统状态

```bash
# 使用curl命令查看系统状态
curl http://your_server_ip:5000/api/system/status
```

## 八、故障排查

### 1. 服务无法启动

```bash
# 查看服务状态
systemctl status live-record

# 查看详细日志
journalctl -u live-record
```

### 2. API接口返回500错误

```bash
# 查看应用日志
tail -f ./logs/app.log
```

### 3. 录制功能不工作

```bash
# 检查FFmpeg是否安装正确
ffmpeg -version

# 查看录制服务日志
tail -f ./logs/app.log | grep recording
```

### 4. 邮件推送失败

```bash
# 检查邮件配置
cat .env | grep EMAIL_

# 查看通知服务日志
tail -f ./logs/app.log | grep notification
```

## 九、更新项目

### 1. 拉取最新代码

```bash
# 进入项目目录
cd /opt/live-record

# 拉取最新代码
git pull

# 进入backend目录
cd backend

# 激活虚拟环境
source venv/bin/activate

# 安装新依赖
pip install -r requirements.txt

# 重启服务
systemctl restart live-record
```

## 十、常见问题

### 1. 阿里云服务器安全组配置

在阿里云控制台中，需要配置安全组规则，允许以下端口的访问：

- 22（SSH）
- 80（HTTP，可选）
- 443（HTTPS，可选）
- 5000（应用端口）

### 2. 抖音API限制

由于抖音API的限制，可能需要使用第三方库或工具来获取直播状态。本项目提供了一个模拟实现，实际使用时需要根据情况进行调整。

### 3. 存储空间管理

随着录制的视频和生成的摘要越来越多，需要定期清理过期的文件，以避免存储空间不足。

```bash
# 创建清理脚本
nano cleanup.sh
```

在cleanup.sh文件中添加以下内容：

```bash
#!/bin/bash

# 清理30天前的视频文件
find /opt/live-record/backend/data/videos -type f -mtime +30 -delete

# 清理30天前的摘要文件
find /opt/live-record/backend/data/summaries -type f -mtime +30 -delete

# 清理过期日志
find /opt/live-record/backend/logs -type f -mtime +7 -delete

echo "Cleanup completed at $(date)"
```

```bash
# 设置脚本执行权限
chmod +x cleanup.sh

# 执行清理脚本
./cleanup.sh

# 添加到定时任务
crontab -e
```

在crontab文件中添加以下内容（每天凌晨执行）：

```
0 0 * * * /opt/live-record/backend/cleanup.sh >> /opt/live-record/backend/logs/cleanup.log 2>&1
```

---

部署完成后，系统会自动监测主播的直播状态，当主播开播时自动录制，并在录制完成后提取核心内容，最后通过邮件和微信推送摘要给您。

祝您使用愉快！
