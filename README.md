# Live Record

一个面向单机部署的抖音直播自动录制工具，当前默认工作模式是：

- 自动巡检指定主播是否开播
- 开播后自动录制音视频，或按配置只录音频
- 下播后优雅收尾并保存录播文件
- 自动抽取音频并发送到企业微信机器人

当前项目已经默认收口为“纯录制模式”，不再依赖前端页面，也不会自动做文字识别或摘要生成。

部署思路参考了 [ihmily/DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) 的源码运行方式：优先使用宿主机安装 `ffmpeg`，再配合 Python 虚拟环境直接运行。对中国大陆服务器来说，这通常比 Docker 构建更稳、更快。

如果你准备直接在阿里云服务器实操，优先看这份分步教程：

- [ALIYUN_DEPLOYMENT.md](./ALIYUN_DEPLOYMENT.md)

## 当前架构

- `backend/app.py`
  Flask API，提供健康检查、录制记录、系统状态等接口。
- `backend/run_scheduler.py`
  调度入口，定时巡检主播、启动录制、停录和发送企业微信音频。
- `backend/config/anchors.json`
  主播配置文件。
- `backend/.env`
  运行配置。

## 推荐运行方式

推荐优先使用普通安装模式，而不是 Docker：

1. 服务器系统安装 `ffmpeg`
2. 创建 Python 虚拟环境 `.venv`
3. 安装 `backend/requirements.txt`
4. 用 `gunicorn` 启动 API
5. 用 `python run_scheduler.py` 启动调度器
6. 使用 `systemd` 做守护和开机自启

## 环境要求

- Linux 服务器
- Python `3.9+`
- `ffmpeg` 和 `ffprobe`
- Git

如果你是阿里云中国内地服务器，推荐直接使用普通安装模式，避开 Docker 镜像构建时的海外源和基础镜像拉取问题。

## 快速开始

### 1. 克隆代码

```bash
git clone https://github.com/BigRootMasters/live-record.git
cd live-record/backend
```

### 2. 安装系统依赖

Alibaba Cloud Linux / Rocky / CentOS Stream:

```bash
dnf install -y python39 python39-devel git ffmpeg
```

Ubuntu / Debian:

```bash
apt-get update
apt-get install -y python3 python3-venv python3-pip git ffmpeg
```

### 3. 创建虚拟环境

```bash
python3.9 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel -i https://mirrors.aliyun.com/pypi/simple/
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

如果你的系统命令是 `python3` 而不是 `python3.9`，把上面的解释器名替换掉即可。

阿里云国内服务器想进一步提速，建议再做这几步：

```bash
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.trusted-host mirrors.aliyun.com
pip config set global.timeout 120
```

Ubuntu / Debian 机器如果系统源本身也慢，先切到阿里云镜像再装系统包：

```bash
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak.$(date +%F-%H%M%S)
sudo sed -i 's@http://archive.ubuntu.com/ubuntu@https://mirrors.aliyun.com/ubuntu@g' /etc/apt/sources.list
sudo sed -i 's@http://security.ubuntu.com/ubuntu@https://mirrors.aliyun.com/ubuntu@g' /etc/apt/sources.list
sudo apt-get clean
sudo apt-get update
```

这个项目在阿里云上最稳的做法依然是：

- 不走 Docker 首次构建
- 宿主机直接安装 `ffmpeg`
- `pip` 固定使用国内镜像
- `.venv` 保留在磁盘上，后续更新只重新执行一次 `pip install -r requirements.txt`

### 4. 配置运行环境

```bash
cp .env.example .env
```

最小可用配置示例：

```env
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=replace-with-a-random-secret

DATABASE_URL=sqlite:///./data.db
VIDEO_STORAGE_PATH=./data/recordings
FFMPEG_BIN=/usr/bin/ffmpeg
FFPROBE_BIN=/usr/bin/ffprobe
RECORDING_MODE=video
AUDIO_RECORDING_BITRATE=64k
AUDIO_RECORDING_SAMPLE_RATE=16000
AUDIO_RECORDING_CHANNELS=1

USE_REAL_API=True
ANCHOR_CONFIG_PATH=./config/anchors.json

WECHAT_WEBHOOK_URL=你的企业微信机器人 webhook
AUTO_SEND_AUDIO_ON_RECORDING_COMPLETE=True

