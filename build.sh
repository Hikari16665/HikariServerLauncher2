#!/bin/bash
set -e

# 避免 AppImage 打包时依赖 FUSE（在容器/无 FUSE 环境下需要）
export APPIMAGE_EXTRACT_AND_RUN=1
# linuxdeploy 自带的 strip 不支持新版 ELF 格式（.relr.dyn），跳过 strip
export NO_STRIP=true

ROOT="$(cd "$(dirname "$0")" && pwd)"
DIST_BASE="$ROOT/dist"

# Wine Windows Python 路径（用于交叉编译）
WINE_PYTHON="C:\\\\Python312\\\\python.exe"
WINE_PREFIX="/home/hikari/.wine_hsl"

# ============================================
#  Hikari Server Launcher - Build Script
# ============================================
#
# 用法:
#   ./build.sh                 # 构建 Linux (deb + appimage)
#   ./build.sh win             # 交叉编译 → Windows (需要 mingw-w64)
#   ./build.sh linux-arm64     # 交叉编译 → Linux ARM64
#   ./build.sh all             # 同时构建 Linux + Windows 两个发行版
#
# 交叉编译依赖:
#   Windows:  sudo pacman -S mingw-w64-gcc
#             rustup target add x86_64-pc-windows-gnu
#   ARM64:    sudo pacman -S aarch64-linux-gnu-gcc
#             rustup target add aarch64-unknown-linux-gnu
# ============================================

# ---------- 平台映射 ----------
platform_dir() {
  case "$1" in
    linux)     echo "linux-x86_64"  ;;
    win)       echo "windows-x64"   ;;
    linux-arm64) echo "linux-aarch64" ;;
  esac
}

# ---------- 确定 Python 解释器 ----------
detect_python() {
  if [ -f "/home/hikari/miniconda3/envs/hsl/bin/python" ]; then
    echo "/home/hikari/miniconda3/envs/hsl/bin/python"
  elif [ -f "$ROOT/.venv/bin/python3" ]; then
    echo "$ROOT/.venv/bin/python3"
  elif [ -f "$ROOT/.venv/bin/python" ]; then
    echo "$ROOT/.venv/bin/python"
  elif command -v python3 &>/dev/null; then
    echo "python3"
  else
    echo "python"
  fi
}

# ---------- Tauri 前端构建 ----------
build_tauri() {
  local target="$1"
  local tauri_target=""
  local bundles=""

  case "$target" in
    linux)
      bundles="deb,appimage"
      no_bundle=""
      TAURI_EXE_NAME="hsl-app"
      ;;
    win)
      tauri_target="x86_64-pc-windows-gnu"
      bundles=""
      no_bundle="--no-bundle"
      TAURI_EXE_NAME="hsl-app.exe"
      ;;
    linux-arm64)
      tauri_target="aarch64-unknown-linux-gnu"
      bundles="deb"
      no_bundle=""
      TAURI_EXE_NAME="hsl-app"
      ;;
  esac

  cd "$ROOT/app"
  echo "    Tauri target: ${tauri_target:-native}, bundles: ${bundles:-none}"

  if [ -n "$tauri_target" ]; then
    npx tauri build --target "$tauri_target" $no_bundle ${bundles:+--bundles "$bundles"}
  else
    npx tauri build $no_bundle ${bundles:+--bundles "$bundles"}
  fi

  # 复制前端二进制到 dist
  local plat_dir="$(platform_dir "$target")"
  local dist_dir="$DIST_BASE/$plat_dir"
  mkdir -p "$dist_dir"

  local binary=""
  case "$target" in
    linux)     binary="$ROOT/app/src-tauri/target/release/app" ;;
    win)       binary="$ROOT/app/src-tauri/target/x86_64-pc-windows-gnu/release/app.exe" ;;
    linux-arm64) binary="$ROOT/app/src-tauri/target/aarch64-unknown-linux-gnu/release/app" ;;
  esac

  if [ -f "$binary" ]; then
    cp "$binary" "$dist_dir/$TAURI_EXE_NAME"
    chmod +x "$dist_dir/$TAURI_EXE_NAME" 2>/dev/null || true
    echo "    Copied $TAURI_EXE_NAME"
  else
    echo "    WARNING: Tauri binary not found at $binary"
  fi
}

