# Dify 大模型到客户端界面能力桥接设计

## 1. 背景与目标

本项目并没有把“打开客户端界面”的能力直接塞进 Dify 聊天接口，而是拆成两条职责清晰的通道：

1. `POST /chat/completion` 负责代理 Dify 对话请求，并把本地 `session_id` 传入 Dify 工作流上下文。
2. `/mcp/smart-tools` 负责向 Dify 暴露可调用的 MCP Tool，这些 Tool 最终通过 Socket.IO 把“函数型指令”下发到指定浏览器会话。

这样做的核心目标有三点：

- 让大模型只感知“可调用工具”，不直接依赖前端实现细节。
- 让后端以 `session_id` 为统一路由键，把 Dify 请求、Socket.IO 连接、页面动作绑定到同一会话。
- 让客户端界面调用保持异步、实时、低耦合，便于后续新增更多界面动作。

## 2. 总体设计思想

### 2.1 统一以 `session_id` 贯穿三层

项目把本地会话标识 `session_id` 作为跨层主键：

- Web 前端先通过 `/chat/create` 创建本地聊天会话。
- 浏览器建立 Socket.IO 连接时，把 `session_id` 放进 `auth.sessionId`。
- 后端在 `/chat/completion` 中把 `session_id` 注入 Dify `inputs.__session_id__`。
- Dify 侧如果要调用客户端界面能力，需要把这个 `session_id` 作为 MCP Tool 入参传回后端。
- 后端再依据该 `session_id` 把事件投递到对应 Socket.IO room。

这意味着：Dify 不需要知道浏览器连接 ID，前端也不需要知道 Dify 的内部上下文对象，只需要围绕同一个 `session_id` 协作。

### 2.2 Chat 链路与 UI 调用链路分离

项目把“内容生成”和“界面操作”拆成两条链路：

- Chat 链路：浏览器 → `/chat/completion` → Dify。
- UI 调用链路：Dify → `/mcp/smart-tools` → Socket.IO → 浏览器函数分发。

两条链路通过 `session_id` 汇合，但彼此职责不同：

- Chat 链路负责上下文延续、`conversation_id` 绑定、SSE 转发。
- MCP 链路负责把工具调用转换成客户端可执行的函数消息。

这种拆分避免了把 UI 指令塞进聊天文本流，也避免了让 Socket.IO 直接承担对话代理职责。

### 2.3 以后端做“协议翻译层”

后端同时承担了两次协议翻译：

1. 把 Dify Tool 调用翻译成统一的 Socket.IO 消息载荷。
2. 把客户端动作抽象成 `type=function`、`name=<动作名>`、`params={}` 的轻量协议。

因此前后端的契约非常简单：

```json
{
  "type": "function",
  "name": "showPatientReportModal",
  "params": {}
}
```

前端只负责根据 `name` 找到对应 handler 并执行，不需要理解 MCP 或 Dify 的协议细节。

## 3. 关键模块与职责

### 3.1 应用装配层

`src/webapp/assistant_app.py`

- 挂载 `/socket.io` 到 `socket_asgi_app`
- 挂载 `/mcp` 到 `mcp_app`
- 注册 `/chat` 路由
- 提供 `/` Demo 页面
- 让 FastAPI 生命周期复用 `mcp_app.lifespan`

这一层决定了三条能力入口最终汇聚在一个 ASGI 应用里：聊天、MCP、Socket.IO。

### 3.2 Chat 会话与 Dify 代理

`src/webapp/routes/chat.py`

- `/chat/create` 负责创建本地 `session_id`
- Session 信息写入 Redis
- `/chat/completion` 读取 Session，并把 `__session_id__` 注入 Dify `inputs`
- 已存在的 `conversation_id` 会被自动带入 Dify 请求
- Dify 首次返回 `conversation_id` 后会反写 Redis，供后续请求复用

这里的关键点不是“单纯转发请求”，而是把本地聊天会话与 Dify 的对话会话稳定绑定起来。

### 3.3 Socket.IO 会话路由

`src/webapp/socketio_app.py`

- `resolve_session_id()` 从 `auth.sessionId` / `auth.session_id` 或查询串中提取会话标识
- `connect()` 在连接建立时把当前 socket 加入 `session_id` 对应 room
- `emit_session_event()` 统一按 room 广播消息
- `message()` 额外提供了一个 `echo/debug` 回环能力，便于前端调试函数消息

