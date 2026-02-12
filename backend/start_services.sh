#!/bin/bash

# 启动所有服务的脚本

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

# 启动Flask应用
echo "Starting Flask application..."
gunicorn -c gunicorn.conf.py app:app &

# 等待应用启动
sleep 5

# 检查应用是否启动成功
if curl -s http://localhost:5000/health; then
    echo "Flask application started successfully!"
else
    echo "Failed to start Flask application!"
    exit 1
fi

# 启动定时任务服务
echo "Starting task scheduler..."
python -c "from app.services.task_scheduler import task_scheduler; task_scheduler.start()"

echo "All services started successfully!"
echo "System is now monitoring for live streams..."
