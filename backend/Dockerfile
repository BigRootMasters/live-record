# 使用Python 3.9作为基础镜像
FROM python:3.9-slim

ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG APT_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN set -eux; \
    for file in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        if [ -f "$file" ]; then \
            sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g; s|https://deb.debian.org/debian|${APT_MIRROR}|g" "$file"; \
            sed -i "s|http://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g; s|https://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" "$file"; \
        fi; \
    done; \
    apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN set -eux; \
    pip_args="--no-cache-dir"; \
    if [ -n "$PIP_INDEX_URL" ]; then \
        pip_args="$pip_args --index-url $PIP_INDEX_URL"; \
    fi; \
    if [ -n "$PIP_EXTRA_INDEX_URL" ]; then \
        pip_args="$pip_args --extra-index-url $PIP_EXTRA_INDEX_URL"; \
    fi; \
    if [ -n "$PIP_TRUSTED_HOST" ]; then \
        pip_args="$pip_args --trusted-host $PIP_TRUSTED_HOST"; \
    fi; \
    pip install $pip_args -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p data/videos data/summaries

# 暴露端口
EXPOSE 5000

# 启动应用
CMD ["gunicorn", "app:app", "--config", "gunicorn.conf.py"]
