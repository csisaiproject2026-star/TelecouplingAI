# Project Template Reference
> 本文档记录了 CSIS 生态智能平台的前端设计风格、组件模式和前后端交互方式。
> 新项目可直接参照本文档，让 LLM 生成风格一致的代码。

---

## 一、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + Tailwind CSS |
| 后端 | Python FastAPI |
| 实时通信 | SSE (Server-Sent Events) |
| 任务队列 | Celery + Redis（若无长耗时任务可省略） |
| 会话管理 | Redis hash（也可用 localStorage 轻量替代） |
| 部署 | Docker + Nginx 反向代理 |

---

## 二、前端设计系统

### 2.1 颜色与字体

```
主色调 primary:  #4285f4  (Google 蓝)
渐变:           linear-gradient(135deg, #4285f4, #9b72cb)
背景色:         #f0f4f9  (浅灰蓝)
卡片背景:       #ffffff
正文色:         #1f1f1f
次要文字:       #5f6368  (gray-500)
成功色:         green-500 / #22c55e
警告色:         amber-500
危险色:         #d96570
```

### 2.2 圆角 & 阴影规则

```
按钮/输入框:   rounded-2xl  (16px)
消息气泡:      rounded-3xl  (24px)  ← 区别于普通按钮
卡片/面板:     rounded-xl   (12px)
弹窗/模态框:   rounded-2xl + shadow-2xl
标签/徽章:     rounded-full (全圆)

阴影: 仅用于卡片(shadow-sm)和模态框(shadow-2xl)，其他元素不加阴影
```

### 2.3 间距原则

```
页面内边距:    px-4 md:px-6
区块间距:      gap-3 / gap-4
按钮内边距:    px-4 py-2 (普通) | px-6 py-3 (大按钮)
图标+文字间距: gap-2
列表项:        space-y-1 / space-y-2
```

### 2.4 字体大小

```
页面标题:   text-xl font-semibold
区块标题:   text-base font-medium
正文:       text-sm
辅助文字:   text-xs text-gray-500
代码/路径:  font-mono text-xs
```

### 2.5 自定义滚动条（index.css）

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  background-color: #f0f4f9;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #dadce0;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
```

---

## 三、前端页面布局模式

### 3.1 整体布局：左侧栏 + 右侧主区

```jsx
// 典型双栏布局
<div className="flex h-screen bg-[#f0f4f9] overflow-hidden">
  {/* 左侧边栏 */}
  <aside className={`
    w-72 bg-white flex flex-col border-r border-gray-200
    fixed inset-y-0 left-0 z-40 transition-transform duration-300
    md:relative md:translate-x-0
    ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
  `}>
    <div className="p-4 border-b border-gray-100">
      <h1 className="text-lg font-semibold text-gray-800">项目名称</h1>
    </div>
    <nav className="flex-1 overflow-y-auto custom-scrollbar p-2">
      {/* 导航列表 */}
    </nav>
  </aside>

  {/* 移动端遮罩 */}
  {isSidebarOpen && (
    <div
      className="fixed inset-0 bg-black/30 z-30 md:hidden"
      onClick={() => setIsSidebarOpen(false)}
    />
  )}

  {/* 主内容区 */}
  <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
    {/* 顶部导航栏 */}
    <header className="h-14 flex items-center px-4 bg-white border-b border-gray-200 gap-3">
      <button
        className="md:hidden p-2 rounded-lg hover:bg-gray-100"
        onClick={() => setIsSidebarOpen(true)}
      >
        <Menu size={20} />
      </button>
      <span className="text-sm font-medium text-gray-700">页面标题</span>
    </header>

    {/* 内容区 */}
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* 页面主体内容 */}
    </div>
  </main>
</div>
```

### 3.2 聊天气泡样式

```jsx
// 用户消息（右对齐）
<div className="flex justify-end mb-4">
  <div className="max-w-[75%] bg-[#4285f4] text-white px-4 py-3 rounded-3xl rounded-br-lg text-sm">
    {message.content}
  </div>
