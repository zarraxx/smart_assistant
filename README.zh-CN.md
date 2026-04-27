# Smart Assistant（中文）

对应英文版：`README.md`

Smart Assistant 是一个基于 FastAPI 的后端服务，提供聊天 Session、Dify 对话代理、LangChain/OpenAI 兼容对话，以及会话级 Socket.IO 通信能力。

## 功能概览

- 通过 `/chat/create` 创建聊天 Session
- 通过 `/chat/completion` 代理 Dify 对话请求
- 通过 `/chat/langchain` 运行内置 LangChain Agent 对话
- 通过 `/socket.io` 建立会话级实时通道
- 通过 `/` 打开内置 Demo 页面
  - 左侧：聊天 UI
  - 右侧：Socket.IO 调试面板

## 启动方式

在项目根目录执行：

```bash
python -m src.startup
```

## 配置项

| 名称 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `SERVER_HOST` | string | `0.0.0.0` | Web 服务监听地址 |
| `SERVER_PORT` | integer | `8000` | Web 服务监听端口 |
| `SERVER_RELOAD` | boolean | `true` | 是否开启自动重载 |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis 连接地址 |
| `DEFAULT_DIFY_URL` | string | `http://127.0.0.1:5001` | Dify 服务地址 |
| `DEFAULT_DIFY_API_KEY` | string | 空 | Dify API Key |
| `DEFAULT_CHAT_PROVIDER` | string | `langchain` | Demo 页面默认聊天后端，支持 `langchain` 或 `dify` |
| `OPENAI_BASE_URL` | string | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `/chat/langchain` 使用的 OpenAI 兼容服务地址 |
| `OPENAI_API_KEY` | string | 空 | `/chat/langchain` 使用的 OpenAI 兼容 API Key |
| `OPENAI_MODEL` | string | `deepseek-v3` | `/chat/langchain` 使用的模型名 |
| `SESSION_DEFAULT_EXPIRE_SECONDS` | integer | `1200` | Session 默认过期秒数 |
| `SESSION_KEY_PREFIX` | string | `smart-assistant:session` | Redis Key 前缀 |
| `ROOT_PATH` | string | `/smart_assistant` | 反向代理子路径支持 |

## 接口概览

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/chat/create` | `POST` | 创建聊天 Session 并返回 `session_id` |
| `/chat/completion` | `POST` | 基于 `session_id` 代理 Dify 对话请求 |
| `/chat/langchain` | `POST` | 基于 `session_id` 发起 LangChain Agent 对话 |
| `/socket.io` | `Socket.IO` | 会话级实时消息通道 |
| `/mcp/smart-tools` | `MCP HTTP` | 可触发会话级客户端动作的 MCP 工具入口 |
| `/` | `GET` | Demo 页面 |

## `POST /chat/create`

用于创建新的聊天 Session。

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `user_id` | string | 是 | 用户标识 |
| `title` | string | 否 | 会话标题 |
| `expire_seconds` | integer | 否 | 会话 TTL，单位秒 |
| `client_capabilities` | string[] | 否 | 客户端能力列表 |
| `metadata` | object | 否 | 扩展元数据 |

### 返回示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "sess_c6444707cb9d4f0b9f9022cc66a3935a",
    "user_id": "u10001",
    "title": "新会话",
    "expire_seconds": 1800,
    "client_capabilities": ["web_search", "vision", "socket.io"],
    "metadata": {
      "source": "web"
    },
    "created_at": "2026-03-09T02:00:00Z",
    "expires_at": "2026-03-09T02:30:00Z"
  }
}
```

## `POST /chat/completion`

用于代理 Dify `chat-messages` 请求。

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 本地聊天 Session ID |
| `inputs` | object | 否 | 应用变量输入，默认 `{}` |
| `query` | string | 是 | 用户问题 |
| `user` | string | 是 | 用户标识 |
| `response_mode` | string | 否 | `streaming` 或 `blocking`，默认 `streaming` |
| `files` | object[] | 否 | Dify 格式文件列表 |
| `auto_generate_name` | boolean | 否 | 是否自动生成会话标题 |

### 会话绑定机制

- 客户端不再传 `conversation_id`
- 后端通过 `session_id` 从 Redis 读取 Session 记录
- 如果 Redis 中已存在 `conversation_id`，后端会自动注入到发往 Dify 的请求
- 如果 Redis 中还没有 `conversation_id`，后端会从第一条包含该字段的 Dify 响应中提取并回写到 Session
- 后续继续对话时只需复用同一个 `session_id`

### 请求示例