这里真正起作用的不是“点对点发给某个 sid”，而是“把当前浏览器连接映射进 session room”，后续所有 MCP 触发都直接按 `session_id` 投递。

### 3.4 MCP Tool 到 Socket.IO 的桥

`src/webapp/mcp/mcp_app.py`

- 使用 `FastMCP("Smart Tools")` 定义工具集
- `_show_client_modal()` 负责生成统一函数消息并调用 `emit_session_event()`
- `showDepartmentAppointmentModal()`、`showPatientReportModal()`、`showQueueModal()` 作为公开 Tool 暴露给 Dify
- `mcp.http_app(path='/smart-tools')` 将 Tool 以 HTTP 方式挂到 `/mcp/smart-tools`

这里的设计重点是复用 `_show_client_modal()` 抽象公共逻辑，避免每个 Tool 都复制一份 Socket.IO 下发代码。

### 3.5 前端函数分发与界面执行

`src/webapp/static/js/index.js`

- `createChatSession()` 调 `/chat/create`，并声明 `client_capabilities: ['socket.io']`
- `connectSocketSession()` 建立 Socket.IO 连接并传入 `auth: { sessionId }`
- `handleSocketMessage()` 校验 `type=function` 后按 `name` 分发到本地函数表
- `socketFunctionHandlers` 维护动作名到浏览器函数的映射
- `showDepartmentAppointment()` / `showPatientReportModal()` / `showQueueModal()` 负责最终展示界面

前端没有实现复杂 RPC，而是采用“受控函数白名单”模式：服务端只发函数名，浏览器只执行映射表里允许的动作，边界更清晰。

## 4. 实现路径回顾

## 4.1 路径一：浏览器先建立可路由的本地会话

1. 前端调用 `/chat/create`。
2. 后端生成 `sess_<uuid>` 形式的 `session_id`。
3. Session 写入 Redis，包含 `user_id`、`expire_seconds`、`client_capabilities` 等信息。
4. 前端拿到 `session_id` 后立即连接 `/socket.io`。
5. Socket.IO 服务端在 `connect()` 中把当前连接加入 `session_id` 房间。

此时，后端已经具备“按聊天会话精确找到浏览器连接”的能力。

## 4.2 路径二：聊天请求把本地会话传入 Dify

1. 前端发送 `/chat/completion`。
2. 后端通过 `session_id` 读取 Redis 中的 Session。
3. 后端向 Dify 请求体中注入：

```json
{
  "inputs": {
    "__session_id__": "sess_xxx"
  }
}
```

4. 如果 Session 已绑定 `conversation_id`，则自动带入 Dify 请求。
5. 如果还未绑定，后端从阻塞响应或流式 SSE 中提取 `conversation_id` 并写回 Redis。

这一步的价值是：Dify 后续工作流或 Tool 调用可以拿到 `__session_id__`，从而知道应该操作哪个前端会话。

## 4.3 路径三：Dify 通过 MCP Tool 请求客户端界面动作

1. Dify 在工作流 / Agent 运行过程中决定调用某个 MCP Tool。
2. Dify 向 `/mcp/smart-tools` 发起 Tool 调用，请求体中带上 `session_id`。
3. FastMCP 命中对应工具函数，例如 `showPatientReportModal(session_id)`。
4. 工具函数复用 `_show_client_modal()` 组装统一消息载荷。
5. 后端调用 `emit_session_event(session_id, payload)`。
6. Socket.IO 服务器把消息发到 `session_id` 对应房间。
7. 浏览器收到 `message` 事件后，`handleSocketMessage()` 按 `name` 调到本地 handler。
8. 浏览器最终打开相应弹窗。

这条链路让“模型决定调用什么界面能力”和“浏览器真正执行什么 UI 操作”之间只通过一个简单、稳定的协议耦合。

## 5. 关键数据约定

### 5.1 本地 Session 数据

存储位置：Redis

典型字段：

- `session_id`
- `user_id`
- `expire_seconds`
- `client_capabilities`
- `metadata`
- `created_at`
- `expires_at`
- `conversation_id`（首次与 Dify 对话后补写）

### 5.2 Dify 输入增强字段

后端自动注入：

- `inputs.__session_id__`

它的作用不是给前端直接使用，而是给 Dify Tool 调用时提供“回路由”参数来源。

