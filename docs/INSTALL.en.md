# HSL2 Installation Guide

[简体中文](INSTALL.zh-CN.md) · [Back to project home](../README_EN.md)

## Requirements

- Windows 10 or Windows 11 on x64
- At least 4 GB of available memory is recommended; actual usage depends on the server and modpack
- Network access to Minecraft, Java, and the selected server distribution
- Microsoft Edge WebView2 Runtime, which is already present on most supported Windows systems

HSL2 prepares a suitable Java runtime for each server, so a system-wide Java installation is not required.

## Install a release

1. Open the project [Releases](https://github.com/Hikari16665/HikariServerLauncher2/releases) page.
2. Download the latest installer named like `HSL2-2.0.0-windows-x86_64-setup.exe`.
3. Run the installer and optionally create a desktop shortcut.
4. Open **Hikari Server Launcher** from the Start menu or desktop.

The default installation directory is `%LOCALAPPDATA%\Programs\HSL2`. Installation is per-user and does not require administrator privileges.

## Choose a launch mode

HSL2 Launcher provides three modes:

- **Start complete environment**: starts the backend, waits until it is ready, and opens the desktop app. This is recommended for most users.
- **Frontend only**: connects the desktop app to an existing local or remote HSL2 backend.
- **Backend only**: exposes the API and server-hosting service without opening the management interface.

If this computer hosts servers continuously, enable backend autostart in the Launcher. This creates a sign-in startup entry for the current Windows user and can be disabled at any time.

## First connection

1. After the backend starts, the Launcher reads its `config.yml`.
2. Copy the administration key shown by the Launcher and store it securely.
3. In the desktop app, keep the default endpoint `http://127.0.0.1:5000`; enter the actual address when using a backend on another computer.
4. Enter the administration key and complete connection verification.
5. Choose whether download mirrors should be preferred for your network.

The administration key is a backend management credential. Do not share it with untrusted parties or commit it to a public repository.

## Update

Exit the Launcher, desktop app, and backend, then run the newer installer over the existing installation. Server data and configuration should not be stored inside the application directory; creating a backup before updating is still recommended.

## Uninstall

Remove Hikari Server Launcher from Windows Installed Apps. Before uninstalling, verify the location of server workspaces and backups. Do not remove server data while a server process is still writing to it.

## Build the complete installer from source

Windows contributors need:

- Python 3.12
- Node.js 20 or newer
- Rust stable and the MSVC C++ build tools
- Inno Setup 6

Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd app
npm install
cd ..
.\build.bat
```

The script runs release quality checks, builds the desktop app, Launcher, and backend, and then produces both a ZIP archive and Windows installer. Fix any failed quality gate instead of publishing an incomplete `dist` directory.

## Troubleshooting

### The desktop app cannot connect after the backend starts

Make sure the backend reports that it is ready, verify the address and port, and check that the firewall allows the selected port. The default port is `5000`.

### The administration key was lost

Inspect `config.yml` in the backend configuration location next to the installation, or reopen the Launcher so it can read the existing configuration. Avoid deleting the configuration, as doing so may generate a new key.

### Downloads are slow or fail

Switch the preferred download source in Settings and recreate the task. Some files may still be available only from their official source.