# ---------- 后端 PyInstaller 构建 ----------
build_backend() {
  local target="$1"
  local plat_dir="$(platform_dir "$target")"
  local dist_dir="$DIST_BASE/$plat_dir"
  mkdir -p "$dist_dir"

  cd "$ROOT"

  if [ "$target" = "win" ]; then
    # Windows: 通过 Wine 交叉编译
    echo "    Using Wine Python for Windows build"
    WINEPREFIX="$WINE_PREFIX" wine "$WINE_PYTHON" -m PyInstaller pyinstaller.spec \
      --distpath "$(winepath -w "$dist_dir")" \
      --workpath "$(winepath -w "$dist_dir/build-temp")" \
      --clean --noconfirm
  else
    # Linux: 原生构建
    local py="$(detect_python)"
    echo "    Using Python: $py"
    "$py" -m PyInstaller pyinstaller.spec \
      --distpath "$dist_dir" \
      --workpath "$dist_dir/build-temp" \
      --clean --noconfirm
  fi

  # PyInstaller 输出在 dist_dir/hsl-server/ 下，clean build-temp
  rm -rf "$dist_dir/build-temp"
}

# ---------- 收集辅助文件 ----------
collect_files() {
  local target="$1"
  local plat_dir="$(platform_dir "$target")"
  local dist_dir="$DIST_BASE/$plat_dir"

  # 启动脚本
  if [ "$target" = "win" ]; then
    [ -f "$ROOT/launcher.bat" ] && cp "$ROOT/launcher.bat" "$dist_dir/start.bat"
  else
    [ -f "$ROOT/launcher.sh" ] && cp "$ROOT/launcher.sh" "$dist_dir/start.sh" && chmod +x "$dist_dir/start.sh"
  fi

  [ -f "$ROOT/USAGE.md" ] && cp "$ROOT/USAGE.md" "$dist_dir/USAGE.md"
  [ -f "$ROOT/LICENSE" ]  && cp "$ROOT/LICENSE"  "$dist_dir/LICENSE"

  echo "    Collected: start script, USAGE.md, LICENSE"
}

# ---------- 打包 ----------
package() {
  local plat_dir="$1"
  local zip_name="HSL2-Release-$plat_dir.tar.gz"

  cd "$ROOT"
  if command -v tar &>/dev/null; then
    tar czf "$zip_name" -C "$DIST_BASE" "$plat_dir"
    echo "  Package: $ROOT/$zip_name"
  fi
}

# ---------- 单平台构建 ----------
build_platform() {
  local target="$1"
  local plat_dir="$(platform_dir "$target")"
  local dist_dir="$DIST_BASE/$plat_dir"

  echo ""
  echo "============================================"
  echo "  Building for: $target"
  echo "  Output:       $dist_dir"
  echo "============================================"
  echo ""

  # Clean
  rm -rf "$dist_dir"
  mkdir -p "$dist_dir"

  # Step 1: Tauri frontend
  echo "[1/3] Building frontend (Tauri)..."
  build_tauri "$target"

  # Step 2: PyInstaller backend
  echo "[2/3] Building backend (PyInstaller)..."
  build_backend "$target"

  # Step 3: Collect files & package
  echo "[3/3] Collecting files..."
  collect_files "$target"

  echo ""
  echo "  Build complete: $dist_dir"
}

# ============================================
#  Main
# ============================================

BUILD_TARGET="${1:-linux}"

case "$BUILD_TARGET" in
  linux|win|linux-arm64)
    build_platform "$BUILD_TARGET"
    package "$(platform_dir "$BUILD_TARGET")"
    ;;
  all)
    echo "============================================"
    echo "  Hikari Server Launcher - Full Distribution"
    echo "  Building: Linux + Windows"
    echo "============================================"

    build_platform "linux"
    build_platform "win"

    echo ""
    echo "============================================"
    echo "  All builds complete! Packaging..."
    echo "============================================"

    package "$(platform_dir linux)"
    package "$(platform_dir win)"

    echo ""
    echo "============================================"
    echo "  Distributions:"
    echo "    $DIST_BASE/$(platform_dir linux)/"
    echo "    $DIST_BASE/$(platform_dir win)/"
    echo "============================================"
    ;;
  *)
    echo "Usage: $0 [linux|win|linux-arm64|all]"
    exit 1
    ;;
esac
