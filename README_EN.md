<div align="center">

<img src="HSL2.png" width="112" alt="HSL2 icon" />

# Hikari Server Launcher 2

**A modern desktop workspace for installing, running, maintaining, and extending Minecraft servers.**

[简体中文](README.md) · [Installation](docs/INSTALL.en.md) · [Usage](USAGE.md) · [Contributing](CONTRIBUTING.md)

[![Release](https://img.shields.io/github/v/release/Hikari16665/HikariServerLauncher2?style=flat-square&color=d44a7a)](https://github.com/Hikari16665/HikariServerLauncher2/releases)
[![Downloads](https://img.shields.io/github/downloads/Hikari16665/HikariServerLauncher2/total?style=flat-square&color=4a8ad4)](https://github.com/Hikari16665/HikariServerLauncher2/releases)
[![License](https://img.shields.io/github/license/Hikari16665/HikariServerLauncher2?style=flat-square&color=2d9d6f)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows_x64-5a6878?style=flat-square)
![Tauri](https://img.shields.io/badge/Tauri-2.x-24C8DB?style=flat-square&logo=tauri&logoColor=white)

</div>

![HSL2 workspace overview](docs/assets/readme-banner.svg)

HSL2 is a desktop management suite for Minecraft server owners. It prepares Java and server files, manages multiple instances, and brings the terminal, files, configuration, backups, marketplace, and diagnostics into one workspace. The desktop client and backend can run together or on separate machines.

## Why HSL2

| Install & run | Daily operations | Add-on ecosystem |
| --- | --- | --- |
| Vanilla, Paper, Forge, NeoForge, and Fabric | WebSocket console, task progress, and download speed | Modrinth mod and plugin marketplace |
| Automatic Java and server runtime preparation | Files, configuration, backups, and restore | Compatible-version filtering and dependency installation |
| Graphical launcher for combined or separate deployment | EULA, authentication, distance, and compatibility diagnostics | `.mrpack` import with server-side incompatibility filtering |

## Highlights

- **Multi-instance workspace** — Create, start, stop, and maintain servers across loaders and versions.
- **Live task system** — Receive stages, subtasks, progress, transfer speed, and actionable errors over WebSocket.
- **Server console** — Follow logs in real time, send commands, and control the server process lifecycle.
- **Mod and plugin marketplace** — Search, filter, and install compatible Modrinth projects for a selected server.
- **Add-on management** — Inspect mods, plugins, and Jar-in-Jar metadata; enable, edit, or remove content.
- **Modpack import** — Read `.mrpack` archives, re-check overrides, and remove client-only content.
- **Pre-flight diagnostics** — Check EULA, online mode, dependencies, runtime compatibility, and high-load settings.
- **Mainland China network support** — Select mirror sources and inspect carrier-network conditions.

## How it works

<div align="center">
  <img src="app/src/assets/hero.png" width="260" alt="HSL2 layered workspace artwork" />
</div>

HSL2 combines a desktop application, a graphical launcher, and a backend service. The launcher can start the complete environment, the frontend only, or the backend only. On Windows, the backend can also start automatically after sign-in. A floating workspace control opens management tools only when needed instead of keeping one large window on screen.

## Get started

Download the Windows installer from [Releases](https://github.com/Hikari16665/HikariServerLauncher2/releases), then follow the [English installation guide](docs/INSTALL.en.md).

> Windows x64 is the primary release target. Keep the administration key shown during first launch private; anyone with this key may gain management access to the backend.

## Technology

| Desktop | Backend | Realtime & data |
| --- | --- | --- |
| Tauri 2, Rust, React, TypeScript, Vite | Python, Flask, PyInstaller | WebSocket, Zustand, Modrinth API |

## Documentation

- [Installation Guide (English)](docs/INSTALL.en.md)
- [安装指南（中文）](docs/INSTALL.zh-CN.md)
- [Usage Guide](USAGE.md)
- [API Reference](API_DOC.md)
- [Contributing](CONTRIBUTING.md)
- [GPL-3.0 License](LICENSE)

## Contributing

Issues, feature proposals, and pull requests are welcome. Read the [contribution guide](CONTRIBUTING.md) before submitting changes, and make sure backend tests, frontend lint, Rust tests, and the production build pass.

---

<div align="center">
Maintained by <a href="https://github.com/Hikari16665">Hikari16665</a> · Continued from <a href="https://github.com/HikariRevivalProject/HikariServerLauncher">Hikari Server Launcher</a>
</div>
