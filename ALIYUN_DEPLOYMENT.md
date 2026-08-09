# Aliyun Deployment Tutorial

这是一份面向阿里云中国内地服务器的实战部署手册，目标是：

- 直接在宿主机跑这个项目
- 保留后续更新和排障的简单性

当前项目推荐的部署形态只有两个长期进程：

- `backend` API
- `scheduler` 调度器

## 1. 部署前准备

建议准备：

- 一台阿里云 ECS Linux 服务器
- 一个可以正常访问抖音页面的公网环境
- 一个企业微信机器人 webhook
- 一个普通用户或 `root` 登录权限

自动部署脚本的确切要求：

- Alibaba Cloud Linux `3.2104`
- `x86_64` 或系统软件源支持的其他架构
- `root` 权限（需要安装 RPM 和 systemd 服务）
- 仓库已经 clone 到服务器
- 仓库内的 `.env` 和 `config/anchors.json` 已配置
- 能访问 GitHub、阿里云 PyPI 镜像、RPM 软件源、抖音和企业微信

如果你只是先试跑，不一定要先配域名。先用服务器 IP 验证流程即可。

## 一键自动部署（推荐）

首次部署：

```bash
dnf install -y git
cd /opt
git clone https://github.com/BigRootMasters/live-record.git
cd /opt/live-record
chmod +x deploy.sh
./deploy.sh
```

后续更新：

```bash
cd /opt/live-record
./deploy.sh
```

脚本按以下顺序执行：

1. 检查仓库是否存在未提交的跟踪文件修改
2. `git pull --ff-only origin main`
3. 安装 Python 3.11、`python3.11-pip`、Git 和 curl
4. 安装 FFmpeg；默认源缺少软件包时自动启用 EPEL 和 RPM Fusion EL8
5. 创建或复用 `backend/.venv`
6. 使用阿里云 PyPI 镜像安装依赖
7. 校验主播 JSON、FFmpeg 路径并运行测试
8. 根据当前 clone 路径生成并安装 systemd 单元
9. 先优雅停止调度器，再启动 API 和调度器
10. 验证 `/health` 和两个 systemd 服务状态

常用参数：

```bash
./deploy.sh --help
./deploy.sh --skip-pull
./deploy.sh --skip-system-deps
./deploy.sh --skip-tests
```

- `--skip-pull`：仅部署当前磁盘上的代码
- `--skip-system-deps`：已安装 Python/FFmpeg 时跳过 RPM 检查
- `--skip-tests`：紧急情况才建议使用

脚本会在 Python 依赖和测试成功后才重启服务，避免把一个依赖不完整的版本直接投入运行。

如果部署时正在录制，调度器会先让 FFmpeg 优雅收尾、处理当前文件并发送音频，
然后重启并在下一次巡检时继续录制。如果不希望产生两个录制片段，请在主播下播后再部署。

## 2. 为什么阿里云上装依赖会慢

最常见的卡点就是这两个：

1. 系统包安装 `ffmpeg` 慢
2. `pip install` 走海外源慢

所以这套教程使用：

- 宿主机安装 `ffmpeg`
- Python `.venv`
- 国内 `pip` 镜像

## 3. 服务器初始化

### Alibaba Cloud Linux 3.2104

```bash
dnf install -y python3.11 python3.11-pip git curl
python3.11 --version
python3.11 -m pip --version
```

不要替换系统默认的 Python 3.6；`dnf` 等系统组件依赖它。

如果 `dnf install -y ffmpeg` 提示没有软件包：

```bash
dnf install -y epel-release || \
  dnf install -y https://mirrors.aliyun.com/epel/epel-release-latest-8.noarch.rpm
dnf install -y \
  https://mirrors.aliyun.com/rpmfusion/free/el/rpmfusion-free-release-8.noarch.rpm
dnf clean metadata
dnf makecache
dnf install -y ffmpeg
ffmpeg -version | head -n 1
ffprobe -version | head -n 1
```

### Ubuntu / Debian

先切系统源到阿里云镜像：

```bash
cp /etc/apt/sources.list /etc/apt/sources.list.bak.$(date +%F-%H%M%S)
sed -i 's@http://archive.ubuntu.com/ubuntu@https://mirrors.aliyun.com/ubuntu@g' /etc/apt/sources.list
sed -i 's@http://security.ubuntu.com/ubuntu@https://mirrors.aliyun.com/ubuntu@g' /etc/apt/sources.list
apt-get clean
apt-get update
```

再安装依赖：

```bash
apt-get install -y python3 python3-venv python3-pip git ffmpeg
python3 --version
ffmpeg -version | head -n 1
```

## 4. 拉代码

```bash
cd /opt
git clone git@github.com:BigRootMasters/live-record.git
cd /opt/live-record
git checkout main
```

如果服务器没有配置 SSH key，也可以先用 HTTPS：

```bash
git clone https://github.com/BigRootMasters/live-record.git
```

## 5. 创建虚拟环境并固定国内 pip 源

```bash
cd /opt/live-record/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.trusted-host mirrors.aliyun.com
pip config set global.timeout 120
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt
```

虚拟环境激活后，`python --version` 必须显示 Python 3.11。

## 6. 配置运行环境

直接编辑仓库里的 `backend/.env` 即可。

推荐从这个最小配置开始：

