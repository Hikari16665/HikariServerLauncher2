#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Wayland 兼容：GTK3/webkit2gtk 在纯 Wayland 下有兼容问题
if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
  export GDK_BACKEND=x11
fi

# webkit2gtk 渲染修复
export WEBKIT_DISABLE_COMPOSITING_MODE=1   # 禁用 GPU 合成（驱动兼容性问题）
export WEBKIT_FORCE_SANDBOX=0              # 禁用沙箱（较新内核的 seccomp 兼容）

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' SIGINT SIGTERM

echo "Hikari Server Launcher"
echo "======================"
echo ""

# Start backend
echo "[1/2] Starting backend server..."
"$SCRIPT_DIR/hsl-server/hsl-server" &
BACKEND_PID=$!

# Wait for backend to become ready
echo "Waiting for backend to become ready..."
until curl -s http://127.0.0.1:5000/api/ping > /dev/null 2>&1; do
  sleep 1
done

# Start frontend
echo "[2/2] Starting frontend..."
"$SCRIPT_DIR/hsl-app" &
FRONTEND_PID=$!

echo ""
echo "Backend running at: http://127.0.0.1:5000"
echo "Press Ctrl+C to stop all processes"
echo ""

wait
