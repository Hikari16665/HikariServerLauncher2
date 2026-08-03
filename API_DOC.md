# Hikari Server Launcher API 文档

Base URL: `http://127.0.0.1:5000`

## 鉴权

除 `/api/auth` 和 `/api/ping` 外，所有接口都需要鉴权。

**方式一：Bearer Token**
```
Authorization: Bearer <token>
```
Token 通过 `/api/auth` 获取，有效期 12 小时。

**方式二：Admin Key**
在请求 Body 中传入 `auth_key` 字段。

**WebSocket 鉴权**：建立连接后必须在 5 秒内发送首条鉴权消息：

```json
{"type": "auth", "token": "<token>"}
```

不要将 token 放在 WebSocket URL 中，以免凭据进入代理日志或 URL 历史。

---

## 接口列表

### 1. 鉴权

#### POST /api/auth
使用 Admin Key 换取 Bearer Token。

**Request Body (JSON)**
```json
{
  "auth_key": "kk5yv9zwlpdEDiCuXC_bV1wHabMWoSCVZcO338kHll4"
}
```

**Response 200**
```json
{
  "success": true,
  "token": "生成的token字符串",
  "expires_in": 43200
}
```

**Response 401**
```json
{
  "success": false,
  "error": "Invalid authentication key"
}
```

---

#### GET /api/auth/verify
验证 Token 是否有效。

**Headers**: `Authorization: Bearer <token>`

**Response 200**
```json
{"valid": true}
```

---

#### GET /api/auth/revoke
吊销 Token。

**Headers**: `Authorization: Bearer <token>`

**Response 200**
```json
{"success": true}
```

---

### 2. 服务器管理

#### GET /api/servers
获取所有服务器列表。

**Response 200**
```json
{
  "servers": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "我的服务器",
      "server_type": "Vanilla",
      "max_memory": 1024,
      "extra_args": "",
      "path": "D:\\Code\\HSL2\\workspace\\550e8400-...",
      "java_version": "21",
      "valid": true
    }
  ]
}
```

---

#### POST /api/servers/create
创建新服务器。返回服务器信息和 task_id，服务器安装（下载 jar、Java 等）在后台异步执行。