```json
{
  "session_id": "sess_c6444707cb9d4f0b9f9022cc66a3935a",
  "inputs": {},
  "query": "请帮我总结今天的工作安排",
  "user": "u10001",
  "response_mode": "streaming"
}
```

## `POST /chat/langchain`

用于基于当前 `session_id` 运行内置 LangChain Agent。

### 请求参数

`/chat/langchain` 复用了 `/chat/completion` 的请求模型。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 本地聊天 Session ID，同时作为 LangGraph 的 `thread_id` |
| `inputs` | object | 否 | 兼容字段；后端会保留并自动注入 `__session_id__` |
| `query` | string | 是 | 用户问题 |
| `user` | string | 是 | 用户标识 |
| `response_mode` | string | 否 | `streaming` 或 `blocking`，默认 `streaming` |
| `files` | object[] | 否 | 为兼容保留，当前未使用 |
| `auto_generate_name` | boolean | 否 | 为兼容保留，当前未使用 |

### 会话行为

- 后端会先校验 `session_id` 是否存在于 Redis 中
- Agent 使用 `session_id` 作为 LangGraph 的 `thread_id`
- 复用同一个 `session_id` 时，可在当前进程内延续同一条 Agent 线程状态
- Agent 工具函数会向同一会话房间发送 Socket.IO `message` 事件

### 阻塞响应示例

```json
{
  "event": "message",
  "answer": "你好，我是 Smart Assistant。",
  "session_id": "sess_c6444707cb9d4f0b9f9022cc66a3935a"
}
```

### 流式响应示例

```text
data: {"event":"message","answer":"你好","session_id":"sess_c6444707cb9d4f0b9f9022cc66a3935a"}

data: {"event":"message","answer":"，我是 Smart Assistant。","session_id":"sess_c6444707cb9d4f0b9f9022cc66a3935a"}

data: [DONE]
```

## Socket.IO

### 连接模型

- 路径：`/socket.io`
- 客户端在 `/chat/create` 成功后建立连接
- 客户端通过 `auth.sessionId` 传入 Session ID
- 服务端会将连接加入 `session_id` 对应的房间
- 默认事件名：`message`

### 服务端下发函数消息

```json
{
  "type": "function",
  "name": "showDepartmentAppointment",
  "params": {}
}
```

前端内置支持：

- `showDepartmentAppointment`
- `showPatientReportModal`
- `showQueueModal`

前端行为规则：

- 没有弹窗打开时，直接打开目标界面
- 同一界面已打开时，不做任何动作
- 如果其他界面已打开，则先关闭再打开目标界面

### 调试回环消息

```json
{
  "type": "echo",
  "name": "debug",
  "params": {
    "type": "function",
    "name": "showPatientReportModal",
    "params": {}
  }
}
```

当服务端收到该消息时，会把 `params` 原样通过 `message` 事件回发给当前 Socket.IO 连接。

## MCP 工具

MCP 挂载在 `/mcp`，Smart Tools HTTP 应用暴露在 `/mcp/smart-tools`。

### `showDepartmentAppointmentModal`

- 用途：向指定会话绑定的客户端发送 Socket.IO 函数事件
- 参数：`session_id` 是当前聊天 Session 的标识，用于路由到正确的 Socket.IO 房间
- 下发事件名：`message`

### 下发载荷示例

```json
{
  "type": "function",
  "name": "showDepartmentAppointment",
  "params": {}
}
```

### `showPatientReportModal`

- 用途：向指定会话绑定的客户端发送 Socket.IO 函数事件，并打开报告弹窗
- 参数：`session_id` 是当前聊天 Session 的标识，用于路由到正确的 Socket.IO 房间
- 下发事件名：`message`

### 下发载荷示例

```json
{
  "type": "function",
  "name": "showPatientReportModal",
  "params": {}
}
```

### `showQueueModal`

- 用途：向指定会话绑定的客户端发送 Socket.IO 函数事件，并打开排队弹窗
- 参数：`session_id` 是当前聊天 Session 的标识，用于路由到正确的 Socket.IO 房间
- 下发事件名：`message`

### 下发载荷示例

```json
{
  "type": "function",
  "name": "showQueueModal",
  "params": {}
}
```

## Demo 页面

访问 `/` 可打开内置调试页面：

- 左侧：聊天 UI
- 右侧：Socket.IO 调试面板
- 页面会显示当前 `session_id`
- 默认聊天面板请求由 `DEFAULT_CHAT_PROVIDER` 控制
- 页面不再暴露 `conversation_id` 输入项

## 说明

- 所有请求与响应均使用 UTF-8 编码
- `/chat/create` 依赖 Redis
- 持续同一轮聊天时，请复用同一个 `session_id`
- 如文档与代码不一致，请以代码实现为准
