#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    env,
    fs::{self, OpenOptions},
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;
#[cfg(windows)]
use winreg::{enums::HKEY_CURRENT_USER, RegKey};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const AUTOSTART_NAME: &str = "HSL2 Backend";

#[derive(Serialize)]
struct LauncherStatus {
    backend_available: bool,
    frontend_available: bool,
    backend_running: bool,
    port_conflict: bool,
    autostart_enabled: bool,
    install_dir: String,
    admin_key: Option<String>,
}

#[derive(Serialize)]
struct LaunchResult {
    message: String,
    admin_key: Option<String>,
}

#[derive(Deserialize)]
struct BackendConfig {
    auth: Option<AuthConfig>,
}

#[derive(Deserialize)]
struct AuthConfig {
    #[serde(
        rename = "admin-key",
        alias = "admin_key",
        alias = "api-key",
        alias = "api_key"
    )]
    admin_key: Option<String>,
}

fn executable_dir() -> Result<PathBuf, String> {
    env::current_exe()
        .map_err(|error| format!("Unable to locate the launcher: {error}"))?
        .parent()
        .map(Path::to_path_buf)
        .ok_or_else(|| "Unable to determine the launcher directory.".to_string())
}

fn install_dir() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("HSL2_INSTALL_DIR") {
        let path = PathBuf::from(value);
        if path.is_dir() {
            return Ok(path);
        }
    }

    let executable = executable_dir()?;
    if backend_path(&executable).exists() || frontend_path(&executable).exists() {
        return Ok(executable);
    }

    Err(
        "The HSL2 runtime was not found beside the launcher. Reinstall HSL2 or set HSL2_INSTALL_DIR."
            .to_string(),
    )
}

fn backend_path(root: &Path) -> PathBuf {
    root.join("hsl-server").join("hsl-server.exe")
}

fn frontend_path(root: &Path) -> PathBuf {
    root.join("hsl-app.exe")
}

fn read_admin_key(root: &Path) -> Option<String> {
    let candidates = [
        root.join("config.yml"),
        root.join("hsl-server").join("config.yml"),
    ];
    candidates.into_iter().find_map(|path| {
        let content = std::fs::read_to_string(path).ok()?;
        let config: BackendConfig = serde_yaml::from_str(&content).ok()?;
        let key = config.auth?.admin_key?.trim().to_string();
        if key.is_empty() || key.eq_ignore_ascii_case("PLACEHOLDER") {
            None
        } else {
            Some(key)
        }
    })
}

#[derive(PartialEq)]
enum BackendProbe {
    Ready,
    PortConflict,
    Offline,
}

fn probe_backend() -> BackendProbe {
    let address = SocketAddr::from(([127, 0, 0, 1], 5000));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(350)) else {
        return BackendProbe::Offline;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(700)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(700)));
    if stream
        .write_all(b"GET /api/ping HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return BackendProbe::PortConflict;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_ok()
        && response.starts_with("HTTP/1.1 200")
        && response
            .split("\r\n\r\n")
            .nth(1)
            .is_some_and(|body| body.trim() == "pong!")
    {
        BackendProbe::Ready
    } else {
        BackendProbe::PortConflict
    }
}

fn backend_is_running() -> bool {
    probe_backend() == BackendProbe::Ready
}

fn hidden_command(path: &Path, root: &Path) -> Command {
    let log_dir = root.join("logs");
    let _ = fs::create_dir_all(&log_dir);
    let output = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("launcher-backend.log"));
    let mut command = Command::new(path);
    command.current_dir(root).stdin(Stdio::null());
    if let Ok(stdout) = output {
        let stderr = stdout.try_clone().ok();
        command.stdout(Stdio::from(stdout));
        command.stderr(stderr.map(Stdio::from).unwrap_or_else(Stdio::null));
    } else {
        command.stdout(Stdio::null()).stderr(Stdio::null());
    }
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    command
}

fn start_backend(root: &Path) -> Result<bool, String> {
    match probe_backend() {
        BackendProbe::Ready => return Ok(false),
        BackendProbe::PortConflict => return Err(
            "Port 5000 is occupied by another program, not HSL2. Close it or change the HSL2 port."
                .to_string(),
        ),
        BackendProbe::Offline => {}
    }

    let path = backend_path(root);
    if !path.exists() {
        return Err(format!(
            "Backend executable was not found: {}",
            path.display()
        ));
    }

    hidden_command(&path, root)
        .spawn()
        .map_err(|error| format!("Unable to start the backend: {error}"))?;
    Ok(true)
}

