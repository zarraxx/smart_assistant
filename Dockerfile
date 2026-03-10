# 1. 从基础镜像创建
FROM registry.bsoft.com.cn/hc/python:3.12-slim

# 设置一个环境变量来存储用户名，方便复用
ARG APP_USER=fastapi_user

# 2. 创建专用用户并设置文件所有权
# 将多个 RUN 命令合并，以减少镜像层数
RUN useradd -m -U -s /sbin/nologin "${APP_USER}" \
    && mkdir -p /app \
    && chown -R "${APP_USER}:${APP_USER}" /app

# 3. 设置工作目录
WORKDIR /app

# 配置镜像元数据
# 切换到非 root 用户
USER ${APP_USER}

# 4. 复制项目文件
# 先只复制依赖定义文件，以便利用 Docker 的层缓存机制
COPY pyproject.toml .
COPY README.md .
# 5 复制应用代码
COPY ./src ./src
RUN  chown -R "${APP_USER}:${APP_USER}" /app && ls -la /app
# 6. 安装依赖
# 将安装 uv 和安装项目依赖合并
RUN uv venv && uv pip install --no-cache-dir .

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
#ENV PYTHONPATH="/app/app"
# 暴露端口
EXPOSE 8000

# 定义容器启动时执行的命令
CMD ["uvicorn", "src.webapp.assistant_app:app", "--host", "0.0.0.0", "--port", "8000"]
