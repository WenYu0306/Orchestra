## 部署方案

### 本地开发（现在用的）

后端 `uvicorn --reload :5000` + 前端 `vite dev :5173`。两个进程各开一个终端。

### 生产部署（建议）

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

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        index index.html;
        try_files $uri /index.html;
    }

    # API 代理到后端
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # SSE 代理
    location /api/events {
        proxy_pass http://127.0.0.1:5000;
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
# 用 gunicorn + uvicorn workers
gunicorn backend.main:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:5000 \
    --max-requests 500 \
    --max-requests-jitter 50
```

### 注意事项

- 生产环境 CORS 需限制具体域名，不要用 `*`
- Chrome 需要图形环境，服务器端部署需要 Xvfb 虚拟显示器
- 账号安全：不要在公用服务器上存个人 BOSS 登录态