</div>

// AI 消息（左对齐）
<div className="flex gap-3 mb-4">
  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4285f4] to-[#9b72cb] flex items-center justify-center flex-shrink-0">
    <Bot size={16} className="text-white" />
  </div>
  <div className="flex-1 max-w-[85%] bg-white rounded-3xl rounded-tl-lg px-4 py-3 shadow-sm text-sm text-gray-800">
    {/* 消息内容 */}
  </div>
</div>
```

### 3.3 输入框区域

```jsx
<div className="p-4 bg-white border-t border-gray-100">
  {/* 文件预览标签 */}
  {selectedFiles.length > 0 && (
    <div className="flex flex-wrap gap-2 mb-2">
      {selectedFiles.map((f, i) => (
        <div key={i} className="flex items-center gap-1 text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-full border border-blue-200">
          <Paperclip size={10} />
          <span>{f.name}</span>
          <button
            onClick={() => setSelectedFiles(prev => prev.filter((_, j) => j !== i))}
            className="ml-1 text-gray-400 hover:text-red-500"
          >×</button>
        </div>
      ))}
    </div>
  )}

  {/* 输入框 + 按钮 */}
  <div className="flex items-end gap-2 bg-gray-50 rounded-2xl border border-gray-200 px-3 py-2">
    {/* 文件上传按钮 */}
    <button
      onClick={() => fileInputRef.current?.click()}
      className="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors flex-shrink-0"
    >
      <Paperclip size={18} />
    </button>
    <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />

    {/* 文本输入 */}
    <textarea
      value={input}
      onChange={e => setInput(e.target.value)}
      onKeyDown={e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
      }}
      placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
      className="flex-1 bg-transparent resize-none outline-none text-sm text-gray-800 placeholder-gray-400 max-h-32 py-1"
      rows={1}
    />

    {/* 发送按钮 */}
    <button
      onClick={handleSend}
      disabled={isLoading || (!input.trim() && selectedFiles.length === 0)}
      className="p-1.5 bg-[#4285f4] text-white rounded-lg hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
    >
      {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
    </button>
  </div>
</div>
```

---

## 四、通用 UI 组件模式

### 4.1 进度卡片（ToolStatusCard）

```jsx
// 用于显示后台任务进度
function ToolStatusCard({ tool, message, progress }) {
  const isComplete = progress >= 100;
  return (
    <div className={`
      rounded-xl border p-3 my-2 text-sm
      ${isComplete
        ? 'bg-green-50 border-green-200 text-green-800'
        : 'bg-blue-50 border-blue-200 text-blue-800'}
    `}>
      <div className="flex items-center gap-2 mb-2">
        {isComplete
          ? <CheckCircle size={16} className="text-green-600" />
          : <Loader2 size={16} className="animate-spin text-blue-600" />
        }
        <span className="font-medium">{tool}</span>
        <span className="ml-auto text-xs text-gray-500">{progress}%</span>
      </div>
      <p className="text-xs text-gray-600 mb-2">{message}</p>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500
            ${isComplete ? 'bg-green-500' : 'bg-blue-500'}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
```

### 4.2 警告卡片（WarningCard）

```jsx
function WarningCard({ message }) {
  return (
    <div className="flex gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3 my-2 text-sm text-amber-800">
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5 text-amber-500" />
      <p>{message}</p>
    </div>
  );
}
```

### 4.3 CSV 表格渲染

```jsx
function CsvRenderer({ filename, columns, rows }) {
  return (
    <div className="my-2 rounded-xl border border-gray-200 overflow-hidden text-xs">
      <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
        <Table size={14} className="text-gray-400" />
        <span className="font-medium text-gray-700">{filename}</span>
        <span className="ml-auto text-gray-400">{rows.length} 行</span>
      </div>
      <div className="overflow-auto max-h-72">
        <table className="w-full">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              {columns.map(col => (
                <th key={col} className="px-3 py-1.5 text-left font-medium text-gray-600 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                {columns.map(col => (
                  <td key={col} className="px-3 py-1.5 text-gray-700 whitespace-nowrap">
                    {row[col] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### 4.4 文件下载列表

```jsx
function ResultFiles({ files }) {
  return (
    <div className="my-2 space-y-1.5">
      {files.map((f, i) => (
        <a
          key={i}
          href={f.url}
          download={f.filename}
          className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl hover:bg-blue-50 hover:border-blue-300 transition-colors text-sm text-gray-700 group"
        >
          <Download size={14} className="text-gray-400 group-hover:text-blue-500" />
          <span className="flex-1 truncate">{f.filename}</span>
          <span className="text-xs text-gray-400 uppercase">{f.filename.split('.').pop()}</span>
        </a>
      ))}
    </div>
  );
}
```

### 4.5 图片查看器

```jsx
function ImageRenderer({ url, filename }) {
  return (
    <div className="my-2 rounded-xl overflow-hidden border border-gray-200">
      <div className="px-3 py-1.5 bg-gray-50 border-b border-gray-200 text-xs text-gray-500">
        {filename}
      </div>
      <img
        src={url}
        alt={filename}
        loading="lazy"
        className="w-full object-contain max-h-96"
      />
    </div>
  );
}
```

---

## 五、前后端交互：SSE 流式通信

### 5.1 前端 SSE 客户端（lib/streaming.js）

```javascript
// 核心：读取 SSE 流，逐行解析 data: {...} 事件
export async function streamChat(message, uploadedFiles, sessionId, onEvent) {
  const formData = new FormData();
  formData.append("message", message);
  uploadedFiles.forEach(f => formData.append("files", f));

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "X-Session-ID": sessionId },
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // 保留不完整的最后一行
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch (e) {
          console.warn("SSE parse error:", e, line);
        }
      }
    }
  }
}
```

### 5.2 前端会话 ID（lib/session.js）

```javascript
// 兼容 HTTP（非 HTTPS）的 UUID 生成
function generateUUID() {
  if (typeof crypto?.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export function getOrCreateSessionId() {
  const key = "app_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `sess_${generateUUID()}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}
```

### 5.3 前端 SSE 事件处理（App.jsx 核心逻辑）

```javascript
// SSE 事件类型 → 对应的 block 类型
const handleSSEEvent = (event) => {
  switch (event.type) {
    case 'text_chunk':
      // 追加到最后一个 text block，或新建
      appendTextChunk(event.content);
      break;
    case 'tool_start':
      appendBlock({ type: 'tool_status', task_id: event.task_id, tool: event.tool, message: event.message, progress: 0 });
      break;
    case 'tool_progress':
      updateBlock(event.task_id, { message: event.message, progress: event.progress });
      break;
    case 'tool_result':
      updateBlock(event.task_id, { progress: 100 });
      event.files?.filter(f => f.render_type === 'image').forEach(f =>
        appendBlock({ type: 'image', url: f.url, filename: f.filename })
      );
      const downloads = event.files?.filter(f => ['download','csv'].includes(f.render_type));
      if (downloads?.length) appendBlock({ type: 'file_download', files: downloads });
      break;
    case 'csv_data':
      appendBlock({ type: 'csv_table', filename: event.filename, rows: event.rows, columns: event.columns });
      break;
    case 'chart_config':
      appendBlock({ type: 'chart', config: event.config });
      break;
    case 'image_url':
      appendBlock({ type: 'image', url: event.url, filename: event.filename });
      break;
    case 'warning':
      appendBlock({ type: 'warning', message: event.message });
      break;
    case 'error':
      appendBlock({ type: 'text', content: `❌ 错误：${event.message}` });
      break;
    case 'done':
      setIsLoading(false);
      break;
  }
};
```

### 5.4 消息状态管理（React 不可变更新模式）

```javascript
// 消息结构
// { role: 'user', content: '...' }
// { role: 'assistant', blocks: [{type, ...}, {type, ...}] }

const appendBlock = (block) => {
  setMessages(prev => {
    const msgs = [...prev];
    const last = msgs[msgs.length - 1];
    if (last?.role === 'assistant') {
      msgs[msgs.length - 1] = { ...last, blocks: [...last.blocks, block] };
    }
    return msgs;
  });
};

const appendTextChunk = (text) => {
  setMessages(prev => {
    const msgs = [...prev];
    const last = msgs[msgs.length - 1];
    if (last?.role === 'assistant') {
      const blocks = [...last.blocks];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === 'text') {
        blocks[blocks.length - 1] = { ...lastBlock, content: lastBlock.content + text };
      } else {
        blocks.push({ type: 'text', content: text });
      }
      msgs[msgs.length - 1] = { ...last, blocks };
    }
    return msgs;
  });
};

const updateBlock = (taskId, updates) => {
  setMessages(prev => {
    const msgs = [...prev];
    const last = msgs[msgs.length - 1];
    if (last?.role === 'assistant') {
      const blocks = last.blocks.map(b =>
        b.task_id === taskId ? { ...b, ...updates } : b
      );
      msgs[msgs.length - 1] = { ...last, blocks };
    }
    return msgs;
  });
};
```

### 5.5 发送消息主流程（handleSend）

```javascript
const handleSend = async () => {
  const text = input.trim();
  if ((!text && selectedFiles.length === 0) || isLoading) return;

  const currentFiles = [...selectedFiles];
  setInput('');
  setSelectedFiles([]);
  setIsLoading(true);

  // 1. 添加用户消息
  setMessages(prev => [...prev, { role: 'user', content: text }]);
  // 2. 添加空 AI 消息占位（将由 SSE 填充）
  setMessages(prev => [...prev, { role: 'assistant', blocks: [] }]);

  try {
    await streamChat(text, currentFiles, sessionId.current, handleSSEEvent);
  } catch (err) {
    appendBlock({ type: 'text', content: `连接错误：${err.message}` });
  } finally {
    setIsLoading(false);
  }
};
```

---

## 六、后端 FastAPI SSE 端点模式

### 6.1 主聊天端点（/api/chat）

```python
from fastapi import FastAPI, Form, File, UploadFile, Header
from fastapi.responses import StreamingResponse
import asyncio, json, uuid

app = FastAPI()

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    x_session_id: str | None = Header(default=None),
):
    session_id = x_session_id or f"sess_{uuid.uuid4().hex}"

    # 保存上传文件
    saved_paths = []
    for f in files:
        dest = UPLOAD_DIR / session_id / f.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = await f.read()
        dest.write_bytes(content)
        saved_paths.append(str(dest))

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def run():
            try:
                await run_agent(message, session_id, saved_paths, callback=queue.put)
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(None)  # 结束信号

        agent_task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            agent_task.cancel()  # 客户端断开时取消任务

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # 关闭 Nginx 缓冲（重要！）
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
```

### 6.2 SSE 事件格式规范

```python
# 后端发送的 SSE 事件类型（callback 参数传入的 dict）

# 文本流
{"type": "text_chunk", "content": "这是一段回复..."}

# 工具执行进度
{"type": "tool_start",    "task_id": "abc123", "tool": "工具名称", "message": "开始执行..."}
{"type": "tool_progress", "task_id": "abc123", "progress": 45, "message": "处理中..."}
{"type": "tool_result",   "task_id": "abc123", "files": [{"filename": "out.csv", "url": "...", "render_type": "csv"}]}

# 结构化数据
{"type": "csv_data",    "filename": "result.csv", "columns": ["A","B"], "rows": [{"A":1,"B":2}]}
{"type": "chart_config","config": { /* Chart.js config object */ }}
{"type": "image_url",   "url": "/download/sess_xxx/out.png", "filename": "out.png"}

# 通知
{"type": "warning", "message": "注意：数据存在缺失值"}
{"type": "error",   "message": "执行失败：...", "error_code": "TOOL_ERROR"}
{"type": "done"}  # 流结束
```

### 6.3 文件下载端点

```python
from fastapi.responses import FileResponse
from pathlib import Path

@app.get("/download/{session_id}/{filename:path}")
async def download_file(session_id: str, filename: str):
    file_path = OUTPUT_DIR / session_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(file_path, filename=Path(filename).name)
```

---

## 七、Vite 开发代理配置（vite.config.js）

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/download': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
```

---

## 八、Nginx 反向代理配置（生产环境）

```nginx
# nginx/default.conf
server {
    listen 80;

    # 关键：关闭 SSE 缓冲
    proxy_buffering off;
    proxy_cache off;

    location /api/ {
        proxy_pass http://api-server:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Connection '';  # SSE 需要保持连接
        proxy_read_timeout 3600s;        # 长任务超时设为 1 小时
    }

    location /download/ {
        proxy_pass http://file-server:8001/;
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://frontend-ui:80;
        proxy_set_header Host $host;
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 九、Docker Compose 最小服务模板

```yaml
# docker-compose.yml（精简版）
version: "3.9"

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on: [backend, frontend]

  backend:
    build: ./backend
    expose: ["8000"]
    env_file: .env.docker
    volumes:
      - shared_outputs:/data/outputs
      - shared_uploads:/data/uploads
    command: uvicorn main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    expose: ["80"]

  redis:
    image: redis:alpine
    expose: ["6379"]
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru

volumes:
  shared_outputs:
  shared_uploads:
```

---

## 十、package.json 关键依赖

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.468.0",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.5",
    "tailwindcss": "^3.4.17",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49"
  }
}
```

## Python 后端关键依赖（requirements.txt）

```txt
fastapi>=0.115
uvicorn[standard]>=0.30
python-multipart>=0.0.12   # 支持 Form + File 上传
redis>=5.0
aiofiles>=24.0
```

---

## 十一、Markdown 渲染（AI 回复中的富文本）

```jsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 在 AI 消息的 text block 中使用
<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  className="prose prose-sm max-w-none text-gray-800"
  components={{
    // 代码块样式
    code({ inline, className, children }) {
      return inline
        ? <code className="bg-gray-100 text-pink-600 px-1 py-0.5 rounded text-xs font-mono">{children}</code>
        : <pre className="bg-gray-900 text-gray-100 rounded-xl p-4 overflow-auto text-xs font-mono my-2"><code>{children}</code></pre>;
    },
    // 链接在新标签页打开
    a({ href, children }) {
      return <a href={href} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">{children}</a>;
    },
  }}
>
  {block.content}
</ReactMarkdown>
```

---

## 十二、本地开发启动命令

```bash
# 前端
cd frontend && npm install && npm run dev      # http://localhost:5173

# 后端
cd backend && uvicorn main:app --reload --port 8000

# Redis（Windows）
C:\Users\<user>\redis\redis-server.exe redis.windows.conf

# Docker 全栈（生产）
docker-compose up --build -d
docker-compose logs -f backend  # 查看后端日志
```

---

## 十三、新项目应用本模板的注意事项

1. **保持 `/api/` 路径前缀**：前端用相对路径，Vite dev proxy 和 Nginx 统一拦截，不需要硬编码后端地址。

2. **SSE 必须关闭 Nginx proxy_buffering**：否则数据会被缓冲，前端收不到实时更新。

3. **X-Session-ID Header**：跨请求维持会话，不要用 Cookie（CORS 更简单）。

4. **事件类型扩展**：新项目可以添加自定义 `type`，前端 `handleSSEEvent` 的 `switch` 中增加对应 case 即可。

5. **文件上传白名单**：后端务必验证文件扩展名，不要接受 `.exe`、`.sh` 等危险文件。

6. **agent_task.cancel() in finally**：客户端断开连接（关闭浏览器 Tab）时，必须取消后台任务，否则任务会继续跑消耗资源。

7. **`ensure_ascii=False`**：`json.dumps` 时加此参数，中文不会被转义成 `\uXXXX`。
