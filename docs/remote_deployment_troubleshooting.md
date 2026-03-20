# Aether 部署与排错指南 (远程与本地)

这份文档总结了在本地开发环境以及远程服务器部署 Aether 时遇到的典型错误、原因分析及解决步骤。

## 1. 数据库报错: `UndefinedTable: relation "users" does not exist`

**问题描述**：
运行 `./dev.sh` 或应用服务启动时，抛出 `sqlalchemy` 和 `psycopg2.errors` 初始化错误，提示找不到 `users` 表。

**原因分析**：
连接到了 PostgreSQL 数据库，但并未应用 Alembic 的数据库增量迁移脚本，导致原本该存在的表结构并未建立。

**解决步骤**：
需读取配置文件里的环境变量 `DATABASE_URL`，再通过 Alembic 初始化建表。

- **如果你有 `uv` 并在本地开发**：
  ```bash
  source .env
  export DATABASE_URL="postgresql://${DB_USER:-postgres}:${DB_PASSWORD}@${DB_HOST:-localhost}:${DB_PORT:-5432}/${DB_NAME:-aether}"
  uv run alembic upgrade head
  ```
- **如果是远程服务器环境 (如使用 `.venv` 虚拟环境)**：
  ```bash
  source .env
  export DATABASE_URL="postgresql://${DB_USER:-postgres}:${DB_PASSWORD}@${DB_HOST:-localhost}:${DB_PORT:-5432}/${DB_NAME:-aether}"
  .venv/bin/alembic upgrade head
  ```
- **通过 Docker 容器运行**：
  ```bash
  docker compose -f docker-compose.build.yml exec app alembic upgrade head
  ```

---

## 2. 端口被占用报错: `[Errno 48] Address already in use`

**问题描述**：
启动后端服务时，Uvicorn 报错并终止，提示 `Address already in use`。

**原因分析**：
之前运行的后台应用进程没有彻底关闭（未能响应结束信号，或者是后台强行留存），导致配置的端口（如 `8084`）仍然处于监听状态。

**解决步骤**：
找出并强制杀掉占用该端口的进程。
```bash
# 查找并强杀 8084 端口关联进程
lsof -i :8084 | awk 'NR>1 {print $2}' | xargs kill -9
# 或者直接通过 uvicorn 的特征进行进程清理
pkill -9 -f uvicorn
```

---

## 3. 队列 Redis 重复重启与拒绝连接: `Connection refused (Error 111)`

**问题描述**：
在远程服务器上，遇到 `全局Redis客户端 连接失败` 的日志，且通过 `docker ps` 可以观察到名为 `aether-redis` 的容器一直处于 `Restarting`（不断重启）的状态。

**原因分析**：
`.env` 文件中的 `REDIS_PASSWORD` 被留空（如 `REDIS_PASSWORD=`）。但在 `docker-compose.build.yml` 中配置了 Redis 服务的启动入参：
`command: redis-server --appendonly no --save "" --requirepass ${REDIS_PASSWORD}`
当密码为空时，这句命令将缺失必要的 `--requirepass` 参数值。Redis 进程无法成功启动并不断抛出 `FATAL CONFIG FILE ERROR (wrong number of arguments)` 导致容器直接奔溃和循环重启，端口无法暴露。

**解决步骤**：
为本地或远程的 `.env` 补充一个实际的密码字符串。
```env
REDIS_PASSWORD=YourSecureRedisPassword123
```
然后重建并启动 Redis 容器使得变更生效：
```bash
docker compose -f docker-compose.build.yml up -d redis
```

---

## 4. 无法通过 SSH 稳定后台运行并获取日志

**问题描述**：
在远程服务器执行部署时，如果使用 `nohup ./dev.sh > dev.log 2>&1 &` 启动项目，可能会发现随着 SSH 连接关闭，脚本仍然被意外杀死（SIGHUP 拦截不全或是标准输入输出了挂起导致失败），且由于环境差异报错 `uv: command not found`。

**原因分析**：
1. 远程服务器一般并未全局将 `uv` 添加进所有的非交互式 SSH path 中。
2. SSH `sh -c` 的子进程管理较弱，容易产生会话僵尸进程、文件句柄阻塞问题。

**解决步骤**：
1. **替换全局命令为实际路径**：直接修改或引用虚拟环境（把 `.env` 中的 `uv run uvicorn` 替换为绝对的可执行路径，例如 `.venv/bin/uvicorn`）。
2. **利用 `tmux` 维持持久化会话**：通过 `tmux` 开启独立的服务器后台会话模拟人的真实交互操作，再重定向日志输出，这样即使断开 SSH 也绝对不会被异常关断：
```bash
# 杀掉旧的 uvicorn
pkill -9 -f uvicorn || true

# 关掉旧的 tmux 会话 (如有)
tmux kill-session -t aether_app || true

# 开启全新的分离式后台会话
tmux new-session -d -s aether_app

# 模拟人工命令执行服务，并定向日志
tmux send-keys -t aether_app 'cd /opt/Aether' C-m
tmux send-keys -t aether_app './dev.sh > dev.log 2>&1' C-m
```
这能保证后端进程安稳跑在后台，排错时只需要运行 `tmux a -t aether_app` 或查看 `dev.log` 即可。