fn wait_for_backend(timeout: Duration) -> bool {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if backend_is_running() {
            return true;
        }
        thread::sleep(Duration::from_millis(350));
    }
    false
}

fn start_frontend(root: &Path) -> Result<(), String> {
    let path = frontend_path(root);
    if !path.exists() {
        return Err(format!(
            "Frontend executable was not found: {}",
            path.display()
        ));
    }

    Command::new(&path)
        .current_dir(root)
        .spawn()
        .map_err(|error| format!("Unable to start the frontend: {error}"))?;
    Ok(())
}

#[cfg(windows)]
fn autostart_enabled() -> bool {
    RegKey::predef(HKEY_CURRENT_USER)
        .open_subkey("Software\\Microsoft\\Windows\\CurrentVersion\\Run")
        .and_then(|key| key.get_value::<String, _>(AUTOSTART_NAME))
        .is_ok()
}

#[cfg(not(windows))]
fn autostart_enabled() -> bool {
    false
}

#[cfg(windows)]
fn update_autostart(enabled: bool) -> Result<(), String> {
    let key = RegKey::predef(HKEY_CURRENT_USER)
        .create_subkey("Software\\Microsoft\\Windows\\CurrentVersion\\Run")
        .map_err(|error| format!("Unable to open the current-user startup registry key: {error}"))?
        .0;

    if enabled {
        let executable = env::current_exe()
            .map_err(|error| format!("Unable to locate the launcher: {error}"))?;
        let value = format!("\"{}\" --backend-only", executable.display());
        key.set_value(AUTOSTART_NAME, &value)
            .map_err(|error| format!("Unable to create the startup entry: {error}"))
    } else {
        match key.delete_value(AUTOSTART_NAME) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(error) => Err(format!("Unable to remove the startup entry: {error}")),
        }
    }
}

#[cfg(not(windows))]
fn update_autostart(_enabled: bool) -> Result<(), String> {
    Err("Backend autostart is only supported on Windows.".to_string())
}

#[tauri::command]
fn get_status() -> LauncherStatus {
    let root = install_dir().unwrap_or_default();
    let probe = probe_backend();
    LauncherStatus {
        backend_available: backend_path(&root).exists(),
        frontend_available: frontend_path(&root).exists(),
        backend_running: probe == BackendProbe::Ready,
        port_conflict: probe == BackendProbe::PortConflict,
        autostart_enabled: autostart_enabled(),
        install_dir: root.display().to_string(),
        admin_key: read_admin_key(&root),
    }
}

#[tauri::command]
async fn launch_mode(mode: String) -> Result<LaunchResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let root = install_dir()?;
        match mode.as_str() {
            "full" => {
                start_backend(&root)?;
                if !wait_for_backend(Duration::from_secs(35)) {
                    return Err(
                        "The backend started but did not become ready within 35 seconds. Check the logs directory."
                            .to_string(),
                    );
                }
                start_frontend(&root)?;
                Ok(LaunchResult { message: "后端已就绪，前端已打开".to_string(), admin_key: read_admin_key(&root) })
            }
            "frontend" => {
                start_frontend(&root)?;
                Ok(LaunchResult { message: "前端已打开".to_string(), admin_key: read_admin_key(&root) })
            }
            "backend" => {
                let started = start_backend(&root)?;
                let message = if started {
                    "后端已在后台启动"
                } else {
                    "后端已经在运行"
                };
                if started && !wait_for_backend(Duration::from_secs(35)) {
                    return Err("The backend started but did not become ready within 35 seconds. Check the logs directory.".to_string());
                }
                Ok(LaunchResult { message: message.to_string(), admin_key: read_admin_key(&root) })
            }
            _ => Err("Unknown launch mode.".to_string()),
        }
    })
    .await
    .map_err(|error| format!("Launch task failed: {error}"))?
}

#[tauri::command]
fn set_backend_autostart(enabled: bool) -> Result<bool, String> {
    update_autostart(enabled)?;
    Ok(autostart_enabled())
}

fn run_backend_only() -> Result<(), String> {
    let root = install_dir()?;
    start_backend(&root)?;
    Ok(())
}

fn main() {
    if env::args().any(|argument| argument == "--backend-only") {
        let _ = run_backend_only();
        return;
    }

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_status,
            launch_mode,
            set_backend_autostart
        ])
        .run(tauri::generate_context!())
        .expect("HSL2 launcher failed");
}