### 5.3 Socket.IO 函数消息协议

当前消息结构：

```json
{
  "type": "function",
  "name": "showQueueModal",
  "params": {}
}
```

字段含义：

- `type`: 固定为 `function`，表示这是函数调用型消息
- `name`: 前端注册的函数名
- `params`: 预留参数对象，当前弹窗类动作暂为空

## 6. 这样设计的原因

### 6.1 避免让 Dify 直接感知前端实现

如果让 Dify 直接输出某种前端脚本或页面指令，耦合会非常高。当前实现只把 MCP Tool 暴露给 Dify，因此模型只需要理解“有哪些能力可调”，而不需要理解 DOM、Modal 结构或 Socket.IO API。

### 6.2 避免把浏览器连接标识暴露到模型侧

Socket 连接的 `sid` 是瞬时的、传输层的，不适合让模型持有。`session_id` 是业务层标识，稳定、可复用、可存储，也天然适合作为 Dify 工作流中的上下文字段。

### 6.3 便于水平扩展 UI 能力

新增一个客户端能力时，通常只需要改三处：

1. 在 `src/webapp/mcp/mcp_app.py` 新增一个 Tool。
2. 在 `src/webapp/static/js/index.js` 的 `socketFunctionHandlers` 注册一个新函数。
3. 在页面模板中提供对应界面或交互容器。

现有路由、会话绑定、Socket.IO 房间广播都不需要重写。

### 6.4 保持完整异步调用链

项目中关键链路基本保持异步：

- FastAPI 路由为 `async`
- Dify 网关使用 `AsyncChatClient`
- Socket.IO 服务端使用 `AsyncServer`
- MCP Tool 中的事件下发通过 `await emit_session_event(...)`

这和仓库中的异步规范是一致的，也避免了 UI 触发链路阻塞事件循环。

## 7. 当前边界与注意点

### 7.1 当前是单向 UI 触发，不是完整双向 RPC

现在的 MCP Tool 触发流程是：后端下发消息，前端执行界面动作。前端执行结果不会自动回传 MCP 调用结果；当前返回的是“事件已发出”的确认，而不是“页面已完成动作”的确认。

### 7.2 前端执行能力受白名单约束

前端只会执行 `socketFunctionHandlers` 中显式注册的函数。这样更安全，但也意味着：后端新增 Tool 后，如果前端没有同步注册 handler，消息会被识别为不支持的函数消息。

### 7.3 `session_id` 是整条链路的关键上下文

如果 Dify Tool 调用时没有正确携带 `session_id`，后端虽然可以成功执行 MCP Tool 代码，但事件无法路由到正确浏览器会话。因此在 Dify 侧编排 Tool 时，应显式透传 `__session_id__`。

## 8. 推荐扩展方向

### 8.1 为函数消息补充参数模型

当前 `params` 为空对象，后续可以扩展为业务参数，例如患者 ID、报告编号、科室编号。建议同步：

- MCP Tool 入参定义
- 后端 payload 结构
- 前端 handler 参数校验

### 8.2 增加客户端动作回执

可考虑新增一个“客户端执行成功 / 失败”的 Socket.IO 回执事件，使 MCP Tool 不只是“触发成功”，而能感知“页面动作是否已真正完成”。

### 8.3 增加能力声明校验

虽然 `/chat/create` 已记录 `client_capabilities`，但当前 MCP 下发时并未强校验。后续可以在下发前检查当前 Session 是否声明支持 `socket.io` 或某些更细粒度能力。

## 9. 代码定位索引

- 应用装配：`src/webapp/assistant_app.py`
- 聊天路由：`src/webapp/routes/chat.py`
- Session 持久化：`src/webapp/services/session_store.py`
- Dify 代理网关：`src/webapp/services/dify_chat.py`
- Socket.IO 服务：`src/webapp/socketio_app.py`
- MCP Tool：`src/webapp/mcp/mcp_app.py`
- 前端 Demo 与函数分发：`src/webapp/static/js/index.js`
- Demo 模板：`src/webapp/templates/index.html`

## 10. 配套图示

- 时序图：`doc/dify-ui-bridge-sequence.puml`
- 流程图：`doc/dify-ui-bridge-flow.puml`

可使用 PlantUML 渲染上述文件，以直观看到“Dify Tool 调用 → MCP → Socket.IO → 浏览器 UI”的执行路径。
