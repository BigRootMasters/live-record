# Deployment Guide

当前项目推荐使用“普通安装模式”部署，而不是 Docker。原因很简单：

- 只有 `backend` 和 `scheduler` 两个长期进程
- 服务器上直接安装 `ffmpeg` 更稳
- 中国大陆服务器首次构建 Docker 镜像往往会慢在基础镜像、`apt` 和 `pip`

这套思路参考了 [ihmily/DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) 常见的源码运行方式：宿主机安装 `ffmpeg`，项目自身走 Python 虚拟环境。

## 1. 服务器要求

- Linux 服务器
- Python `3.9+`
- `ffmpeg` / `ffprobe`
- Git
- 可访问抖音直播页面

## 2. 安装系统依赖

### Alibaba Cloud Linux / Rocky / CentOS Stream

```bash
dnf install -y python39 python39-devel git ffmpeg
python3.9 --version
ffmpeg -version | head -n 1
```

### Ubuntu / Debian

```bash
apt-get update
apt-get install -y python3 python3-venv python3-pip git ffmpeg
python3 --version
ffmpeg -version | head -n 1
```

## 3. 获取代码

```bash
cd /opt
git clone https://github.com/BigRootMasters/live-record.git
cd /opt/live-record
git checkout main
```

更新时使用：

```bash
cd /opt/live-record
git fetch origin
git checkout main
git pull
```

## 4. 配置主播

编辑 [`backend/config/anchors.json`](./backend/config/anchors.json)。

如果你当前只需要一个主播，可以直接写成：

```json
[
  {
    "name": "天霸哥讲财经",
    "douyin_id": "MS4wLjABAAAAhIZOt35fbbF-cvx6M9FkcZk4S3uwcYJ2CS3MsfvF88GnIiCSC-wakC4woeCxiBNv",
    "anchor_id": "",
    "profile_url": "https://www.douyin.com/user/MS4wLjABAAAAhIZOt35fbbF-cvx6M9FkcZk4S3uwcYJ2CS3MsfvF88GnIiCSC-wakC4woeCxiBNv?from_tab_name=live",
    "live_url": "",
    "room_id": "",
    "avatar_url": "",
    "is_followed": true,
    "notes": "仅提供主页信息，用于验证主页推导直播入口"
  }
]
```

## 5. 创建虚拟环境并安装依赖

```bash
cd /opt/live-record/backend
python3.9 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel -i https://mirrors.aliyun.com/pypi/simple/
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

如果你的服务器只有 `python3`，把 `python3.9` 换成 `python3` 即可。

## 6. 配置 .env

```bash
cd /opt/live-record/backend
cp .env.example .env
```

建议至少确认这些配置：

```env
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=replace-with-a-random-secret

DATABASE_URL=sqlite:///./data.db
VIDEO_STORAGE_PATH=./data/temp_videos
SUMMARY_STORAGE_PATH=./data/summaries
FFMPEG_BIN=/usr/bin/ffmpeg
FFPROBE_BIN=/usr/bin/ffprobe

USE_REAL_API=True
ANCHOR_CONFIG_PATH=./config/anchors.json

WECHAT_WEBHOOK_URL=你的企业微信机器人 webhook
WECHAT_TIMEOUT=10
WECHAT_RETRIES=3
AUTO_SEND_AUDIO_ON_RECORDING_COMPLETE=True
WECHAT_AUDIO_BITRATE=16k
WECHAT_AUDIO_SAMPLE_RATE=16000
WECHAT_AUDIO_CHANNELS=1
WECHAT_AUDIO_MAX_MB=20

ENABLE_TRANSCRIPTION=False
AUTO_NOTIFY_ON_TRANSCRIBE=False

CHECK_INTERVAL=120
MAX_RECORDING_DURATION=9000
RECORDING_RETENTION_DAYS=7
CLEANUP_VIDEO=False
LOG_LEVEL=INFO
```

## 7. 创建运行目录

```bash
cd /opt/live-record/backend
mkdir -p data/temp_videos data/summaries logs run
```

## 8. 手工验证启动

### 启动 API

```bash
cd /opt/live-record/backend
source .venv/bin/activate
gunicorn -c gunicorn.conf.py app:app
```

新开终端验证：

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/api/system/status
```

### 启动调度器

```bash
cd /opt/live-record/backend
source .venv/bin/activate
python run_scheduler.py
```

或者直接使用：

```bash
cd /opt/live-record/backend
chmod +x start_services.sh stop_services.sh
./start_services.sh
```

停止：

```bash
./stop_services.sh
```

## 9. 配置 systemd

项目已提供模板：

- [`backend/deploy/systemd/live-record-backend.service`](./backend/deploy/systemd/live-record-backend.service)
- [`backend/deploy/systemd/live-record-scheduler.service`](./backend/deploy/systemd/live-record-scheduler.service)

默认模板按部署目录 `/opt/live-record/backend` 编写，如果你用的是别的目录，请先修改模板中的路径。

安装方式：

```bash
cp /opt/live-record/backend/deploy/systemd/live-record-backend.service /etc/systemd/system/
cp /opt/live-record/backend/deploy/systemd/live-record-scheduler.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now live-record-backend
systemctl enable --now live-record-scheduler
```

查看状态：

```bash
systemctl status live-record-backend --no-pager
systemctl status live-record-scheduler --no-pager
```

查看日志：

```bash
journalctl -u live-record-backend -f
journalctl -u live-record-scheduler -f
```

## 10. 验证录制链路

正常启动后，调度器日志应该看到：

```text
Starting task scheduler service
Starting live monitor task
Transcription is disabled; analyzer and summary notification tasks will not start
```

如果主播在播，后面应看到：

```text
Anchor 天霸哥讲财经 is live!
Starting recording for anchor 天霸哥讲财经
Video recording started for recording ID: ...
```

录制结束后应看到：

```text
Recording ... processed successfully
Recording audio delivered successfully for recording ...
```

## 11. 常见问题

### Python 版本过低

如果系统自带 Python 是 `3.6` 或更低，优先安装 `python3.9+` 后再创建虚拟环境。当前项目建议直接用 `3.9+`。

### ffmpeg not found

先检查：

```bash
which ffmpeg
which ffprobe
```

找不到就安装系统包；能找到但路径特殊，就写到 `.env`：

```env
FFMPEG_BIN=/usr/local/bin/ffmpeg
FFPROBE_BIN=/usr/local/bin/ffprobe
```

### 5000 端口被占用

```bash
ss -ltnp | grep :5000
```

### 为什么这里不推荐 Docker

如果只是要在一台阿里云服务器上稳定跑：

- 普通安装模式更轻
- 更省内存
- 更容易定位问题
- 避开首次构建镜像时的网络波动

Docker 仍然保留为可选方案，但不再是首推路径。
