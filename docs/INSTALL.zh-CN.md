# HSL2 安装指南

[English](INSTALL.en.md) · [返回项目首页](../README.md)

## 系统要求

- Windows 10 或 Windows 11，x64 架构
- 建议至少 4 GB 可用内存；实际需求取决于服务器和模组数量
- 能够访问 Minecraft、Java 和所选服务端的下载来源
- Microsoft Edge WebView2 Runtime（多数受支持的 Windows 系统已安装）

HSL2 会为服务器准备合适的 Java 运行环境，无需预先安装 Java。

## 使用安装器

1. 打开项目的 [Releases](https://github.com/Hikari16665/HikariServerLauncher2/releases) 页面。
2. 下载名称类似 `HSL2-2.0.0-windows-x86_64-setup.exe` 的最新安装器。
3. 运行安装器并选择是否创建桌面快捷方式。
4. 从开始菜单或桌面打开 **Hikari Server Launcher**。

安装器默认将程序安装到当前用户的 `%LOCALAPPDATA%\Programs\HSL2`，不需要管理员权限。

## 选择启动方式

HSL2 Launcher 提供三种方式：

- **启动完整环境**：启动后端，等待其就绪，再打开桌面应用。大多数用户应选择此项。
- **仅启动前端**：连接到已经运行的本机或远程 HSL2 后端。
- **仅启动后端**：只提供 API 与服务器托管能力，不打开管理界面。

如果这台电脑长期托管服务器，可以在 Launcher 中启用后端自启动。该选项只为当前 Windows 用户创建登录启动项，可随时关闭。

## 首次连接

1. 启动后端后，Launcher 会读取后端的 `config.yml`。
2. 复制界面中显示的管理密钥，并妥善保存。
3. 打开桌面应用，在首次设置中保留默认地址 `http://127.0.0.1:5000`；如果后端位于其他电脑，请填写实际地址。
4. 输入管理密钥并完成连接验证。
5. 根据网络环境选择是否优先使用镜像源。

管理密钥相当于后端管理凭据。不要将它发送给不受信任的人，也不要提交到公开仓库。

## 更新

退出 HSL2 Launcher、桌面应用和后端后，运行新版本安装器覆盖安装。服务器数据与配置不应放在程序安装目录中；更新前仍建议对重要服务器创建备份。

## 卸载

在 Windows“已安装的应用”中卸载 Hikari Server Launcher。卸载前请确认服务器工作目录和备份的位置；不要在仍有服务器写入时删除相关数据。

## 从源码构建完整安装包

面向贡献者的 Windows 构建需要：

- Python 3.12
- Node.js 20 或更高版本
- Rust stable 与 MSVC C++ 构建工具
- Inno Setup 6

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd app
npm install
cd ..
.\build.bat
```

脚本会依次运行质量检查，构建桌面应用、Launcher 和后端，并生成 ZIP 与 Windows 安装器。构建失败时应先修复对应检查，不要发布不完整的 `dist` 目录。

## 常见问题

### 后端启动后前端无法连接

确认后端已经显示就绪、地址与端口正确，并检查防火墙是否允许所选端口。默认端口为 `5000`。

### 忘记管理密钥

在安装目录旁的后端配置目录中查看 `config.yml`，或重新打开 Launcher 让其读取现有配置。不要随意删除配置，否则可能生成新的密钥。

### 下载速度慢或失败

在设置中切换镜像来源，然后重新创建任务。部分文件仍可能只能从官方来源获取。