CHECK_INTERVAL=120
MAX_RECORDING_DURATION=9000
RECORDING_RETENTION_DAYS=7
CLEANUP_VIDEO=False
LOG_LEVEL=INFO
```

### 5. 配置主播

编辑 [`backend/config/anchors.json`](./backend/config/anchors.json)。当前常用格式如下：

```json
[
  {
    "name": "天霸哥讲财经",
    "douyin_id": "MS4wLjABAAAAhIZOt35fbbF-cvx6M9FkcZk4S3uwcYJ2CS3MsfvF88GnIiCSC-wakC4woeCxiBNv",
    "anchor_id": "",
    "profile_url": "https://www.douyin.com/user/...",
    "live_url": "",
    "room_id": "",
    "avatar_url": "",
    "is_followed": true,
    "notes": "仅提供主页信息，用于验证主页推导直播入口"
  }
]
```

录制文件会按下面的目录结构落盘：

```text
data/recordings/<anchor_id>_<anchor_name>/<YYYY-MM-DD>/<audio|video>/<YYYYMMDD_HHMMSS>.<ext>
```

### 6. 手工启动

启动 API：

```bash
source .venv/bin/activate
gunicorn -c gunicorn.conf.py app:app
```

另开一个终端启动调度器：

```bash
source .venv/bin/activate
python run_scheduler.py
```

或者直接使用项目自带脚本：

```bash
./start_services.sh
```

### 7. 验证

健康检查：

```bash
curl http://127.0.0.1:5000/health
```

系统状态：

```bash
curl http://127.0.0.1:5000/api/system/status
```

调度器正常启动时，日志里应该看到：

```text
Starting task scheduler service
Starting live monitor task
Task scheduler is running in record-only mode
```

如果主播正在直播，后面应该出现：

```text
Anchor 天霸哥讲财经 is live!
Starting recording for anchor 天霸哥讲财经
Video recording started for recording ID: ...
```

录制结束后应该出现：

```text
Recording ... processed successfully
Recording audio delivered successfully for recording ...
```

## 使用 systemd 守护

项目里已经提供了现成模板：

- [`backend/deploy/systemd/live-record-backend.service`](./backend/deploy/systemd/live-record-backend.service)
- [`backend/deploy/systemd/live-record-scheduler.service`](./backend/deploy/systemd/live-record-scheduler.service)

假设项目部署在 `/opt/live-record`：

```bash
cp backend/deploy/systemd/live-record-backend.service /etc/systemd/system/
cp backend/deploy/systemd/live-record-scheduler.service /etc/systemd/system/

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

## 更新流程

```bash
cd /opt/live-record
git fetch origin
git checkout main
git pull

cd backend
source .venv/bin/activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

systemctl restart live-record-backend
systemctl restart live-record-scheduler
```

## 常见问题

### 1. 为什么不默认推荐 Docker

对中国大陆服务器来说，Docker 首次构建通常会同时卡在这些步骤：

- 基础镜像拉取
- `apt-get install ffmpeg`
- `pip install -r requirements.txt`

而当前项目只需要两个长期进程，使用普通安装模式更直接。

### 2. `ffmpeg not found`

确认服务器上存在：

```bash
which ffmpeg
which ffprobe
```

必要时在 `.env` 中显式指定：

```env
FFMPEG_BIN=/usr/bin/ffmpeg
FFPROBE_BIN=/usr/bin/ffprobe
```

### 3. 录制能否正常结束

当前停止逻辑不是直接强杀 `ffmpeg`，而是先发送 `q`，让 `ffmpeg` 优雅写完封装信息后退出，所以正常情况下能完整收尾 MP4 文件。

### 4. 是否必须部署前端

不是。当前主链路只需要：

- `backend`
- `scheduler`
- `anchors.json`
- 企业微信 webhook

### 5. 如何彻底清理旧转写数据

如果你是从旧版本升级上来的，想把历史 `summaries` 表和旧摘要目录一起删掉，可以执行：

```bash
cd /opt/live-record/backend
source .venv/bin/activate
python scripts/cleanup_legacy_transcription_data.py
```

## 更多部署细节

更完整的服务器部署说明见 [`DEPLOYMENT.md`](./DEPLOYMENT.md)。