```env
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your_secret_key_here

DATABASE_URL=sqlite:///./data.db
VIDEO_STORAGE_PATH=./data/recordings
FFMPEG_BIN=/usr/bin/ffmpeg
FFPROBE_BIN=/usr/bin/ffprobe

RECORDING_MODE=audio
AUDIO_RECORDING_BITRATE=64k
AUDIO_RECORDING_SAMPLE_RATE=16000
AUDIO_RECORDING_CHANNELS=1

USE_REAL_API=True
API_TIMEOUT=10
API_RETRIES=3
DOUYIN_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36

WECHAT_WEBHOOK_URL=你的企业微信机器人webhook
WECHAT_TIMEOUT=10
WECHAT_RETRIES=3
AUTO_SEND_AUDIO_ON_RECORDING_COMPLETE=True
WECHAT_AUDIO_BITRATE=16k
WECHAT_AUDIO_SAMPLE_RATE=16000
WECHAT_AUDIO_CHANNELS=1
WECHAT_AUDIO_MAX_MB=20

ANCHOR_CONFIG_PATH=./config/anchors.json

CHECK_INTERVAL=120
OFFLINE_CONFIRMATION_CHECKS=2
KEEP_RECORDING_ON_DISCOVERY_ERROR=True
MAX_RECORDING_DURATION=9000
RECORDING_RETENTION_DAYS=7
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
```

注意：现在 `.env` 已经纳入 Git 管理。

- 如果你在服务器上改过 `backend/.env`，后续 `git pull` 可能会被本地改动拦住
- 更稳的做法是统一在仓库里维护 `.env`，服务器只做拉取和重启

## 7. 配置主播

编辑 [`backend/config/anchors.json`](./backend/config/anchors.json)。

最常见格式如下：

```json
[
  {
    "name": "主播名称",
    "douyin_id": "MS4wLjABAAAA...",
    "anchor_id": "",
    "profile_url": "https://www.douyin.com/user/...",
    "live_url": "",
    "room_id": "",
    "avatar_url": "",
    "is_followed": true,
    "notes": "可选备注"
  }
]
```

## 8. 创建目录

```bash
cd /opt/live-record/backend
mkdir -p data/recordings logs run backups
```

## 9. 手工启动验证

### 启动 API

```bash
cd /opt/live-record/backend
source .venv/bin/activate
gunicorn -c gunicorn.conf.py app:app
```

如果服务器 `5000` 端口被占用，可以临时改成：

```bash
PORT=5001 gunicorn --bind 127.0.0.1:5001 -c gunicorn.conf.py app:app
```

### 启动调度器

新开一个终端：

```bash
cd /opt/live-record/backend
source .venv/bin/activate
python run_scheduler.py
```

### 验证接口

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/api/system/status
curl http://127.0.0.1:5000/api/recordings
```

如果你绑定的是 `5001`，把上面的端口替换成 `5001`。

正常情况下，调度器日志里应看到：

```text
Starting task scheduler service
Starting live monitor task
Task scheduler is running in record-only mode
```

主播正在直播时，会看到类似：

```text
Anchor 炉石挽歌 is live!
Starting recording for anchor 炉石挽歌
Audio recording started for recording ID: 11, output: ./data/recordings/...
```

## 10. 配置 systemd

项目已提供模板：

- [`backend/deploy/systemd/live-record-backend.service`](./backend/deploy/systemd/live-record-backend.service)
- [`backend/deploy/systemd/live-record-scheduler.service`](./backend/deploy/systemd/live-record-scheduler.service)

复制并启用：

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

## 11. 更新流程

推荐使用自动更新：

```bash
cd /opt/live-record
./deploy.sh
```

如果需要手工更新：

```bash
cd /opt/live-record
git fetch origin
git checkout main
git pull

cd backend
source .venv/bin/activate
python -m pip install -r requirements.txt

systemctl stop live-record-scheduler
systemctl restart live-record-backend
systemctl start live-record-scheduler
```

## 12. 从旧版本升级时的清理

如果你之前部署过带转写的老版本，升级到当前纯录制模式后，执行一次：

```bash
cd /opt/live-record/backend
source .venv/bin/activate
python scripts/cleanup_legacy_transcription_data.py
```

它会做三件事：

- 归一化旧的录制状态
- 删除数据库里的 `summaries` 表
- 删除旧的 `data/summaries` 目录

## 13. 常见问题

### `pip install` 还是慢

先确认：

```bash
pip config list
```

确保能看到：

- `global.index-url='https://mirrors.aliyun.com/pypi/simple/'`
- `global.trusted-host='mirrors.aliyun.com'`

### `ffmpeg not found`

```bash
which ffmpeg
which ffprobe
```

找不到就装系统包；如果路径特殊，就写进 `.env`：

```env
FFMPEG_BIN=/usr/local/bin/ffmpeg
FFPROBE_BIN=/usr/local/bin/ffprobe
```

### 5000 端口被占用

```bash
ss -ltnp | grep :5000
```

如果端口被别的服务占了：

- 换端口绑定
- 或让 Nginx / Caddy 反向代理到本地端口

### 企业微信没收到文件

优先检查：

- `WECHAT_WEBHOOK_URL` 是否正确
- 音频大小是否超过 `WECHAT_AUDIO_MAX_MB`
- 录制文件是否真正生成

### 录制文件保存在哪里

默认目录结构：

```text
data/recordings/<anchor_id>_<anchor_name>/<YYYY-MM-DD>/<audio|video>/<YYYYMMDD_HHMMSS>.<ext>
```