**Request Body (JSON)**
```json
{
  "name": "我的服务器",
  "server_type": "Vanilla",
  "max_memory": 2048,
  "extra_args": "",
  "java_version": "21",
  "version": "1.21.4"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 服务器名称，默认自动生成 |
| server_type | string | 否 | 服务器类型：Vanilla / Paper / Forge / Fabric / NeoForge / April，默认 Vanilla |
| max_memory | int | 否 | 最大内存(MB)，默认 1024 |
| extra_args | string | 否 | 额外 JVM 参数 |
| java_version | string | 否 | Java 版本，默认 "21" |
| version | string | 否 | MC 版本号（为空则自动获取最新） |

**Response 200**
```json
{
  "success": true,
  "server": {
    "uuid": "550e8400-...",
    "name": "我的服务器",
    "server_type": "Vanilla",
    "max_memory": 2048,
    "extra_args": "",
    "path": "D:\\Code\\HSL2\\workspace\\550e8400-...",
    "java_version": "21",
    "valid": true
  },
  "task_id": "abc123..."
}
```

---

#### GET /api/servers/:uuid
获取单个服务器详情。

**Response 200**
```json
{
  "server": {
    "uuid": "550e8400-...",
    "name": "我的服务器",
    "server_type": "Vanilla",
    "max_memory": 2048,
    "extra_args": "",
    "path": "...",
    "java_version": "21",
    "valid": true
  }
}
```

**Response 404**
```json
{"error": "Server not found"}
```

---

#### PUT /api/servers/:uuid
更新服务器元数据。

**Request Body (JSON)**
```json
{
  "name": "新名称",
  "max_memory": 4096,
  "extra_args": "-XX:+UseG1GC",
  "java_version": "17"
}
```
所有字段均为可选。

**Response 200**
```json
{
  "success": true,
  "server": { ... }
}
```

---

#### DELETE /api/servers/:uuid
删除服务器（同时删除文件）。

**Response 200**
```json
{"success": true}
```

---

### 3. 服务器进程管理

#### POST /api/servers/:uuid/start
启动服务器进程。

**Response 200**
```json
{
  "success": true,
  "message": "Server started (PID: 12345)",
  "status": {"running": true, "pid": 12345, "uptime": 0.5, "command": "java -Dfile.encoding=utf-8 ..."}
}
```

**Response 400**
```json
{"success": false, "error": "Server is already running"}
```

---

#### POST /api/servers/:uuid/stop
优雅停止服务器（发送 `stop` 命令到服务器 stdin）。

等待最多 60 秒让服务器自行关闭，超时后自动 force kill。

**Response 200**
```json
{"success": true, "message": "Server stopped gracefully"}
```

---

#### POST /api/servers/:uuid/kill
强制终止服务器进程（kill + psutil 级联杀子进程）。

**Response 200**
```json
{"success": true, "message": "Server killed"}
```

---

#### POST /api/servers/:uuid/command
向服务器 stdin 发送任意命令。

**Request Body (JSON)**
```json
{"command": "say Hello World"}
```

**Response 200**
```json
{"success": true, "message": "Command sent"}
```

**Response 400**
```json
{"success": false, "error": "Server is not running"}
```

---

#### GET /api/servers/:uuid/status
查询服务器运行状态。

**Response 200 (运行中)**
```json
{
  "running": true,
  "pid": 12345,
  "uptime": 3600.5,
  "command": "java -Dfile.encoding=utf-8 -Xmx2048M -jar server.jar"
}
```

**Response 200 (未运行)**
```json
{"running": false}
```

---

### 4. 文件管理

所有文件路径 (`path`) 均为相对于服务器根目录的相对路径，使用 `/` 分隔。
路径穿越攻击（如 `../../../etc/passwd`）被自动拦截。

#### GET /api/servers/:uuid/files
列出服务器目录内容。

**Query Params**: `?path=config` 列出子目录（可选，默认根目录）

**Response 200**
```json
{
  "path": "config",
  "items": [
    {
      "name": "paper-global.yml",
      "path": "config/paper-global.yml",
      "type": "file",
      "size": 1234,
      "modified": "2026-05-06T18:00:00"
    },
    {
      "name": "paper-world-defaults.yml",
      "path": "config/paper-world-defaults.yml",
      "type": "file",
      "size": 5678,
      "modified": "2026-05-06T18:00:00"
    }
  ]
}
```

---

#### GET /api/servers/:uuid/files/read
读取文件内容。

**Query Params**: `?path=server.properties`

**Response 200**
```json
{
  "name": "server.properties",
  "path": "server.properties",
  "type": "file",
  "size": 2345,
  "modified": "2026-05-06T18:00:00",
  "content": "server-port=25565\nonline-mode=true\nmotd=A Minecraft Server\n..."
}
```

---

#### POST /api/servers/:uuid/files
创建新文件或空文件夹。

**Request Body (JSON)**
```json
{
  "path": "newfolder/hello.txt",
  "type": "file",
  "content": "Hello Minecraft"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 是 | 相对路径 |
| type | string | 否 | `"file"` (默认) 或 `"folder"`。创建文件夹时忽略 content |
| content | string | 否 | 文件内容（仅 type=file 时有效） |

**Response 200**
```json
{"name": "hello.txt", "path": "newfolder/hello.txt", "type": "file", "size": 15, "modified": "..."}
```

---

#### PUT /api/servers/:uuid/files
写入文件完整内容（覆盖）。父目录不存在时自动创建。

**Request Body (JSON)**
```json
{
  "path": "server.properties",
  "content": "server-port=25566\n..."
}
```

**Response 200**
```json
{"name": "server.properties", "path": "server.properties", "type": "file", "size": 1234, "modified": "..."}
```

**限制**: 不允许编辑 `.hslmeta` 元数据文件。

---

#### DELETE /api/servers/:uuid/files
删除文件或文件夹。

**Query Params**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 是 | 要删除的路径 |
| recursive | string | 否 | `"true"` 递归删除文件夹及所有子文件（默认 `"false"`） |

非递归删除时，文件夹必须为空才能删除。

**Response 200**
```json
{"success": true, "path": "oldconfig/server.properties"}
```

**Response 400 (文件夹非空)**
```json
{"error": "Directory not empty. Use recursive=true to delete recursively"}
```

**限制**: 不允许删除 `.hslmeta` 或服务器根目录。

---

### 5. 特定配置 (spconfigs)

#### GET /api/servers/:uuid/spconfigs
获取服务器当前可编辑的配置文件及当前值。

**Response 200**
```json
{
  "configs": [
    {
      "name": "server.properties",
      "path": "server.properties",
      "description": "Minecraft服务器基本配置文件 包含端口，人数，正版等",
      "type": "properties",
      "keys": [
        {
          "name": "服务器端口",
          "key": "server-port",
          "description": "服务器将监听的端口（默认：25565）",
          "tips": "只有你确定才要更改...",
          "type": "int",
          "current_value": "25565",
          "danger": false
        }
      ]
    }
  ]
}
```

仅返回服务器上实际存在对应文件的配置。当前支持的配置文件：

| 名称 | 文件路径 | 类型 | 适用服务器 |
|------|----------|------|------------|
| server.properties | server.properties | properties | 全部 |
| bukkit.yml | bukkit.yml | yml | Paper/Forge/Fabric |
| Paper 世界设置 | config/paper-world-defaults.yml | yml | Paper |
| Paper 总设置 | config/paper-global.yml | yml | Paper |

---

#### PUT /api/servers/:uuid/spconfigs/:path
修改服务器配置项。

URL 中的 `:path` 对应配置文件的路径（如 `server.properties`）。

**Request Body (JSON)**
```json
{
  "key": "server-port",
  "value": "25566"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | 是 | 配置键的 key（嵌套用 `.` 分割，如 `settings.allow-end`） |
| value | string/int/bool | 是 | 新值，类型由配置项定义 |

**Response 200**
```json
{"success": true, "key": "server-port", "value": "25566"}
```

**Response 400** (类型不匹配)
```json
{"success": false, "error": "Type mismatch: expected int"}
```

**Response 400** (选项无效)
```json
{"success": false, "error": "Invalid choice 'xxx'. Valid: ['peaceful', 'easy', 'normal', 'hard']"}
```

---

### 6. 任务管理

#### POST /api/servers/create 返回的 task 跟踪

服务端安装任务会在后台执行，包含以下步骤：
1. 检查/下载 Java 运行环境
2. 下载对应类型服务端 JAR
3. 写入 eula.txt

#### GET /api/tasks
获取所有任务列表。支持按状态过滤。

**Query Params**: `?status=running` (可选: pending / running / completed / failed / cancelled)

**Response 200**
```json
{
  "tasks": [
    {
      "task_id": "abc123...",
      "status": "running",
      "progress": 45.5,
      "progress_message": "Downloading server.jar...",
      "error_message": null,
      "created_at": 1715000000.0,
      "started_at": 1715000001.0,
      "completed_at": null,
      "result": null
    }
  ]
}
```

---

#### GET /api/tasks/:task_id
获取单个任务的详情和进度。

**Response 200**
```json
{
  "task_id": "abc123...",
  "status": "running",
  "progress": 75.0,
  "progress_message": "Downloading Java 21...",
  "error_message": null,
  "created_at": 1715000000.0,
  "started_at": 1715000001.0,
  "completed_at": null,
  "result": null
}
```

任务完成后：
```json
{
  "task_id": "abc123...",
  "status": "completed",
  "progress": 100.0,
  "progress_message": "Server created successfully",
  "result": {
    "server_uuid": "550e8400-...",
    "server_type": "Vanilla",
    "java_version": "21",
    "java_binary": "D:\\Code\\HSL2\\java\\21\\bin\\java.exe",
    "jar_path": "D:\\Code\\HSL2\\workspace\\550e8400-...\\server.jar"
  }
}
```

---

### 7. 版本列表

所有版本接口支持通过 `?use_mirror=true` 参数优先使用镜像源（逆向轮询源列表，镜像优先）。

#### GET /api/versions/vanilla
获取 Vanilla (原版) Minecraft 版本列表。

**Query Params**: `?use_mirror=true` 优先使用 BMCLAPI 镜像

**Response 200**
```json
{
  "releases": [
    {"id": "1.21.4", "type": "release", "release_time": "2024-12-03T..."},
    {"id": "1.21.3", "type": "release", "release_time": "2024-10-23T..."}
  ],
  "snapshots": [
    {"id": "25w14craftmine", "type": "snapshot", "release_time": "..."}
  ],
  "source_type": "bmclapi"
}
```

---

#### GET /api/versions/paper
获取 Paper 最新版本信息和可用构建列表。

**Response 200**
```json
{
  "latest_stable": {
    "version": "1.21.4",
    "download_url": "https://api.papermc.io/v2/projects/paper/versions/1.21.4/builds/190/downloads/paper-1.21.4-190.jar"
  },
  "latest_experimental": {
    "version": "1.21.4",
    "download_url": "https://api.papermc.io/v2/projects/paper/versions/1.21.4/builds/190/downloads/paper-1.21.4-190.jar"
  },
  "latest_version_builds": [
    {"build": 190, "version": "1.21.4", "channel": "default"}
  ]
}
```

---

#### GET /api/versions/april
获取愚人节 Minecraft 版本列表。

**Response 200**
```json
{
  "versions": [
    {
      "name": "2025-25w14craftmine",
      "version": "1.21.5",
      "download_url": "https://piston-data.mojang.com/v1/objects/4527a9019e37e001770787e4523b505f79cac4c5/server.jar"
    }
  ]
}
```

---

#### GET /api/versions/forge
获取 Forge 支持的 MC 版本或指定 MC 版本的 Forge 构建列表。

**Query Params**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mc_version | string | 否 | MC 版本号，不传则返回支持的 MC 版本列表 |
| use_mirror | string | 否 | `"true"` 优先使用 BMCLAPI 镜像（逆向轮询） |

**不传 mc_version 时的 Response 200**
```json
{
  "mc_versions": ["1.21.4", "1.21.3", "1.21.1", ...],
  "source_type": "bmclapi"
}
```

**传 mc_version 时的 Response 200**
```json
{
  "mc_version": "1.21.4",
  "forge_versions": [
    {
      "version": "1.21.4-51.0.21",
      "build": 123,
      "mc_version": "1.21.4",
      "installer_url": "https://bmclapi2.bangbang93.com/forge/download"
    }
  ],
  "source_type": "bmclapi"
}
```

**镜像优先说明**: Forge 的官方源 (`official`) 和镜像源 (`bmclapi`) 分别对应 `source.json` 中的源条目。`use_mirror=true` 时将反向轮询列表，优先尝试镜像。响应中的 `source_type` 指示实际使用的源类型。

---

#### GET /api/versions/neoforge
获取 NeoForge 版本列表。

**Query Params**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mc_version | string | 否 | MC 版本号 |
| use_mirror | string | 否 | `"true"` 优先使用镜像源 |

**Response 200**
```json
{
  "mc_versions": ["1.21.4", "1.21.3", ...],
  "neoforge_versions": [...],
  "source_type": "official"
}
```

---

#### GET /api/versions/fabric
获取 Fabric 支持的 MC 版本和最新 Loader 版本。

**Query Params**: `?use_mirror=true` (Fabric 目前仅官方源，参数保留用于 API 一致性)

**Response 200**
```json
{
  "mc_versions": [
    {"version": "1.21.4", "stable": true},
    {"version": "1.21.3", "stable": true}
  ],
  "loader_versions": ["0.16.10", "0.16.9", ...],
  "latest_loader": "0.16.10"
}
```

---

#### GET /api/versions/java
获取可用的 Java 版本及下载链接。OS 由服务端自动判断。

**Query Params**: `?use_mirror=true` 优先使用 lingyi 镜像源

**Response 200**
```json
{
  "os": "windows",
  "versions": [
    {
      "version": "21",
      "source": "GloryGods",
      "source_label": "normal",
      "download_url": "https://jdk.114914.xyz/jdk-21.zip",
      "os": "windows"
    },
    {
      "version": "21",
      "source": "lingyi",
      "source_label": "mirror",
      "download_url": "https://ipv4wp.axzzz.top:9503/f/dd1Mil/java21.zip",
      "os": "windows"
    }
  ]
}
```

**源说明**:
| source | source_label | 类型 |
|--------|-------------|------|
| GloryGods | normal | 普通源 |
| lingyi | mirror | 镜像源 |

**`use_mirror` 行为**: 默认顺序 GloryGods → lingyi。`use_mirror=true` 时逆转为 lingyi → GloryGods，使镜像源排在前面。OS 类型 (`windows`/`linux`) 由服务端根据运行环境自动选择。

---

### 8. Java 管理

#### GET /api/java/versions
获取已安装的 Java 版本列表。

**Response 200**
```json
{
  "versions": [
    {
      "version": "21",
      "installed": true,
      "binary_path": "D:\\Code\\HSL2\\java\\21\\bin\\java.exe"
    }
  ]
}
```

---

### 9. WebSocket - 服务器终端

#### WS /api/servers/:uuid/terminal
实时服务器控制台终端。双向通信。

`ws://127.0.0.1:5000/api/servers/550e8400-.../terminal`

**连接时**：客户端先发送 `auth` 消息。鉴权成功后服务器返回连接确认；若服务器已运行则回放历史日志缓冲（最近 2000 行），之后实时推送 stdout。

**服务端 → 客户端消息**：

| type | 说明 | 示例 |
|------|------|------|
| `status` | 状态通知 | `{"type":"status","message":"Connected to terminal for 我的服务器","server_uuid":"...","server_name":"我的服务器","running":true}` |
| `log` | 服务器 stdout 行 | `{"type":"log","line":"[12:00:00 INFO]: Done (3.520s)! For help, type \"help\""}` |
| `error` | 错误信息 | `{"type":"error","message":"Server is not running"}` |

**客户端 → 服务端消息**（第一条必须是鉴权消息）：

```json
{"type": "auth", "token": "<token>"}
{"type": "command", "command": "say Hello players!"}
```

发送任意命令到服务器 stdin。

**完整示例** (使用 wscat)：
```
wscat -c "ws://127.0.0.1:5000/api/servers/xxx/terminal"
Connected (press CTRL+C to quit)
> {"type":"auth","token":"yyy"}
< {"type":"status","message":"Connected to terminal for 我的服务器","server_uuid":"xxx","server_name":"我的服务器","running":true}
< {"type":"log","line":"[12:00:01 INFO]: Starting minecraft server..."}
< {"type":"log","line":"[12:00:04 INFO]: Done! For help, type \"help\""}
> {"type":"command","command":"list"}
< {"type":"log","line":"[12:00:10 INFO]: There are 0 of a max 20 players online:"}
```

#### WS /api/tasks/stream

实时推送任务快照和进度。连接后同样必须先发送 `auth` 消息；鉴权成功后服务端立即发送 `task_snapshot`，之后推送任务创建、进度、子任务与完成状态，无需轮询。

---

### 10. 启动脚本导出

#### GET /api/servers/:uuid/export
生成服务器启动脚本（.bat 或 .sh）。

**Query Params**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| format | string | 否 | `"batch"` (Windows) 或 `"shell"` (Linux)，默认 `"batch"` |

**Response 200**
```json
{
  "server_uuid": "550e8400-...",
  "format": "batch",
  "script": "@echo off\r\ncd /d \"D:\\...\"\r\njava -Xmx2048M -jar server.jar"
}
```

---

### 11. 备份管理

所有备份文件以 `<server_uuid>_YYYY-MM-DD_HH-MM-SS.zip` 格式命名。

#### POST /api/servers/:uuid/backups
创建服务器备份（异步任务）。

**Response 200**
```json
{"success": true, "task_id": "abc123...", "server_uuid": "550e8400-..."}
```

#### GET /api/servers/:uuid/backups
获取备份列表。

**Response 200**
```json
{
  "backups": [
    {"filename": "550e8400-_2026-05-06_19-00-00.zip", "server_uuid": "...", "size": 1048576, "created": "2026-05-06T19:00:00"}
  ],
  "server_uuid": "550e8400-..."
}
```

#### POST /api/servers/:uuid/backups/:filename/restore
从备份恢复服务器（异步任务）。会自动终止正在运行的服务器。

**Response 200**
```json
{"success": true, "task_id": "abc123...", "server_uuid": "...", "filename": "550e8400-_2026-05-06_19-00-00.zip"}
```

**Response 400**
```json
{"error": "Invalid backup filename"}
```

#### DELETE /api/servers/:uuid/backups/:filename
删除备份文件。文件名通过正则验证防止路径穿越。

**Response 200**
```json
{"success": true, "filename": "550e8400-_2026-05-06_19-00-00.zip"}
```

---

### 12. 其他

#### GET /api/ping
健康检查（无需鉴权）。

**Response 200**
```
pong!
```

---

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未鉴权或鉴权失败 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
