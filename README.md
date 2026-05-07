# Hikari Server Launcher 2

Minecraft server hosting platform with a Python Flask backend, Tauri v2 (Rust) desktop shell, and React TypeScript frontend. Manage multiple Minecraft server instances across various server types through a unified desktop application.

## Features

- Multi-type server support: Vanilla, Paper, Forge, NeoForge, Fabric
- Desktop application with system tray minimization (Tauri v2 + Rust)
- Real-time server console via WebSocket terminal
- File browser with upload/download
- Configuration editor for server properties and plugin configs
- Backup system with restore
- Task queue with progress tracking
- Mirror source selection for users in mainland China
- Admin authentication with configurable keys

## Project Structure

```
HSL2/
├── app.py                    # Flask backend entry point
├── core/                     # Backend modules
│   ├── auth.py               # Authentication manager
│   ├── backup.py             # Backup/restore logic
│   ├── config.py             # Configuration management
│   ├── environment.py        # Environment setup
│   ├── logger.py             # Logging with Rich TUI
│   ├── server_creator.py     # Server installation orchestration
│   ├── server_file_manager.py# File operations
│   ├── server_process.py     # Process lifecycle management
│   ├── source.py             # Mirror source resolution
│   ├── spconfigs.py          # Server-specific config parsing
│   ├── task_manager.py       # Async task queue
│   ├── tui.py                # Terminal UI (Rich)
│   ├── version_resolver.py   # Version listing for all server types
│   └── workspace.py          # Workspace directory management
├── app/                      # Tauri + React frontend
│   ├── src-tauri/            # Rust backend (IPC proxy, tray, window control)
│   │   └── src/
│   │       ├── lib.rs        # Tauri commands: proxy_fetch, proxy_upload, window ops
│   │       └── main.rs       # Entry point
│   └── src/                  # React TypeScript frontend
│       ├── components/       # UI components (ConfigEditor, FileBrowser, Terminal, etc.)
│       ├── pages/            # Page views (Dashboard, ServerDetail, CreateServer, etc.)
│       ├── lib/              # API client and type definitions
│       └── store/            # Zustand state stores
├── example/                  # Reference: original HSL v1 codebase
├── install/                  # Default config templates
├── build.bat                 # Build script (PyInstaller + Tauri)
├── launcher.bat              # Runtime launcher
├── requirements.txt          # Python dependencies
└── pyinstaller.spec          # PyInstaller spec
```

## Quick Start

See [USAGE.md](USAGE.md) for launch instructions, setup guide, and known issues.

## Tech Stack

| Layer    | Technology                          |
|----------|-------------------------------------|
| Backend  | Python 3, Flask, Rich, PyInstaller  |
| Shell    | Tauri 2, Rust, ureq, tokio          |
| Frontend | React 18, TypeScript, Vite, Zustand |

## Build

Requires Python 3.10+, Node.js 20+, Rust toolchain (MSVC), and a Bash-compatible shell.

```batch
build.bat
```

Output is placed in `dist/` and packaged as `HSL2-Release.zip`.
