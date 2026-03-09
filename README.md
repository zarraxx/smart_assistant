# Smart Assistant

Chinese version: `README.zh-CN.md`

Smart Assistant is a FastAPI backend for chat sessions, Dify chat proxying, and session-level Socket.IO communication.

## Features

- Create chat sessions with `/chat/create`
- Proxy Dify chat requests with `/chat/completion`
- Open a session-level Socket.IO channel at `/socket.io`
- Provide a demo page at `/` with:
  - left side: chat UI
  - right side: Socket.IO debug panel

## Run

Start the server from the project root:

```bash
python -m src.startup
```

## Configuration

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `SERVER_HOST` | string | `0.0.0.0` | Web server host |
| `SERVER_PORT` | integer | `8000` | Web server port |
| `SERVER_RELOAD` | boolean | `true` | Enable auto reload |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis connection URL |
| `DEFAULT_DIFY_URL` | string | `http://127.0.0.1:5001` | Dify base URL |
| `DEFAULT_DIFY_API_KEY` | string | empty | Dify API key |
| `SESSION_DEFAULT_EXPIRE_SECONDS` | integer | `1200` | Default session TTL |
| `SESSION_KEY_PREFIX` | string | `smart-assistant:session` | Redis key prefix |
| `ROOT_PATH` | string | `/` | Reverse-proxy subpath support |

## API Overview

| Path | Method | Description |
| --- | --- | --- |
| `/chat/create` | `POST` | Create a chat session and return `session_id` |
| `/chat/completion` | `POST` | Proxy Dify chat completion requests using `session_id` |
| `/socket.io` | `Socket.IO` | Session-level realtime message channel |
| `/mcp/smart-tools` | `MCP HTTP` | MCP tools that can trigger session-scoped client actions |
| `/` | `GET` | Demo page |

## `POST /chat/create`

Creates a new chat session.

### Request body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | string | yes | User identifier |
| `title` | string | no | Session title |
| `expire_seconds` | integer | no | Session TTL in seconds |
| `client_capabilities` | string[] | no | Client capability list |
| `metadata` | object | no | Extra metadata |

### Example response

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "sess_c6444707cb9d4f0b9f9022cc66a3935a",
    "user_id": "u10001",
    "title": "New Session",
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

Proxies Dify `chat-messages` requests.

### Request body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `session_id` | string | yes | Local chat session id |
| `inputs` | object | no | App variable input, default `{}` |
| `query` | string | yes | User query |
| `user` | string | yes | User identifier |
| `response_mode` | string | no | `streaming` or `blocking`, default `streaming` |
| `files` | object[] | no | File list in Dify format |
| `auto_generate_name` | boolean | no | Whether to auto-generate a session title |

### Conversation binding mechanism

- The client no longer sends `conversation_id`
- The backend loads the session record from Redis using `session_id`
- If Redis already contains `conversation_id`, the backend injects it into the outgoing Dify request
- If Redis does not contain `conversation_id`, the backend reads it from the first Dify response that contains one and stores it back into the session record
- All later requests only need the same `session_id`

### Example request

```json
{
  "session_id": "sess_c6444707cb9d4f0b9f9022cc66a3935a",
  "inputs": {},
  "query": "Please summarize today's work plan",
  "user": "u10001",
  "response_mode": "streaming"
}
```

## Socket.IO

### Connection model

- Path: `/socket.io`
- The client connects after `/chat/create`
- The client passes `auth.sessionId`
- The server joins the connection into the room named by `session_id`
- Default event name: `message`

### Server-to-client function message

```json
{
  "type": "function",
  "name": "showDepartmentAppointment",
  "params": {}
}
```

Built-in frontend handlers:

- `showDepartmentAppointment`
- `showPatientReportModal`
- `showQueueModal`

Frontend behavior:

- If no modal is open, open the target modal directly
- If the same modal is already open, do nothing
- If a different modal is open, close it first and then open the target modal

### Debug echo message

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

When the server receives this payload, it sends back `params` to the same Socket.IO client through the `message` event.

## MCP Tools

MCP is mounted under `/mcp`, and the Smart Tools HTTP app is exposed at `/mcp/smart-tools`.

### `showDepartmentAppointmentModal`

- Purpose: send a Socket.IO function event to the client bound to the given session
- Parameter: `session_id` is the Dify `session_id` used to identify the current chat session and route the event to the correct Socket.IO room
- Emitted Socket.IO event name: `message`

### Emitted payload

```json
{
  "type": "function",
  "name": "showDepartmentAppointment",
  "params": {}
}
```

### `showPatientReportModal`

- Purpose: send a Socket.IO function event to the client bound to the given session and open the patient report modal
- Parameter: `session_id` is the Dify `session_id` used to identify the current chat session and route the event to the correct Socket.IO room
- Emitted Socket.IO event name: `message`

### Emitted payload

```json
{
  "type": "function",
  "name": "showPatientReportModal",
  "params": {}
}
```

### `showQueueModal`

- Purpose: send a Socket.IO function event to the client bound to the given session and open the queue modal
- Parameter: `session_id` is the Dify `session_id` used to identify the current chat session and route the event to the correct Socket.IO room
- Emitted Socket.IO event name: `message`

### Emitted payload

```json
{
  "type": "function",
  "name": "showQueueModal",
  "params": {}
}
```

## Demo Page

Open `/` to use the built-in demo page:

- Left side: chat UI
- Right side: Socket.IO debug panel
- The page shows the current `session_id`
- The page no longer exposes `conversation_id`

## Notes

- All requests and responses use UTF-8 encoding
- `/chat/create` depends on Redis
- Reuse the same `session_id` when continuing the same chat session
- If documentation and code differ, treat the code as the source of truth
