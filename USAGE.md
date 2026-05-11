# 启动方式

## Linux

```bash
./start.sh
```

脚本会自动设置 Wayland 兼容环境变量并依次启动后端和前端。

### 环境变量说明

- `GDK_BACKEND=x11` — 在 Wayland 会话下强制使用 X11 后端，解决 GTK3/webkit2gtk 协议错误
- `WEBKIT_DISABLE_COMPOSITING_MODE=1` — 禁用 GPU 合成，解决部分显卡驱动下的渲染异常
- `WEBKIT_FORCE_SANDBOX=0` — 禁用 webkit2gtk 沙箱，兼容较新内核的 seccomp 策略

## Windows

双击 `start.bat` 即可启动。

---

# 引导

1. 默认地址为 http://127.0.0.1:5000，您无需修改。
2. Server 启动后将在目录下生成 `config.yml`，打开后可在 `admin-key` 中找到生成的管理密码，在引导中进行粘贴即可。
3. 如果您位于中国大陆境内，可以点击优先选择镜像源。
4. 您可以随时在设置页面切换镜像源。
