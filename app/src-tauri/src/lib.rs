use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::OnceLock;
use std::time::Duration;
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

#[derive(Debug, Serialize, Deserialize)]
struct ProxyRequest {
    url: String,
    method: String,
    headers: HashMap<String, String>,
    body: Option<String>,
}

#[derive(Debug, Serialize)]
struct ProxyResponse {
    status: u16,
    body: String,
    error: Option<String>,
}

#[tauri::command]
async fn proxy_fetch(req: ProxyRequest) -> ProxyResponse {
    let result = tauri::async_runtime::spawn_blocking(move || {
        let method = req.method.to_uppercase();
        let mut r = match method.as_str() {
            "GET" => agent().get(&req.url),
            "POST" => agent().post(&req.url),
            "PUT" => agent().put(&req.url),
            "DELETE" => agent().delete(&req.url),
            _ => agent().get(&req.url),
        };

        for (k, v) in &req.headers {
            r = r.set(k, v);
        }

        let result = if let Some(body) = &req.body {
            r.send_string(body)
        } else {
            r.send_string("")
        };

        match result {
            Ok(resp) => {
                let status = resp.status();
                let body = resp.into_string().unwrap_or_default();
                ProxyResponse { status, body, error: None }
            }
            Err(ureq::Error::Status(status, resp)) => {
                let body = resp.into_string().unwrap_or_default();
                ProxyResponse { status, body, error: None }
            }
            Err(ureq::Error::Transport(t)) => {
                ProxyResponse { status: 0, body: String::new(), error: Some(t.to_string()) }
            }
        }
    }).await;

    match result {
        Ok(resp) => resp,
        Err(e) => ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some(format!("proxy_fetch task failed: {e}")),
        },
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct ProxyUploadRequest {
    url: String,
    file_data: String,  // base64
    file_name: String,
    token: String,
}

fn agent() -> &'static ureq::Agent {
    static AGENT: OnceLock<ureq::Agent> = OnceLock::new();
    AGENT.get_or_init(|| {
        ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(10))
            .timeout_read(Duration::from_secs(30))
            .timeout_write(Duration::from_secs(30))
            .timeout(Duration::from_secs(60))
            .max_idle_connections(10)
            .max_idle_connections_per_host(4)
            .build()
    })
}

#[tauri::command]
async fn proxy_upload(req: ProxyUploadRequest) -> ProxyResponse {
    let result = tauri::async_runtime::spawn_blocking(move || {
        use base64::Engine as _;
        let file_bytes = match base64::engine::general_purpose::STANDARD.decode(&req.file_data) {
            Ok(b) => b,
            Err(e) => return ProxyResponse { status: 0, body: String::new(), error: Some(format!("base64 decode: {e}")) },
        };

        let boundary = "----HslUploadBoundary";
        let mut body = Vec::new();
        body.extend_from_slice(format!("--{boundary}\r\n").as_bytes());
        body.extend_from_slice(format!("Content-Disposition: form-data; name=\"file\"; filename=\"{}\"\r\n", req.file_name).as_bytes());
        body.extend_from_slice(b"Content-Type: application/octet-stream\r\n\r\n");
        body.extend_from_slice(&file_bytes);
        body.extend_from_slice(format!("\r\n--{boundary}--\r\n").as_bytes());

        let content_type = format!("multipart/form-data; boundary={boundary}");
        match agent().post(&req.url).set("Authorization", &format!("Bearer {}", req.token)).set("Content-Type", &content_type).send_bytes(&body) {
            Ok(resp) => {
                let status = resp.status();
                let resp_body = resp.into_string().unwrap_or_default();
                ProxyResponse { status, body: resp_body, error: None }
            }
            Err(ureq::Error::Status(status, resp)) => {
                let resp_body = resp.into_string().unwrap_or_default();
                ProxyResponse { status, body: resp_body, error: None }
            }
            Err(ureq::Error::Transport(t)) => {
                ProxyResponse { status: 0, body: String::new(), error: Some(t.to_string()) }
            }
        }
    }).await;

    match result {
        Ok(resp) => resp,
        Err(e) => ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some(format!("proxy_upload task failed: {e}")),
        },
    }
}

#[tauri::command]
fn win_is_maximized(window: tauri::Window) -> bool {
    window.is_maximized().unwrap_or(false)
}

#[tauri::command]
fn win_minimize(window: tauri::Window) {
    let _ = window.minimize();
}

#[tauri::command]
fn win_toggle_maximize(window: tauri::Window) {
    if window.is_maximized().unwrap_or(false) {
        let _ = window.unmaximize();
    } else {
        let _ = window.maximize();
    }
}

#[tauri::command]
fn win_close(window: tauri::Window) {
    let _ = window.close();
}

#[tauri::command]
fn win_start_dragging(window: tauri::Window) {
    let _ = window.start_dragging();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![proxy_fetch, proxy_upload, win_minimize, win_toggle_maximize, win_close, win_is_maximized, win_start_dragging])
        .setup(|app| {
            // Build tray menu
            let show = MenuItemBuilder::with_id("show", "显示窗口").build(app)?;
            let quit = MenuItemBuilder::with_id("quit", "退出").build(app)?;
            let menu = MenuBuilder::new(app)
                .item(&show)
                .item(&quit)
                .build()?;

            // Build tray icon
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("Hikari Server Launcher")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // Handle close → hide to tray
            let window = app.get_webview_window("main").unwrap();
            let window_clone = window.clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window_clone.hide();
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
