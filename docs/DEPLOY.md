## 部署方案

### Docker（推荐）

```bash
docker compose up -d
```

- 后端: `http://localhost:5001`
- 前端: `http://localhost:5173`

### 本地开发

后端 `uvicorn --reload :5001` + 前端 `vite dev :5173`。两个进程各开一个终端，或运行 `./start.sh` 一键启动。

### 生产部署

#### 1. 构建前端静态文件

```bash
cd frontend && npm run build
```

产出到 `frontend/dist/`。

#### 2. Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/frontend/dist;
        index index.html;
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/events {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
    }
}
```

#### 3. 后端生产运行

```bash
gunicorn backend.main:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:5001 \
    --max-requests 500 \
    --max-requests-jitter 50
```

### 注意事项

- 端口 5000 被 macOS AirPlay 接收器占用，改用 5001
- Chrome 需要图形环境，服务器端部署需 Xvfb 虚拟显示器或使用 `CHROME_HEADLESS=1`
- 账号安全：不要在公用服务器上存个人 BOSS 登录态
