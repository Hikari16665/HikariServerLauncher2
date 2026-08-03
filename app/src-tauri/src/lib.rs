use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{Cursor, Read, Seek, SeekFrom, Write};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex, OnceLock,
};
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

fn validate_proxy_url(value: &str) -> Result<(), String> {
    let parsed = url::Url::parse(value).map_err(|_| "Invalid backend URL".to_string())?;
    if !matches!(parsed.scheme(), "http" | "https") || parsed.host_str().is_none() {
        return Err("Only HTTP and HTTPS backend URLs are supported".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("Credentials must not be embedded in the backend URL".to_string());
    }
    Ok(())
}

#[tauri::command]
async fn proxy_fetch(req: ProxyRequest) -> ProxyResponse {
    if let Err(error) = validate_proxy_url(&req.url) {
        return ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some(error),
        };
    }
    if req
        .body
        .as_ref()
        .is_some_and(|body| body.len() > 8 * 1024 * 1024)
    {
        return ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some("Request body exceeds 8 MB".to_string()),
        };
    }
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
            if matches!(
                k.to_ascii_lowercase().as_str(),
                "authorization" | "content-type" | "accept"
            ) {
                r = r.set(k, v);
            }
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
                ProxyResponse {
                    status,
                    body,
                    error: None,
                }
            }
            Err(ureq::Error::Status(status, resp)) => {
                let body = resp.into_string().unwrap_or_default();
                ProxyResponse {
                    status,
                    body,
                    error: None,
                }
            }
            Err(ureq::Error::Transport(t)) => ProxyResponse {
                status: 0,
                body: String::new(),
                error: Some(t.to_string()),
            },
        }
    })
    .await;

    match result {
        Ok(resp) => resp,
        Err(e) => ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some(format!("proxy_fetch task failed: {e}")),
        },
    }
}

const MAX_UPLOAD_BYTES: u64 = 512 * 1024 * 1024;
const MAX_UPLOAD_CHUNK_BYTES: usize = 4 * 1024 * 1024;
const MAX_UPLOAD_SESSIONS: usize = 8;

#[derive(Debug, Deserialize)]
struct ProxyUploadBeginRequest {
    url: String,
    file_name: String,
    token: String,
    file_size: u64,
}

#[derive(Debug, Deserialize)]
struct ProxyUploadChunkRequest {
    upload_id: String,
    file_data: String,
}

#[derive(Debug, Deserialize)]
struct ProxyUploadSessionRequest {
    upload_id: String,
}

#[derive(Debug, Serialize)]
struct ProxyUploadBeginResult {
    upload_id: String,
}

struct UploadSession {
    file: tempfile::NamedTempFile,
    url: String,
    file_name: String,
    token: String,
    expected_size: u64,
    received: u64,
    cancelled: Arc<AtomicBool>,
}

struct CancellableReader<R> {
    inner: R,
    cancelled: Arc<AtomicBool>,
}

impl<R: Read> Read for CancellableReader<R> {
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        if self.cancelled.load(Ordering::Relaxed) {
            return Err(std::io::Error::new(
                std::io::ErrorKind::Interrupted,
                "Upload cancelled",
            ));
        }
        self.inner.read(buffer)
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct ProxyDownloadRequest {
    url: String,
    file_name: String,
    token: String,
}

#[derive(Debug, Serialize)]
struct ProxyDownloadResult {
    saved: bool,
    path: Option<String>,
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

fn upload_sessions() -> &'static Mutex<HashMap<String, UploadSession>> {
    static SESSIONS: OnceLock<Mutex<HashMap<String, UploadSession>>> = OnceLock::new();
    SESSIONS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn finishing_uploads() -> &'static Mutex<HashMap<String, Arc<AtomicBool>>> {
    static FINISHING: OnceLock<Mutex<HashMap<String, Arc<AtomicBool>>>> = OnceLock::new();
    FINISHING.get_or_init(|| Mutex::new(HashMap::new()))
}

fn upload_agent() -> &'static ureq::Agent {
    static AGENT: OnceLock<ureq::Agent> = OnceLock::new();
    AGENT.get_or_init(|| {
        ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(10))
            .timeout_read(Duration::from_secs(60))
            .timeout_write(Duration::from_secs(120))
            .timeout(Duration::from_secs(30 * 60))
            .max_idle_connections(2)
            .max_idle_connections_per_host(2)
            .build()
    })
}

fn validate_upload_filename(value: &str) -> Result<(), String> {
    if value.is_empty()
        || value == "."
        || value == ".."
        || value.contains(['/', '\\', '\r', '\n', '"'])
    {
        return Err("Invalid upload filename".to_string());
    }
    Ok(())
}

#[tauri::command]
fn proxy_upload_begin(req: ProxyUploadBeginRequest) -> Result<ProxyUploadBeginResult, String> {
    validate_proxy_url(&req.url)?;
    validate_upload_filename(&req.file_name)?;
    if req.file_size > MAX_UPLOAD_BYTES {
        return Err("Upload exceeds 512 MB".to_string());
    }
    let upload_id = uuid::Uuid::new_v4().to_string();
    let session = UploadSession {
        file: tempfile::NamedTempFile::new().map_err(|error| error.to_string())?,
        url: req.url,
        file_name: req.file_name,
        token: req.token,
        expected_size: req.file_size,
        received: 0,
        cancelled: Arc::new(AtomicBool::new(false)),
    };
    let mut sessions = upload_sessions()
        .lock()
        .map_err(|_| "Upload session lock is poisoned".to_string())?;
    if sessions.len() >= MAX_UPLOAD_SESSIONS {
        return Err("Too many active upload sessions".to_string());
    }
    sessions.insert(upload_id.clone(), session);
    Ok(ProxyUploadBeginResult { upload_id })
}

#[tauri::command]
fn proxy_upload_chunk(req: ProxyUploadChunkRequest) -> Result<u64, String> {
    use base64::Engine as _;
    if req.file_data.len() > (MAX_UPLOAD_CHUNK_BYTES * 4 / 3) + 8 {
        return Err("Upload chunk is too large".to_string());
    }
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(req.file_data)
        .map_err(|error| format!("Invalid upload chunk: {error}"))?;
    if bytes.len() > MAX_UPLOAD_CHUNK_BYTES {
        return Err("Upload chunk is too large".to_string());
    }
    let mut sessions = upload_sessions()
        .lock()
        .map_err(|_| "Upload session lock is poisoned".to_string())?;
    let session = sessions
        .get_mut(&req.upload_id)
        .ok_or_else(|| "Upload session not found".to_string())?;
    let next_size = session.received + bytes.len() as u64;
    if next_size > session.expected_size {
        return Err("Upload exceeds declared file size".to_string());
    }
    session
        .file
        .as_file_mut()
        .write_all(&bytes)
        .map_err(|error| error.to_string())?;
    session.received = next_size;
    Ok(next_size)
}

#[tauri::command]
fn proxy_upload_abort(req: ProxyUploadSessionRequest) -> Result<(), String> {
    if let Some(session) = upload_sessions()
        .lock()
        .map_err(|_| "Upload session lock is poisoned".to_string())?
        .remove(&req.upload_id)
    {
        session.cancelled.store(true, Ordering::Relaxed);
        return Ok(());
    }
    if let Some(cancelled) = finishing_uploads()
        .lock()
        .map_err(|_| "Upload session lock is poisoned".to_string())?
        .get(&req.upload_id)
    {
        cancelled.store(true, Ordering::Relaxed);
    }
    Ok(())
}

fn response_from_ureq(result: Result<ureq::Response, ureq::Error>) -> ProxyResponse {
    match result {
        Ok(response) => ProxyResponse {
            status: response.status(),
            body: response.into_string().unwrap_or_default(),
            error: None,
        },
        Err(ureq::Error::Status(status, response)) => ProxyResponse {
            status,
            body: response.into_string().unwrap_or_default(),
            error: None,
        },
        Err(ureq::Error::Transport(error)) => ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some(error.to_string()),
        },
    }
}

#[tauri::command]
async fn proxy_upload_finish(req: ProxyUploadSessionRequest) -> ProxyResponse {
    let upload_id = req.upload_id;
    let session = match upload_sessions().lock() {
        Ok(mut sessions) => sessions.remove(&upload_id),
        Err(_) => {
            return ProxyResponse {
                status: 0,
                body: String::new(),
                error: Some("Upload session lock is poisoned".to_string()),
            }
        }
    };
    let Some(mut session) = session else {
        return ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some("Upload session not found".to_string()),
        };
    };
    if session.received != session.expected_size {
        return ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some("Upload is incomplete".to_string()),
        };
    }
    if let Ok(mut finishing) = finishing_uploads().lock() {
        finishing.insert(upload_id.clone(), Arc::clone(&session.cancelled));
    } else {
        return ProxyResponse {
            status: 0,
            body: String::new(),
            error: Some("Upload session lock is poisoned".to_string()),
        };
    }

    let result = tauri::async_runtime::spawn_blocking(move || {
        if let Err(error) = session.file.as_file_mut().flush() {
            return ProxyResponse { status: 0, body: String::new(), error: Some(error.to_string()) };
        }
        if let Err(error) = session.file.as_file_mut().seek(SeekFrom::Start(0)) {
            return ProxyResponse { status: 0, body: String::new(), error: Some(error.to_string()) };
        }
        let boundary = format!("----HslUpload{}", uuid::Uuid::new_v4().simple());
        let prefix = format!(
            "--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{}\"\r\nContent-Type: application/octet-stream\r\n\r\n",
            session.file_name
        ).into_bytes();
        let suffix = format!("\r\n--{boundary}--\r\n").into_bytes();
        let content_length = prefix.len() as u64 + session.expected_size + suffix.len() as u64;
        let reader = Cursor::new(prefix)
            .chain(session.file.as_file_mut().take(session.expected_size))
            .chain(Cursor::new(suffix));
        let reader = CancellableReader {
            inner: reader,
            cancelled: Arc::clone(&session.cancelled),
        };
        response_from_ureq(
            upload_agent()
                .post(&session.url)
                .set("Authorization", &format!("Bearer {}", session.token))
                .set("Content-Type", &format!("multipart/form-data; boundary={boundary}"))
                .set("Content-Length", &content_length.to_string())
                .send(reader),
        )
    }).await;
    if let Ok(mut finishing) = finishing_uploads().lock() {
        finishing.remove(&upload_id);
    }
    result.unwrap_or_else(|error| ProxyResponse {
        status: 0,
        body: String::new(),
        error: Some(format!("proxy_upload_finish task failed: {error}")),
    })
}

#[cfg(test)]
mod upload_tests {
    use super::*;
    use base64::Engine as _;
    use std::io::{Read, Write};
    use std::net::TcpListener;

    #[test]
    fn chunked_upload_writes_only_the_declared_size() {
        let begin = proxy_upload_begin(ProxyUploadBeginRequest {
            url: "http://127.0.0.1:5000/upload".to_string(),
            file_name: "server.jar".to_string(),
            token: "test".to_string(),
            file_size: 3,
        })
        .expect("session should start");
        let encoded = base64::engine::general_purpose::STANDARD.encode(b"jar");
        assert_eq!(
            proxy_upload_chunk(ProxyUploadChunkRequest {
                upload_id: begin.upload_id.clone(),
                file_data: encoded,
            })
            .expect("chunk should be accepted"),
            3
        );
        assert!(proxy_upload_chunk(ProxyUploadChunkRequest {
            upload_id: begin.upload_id.clone(),
            file_data: base64::engine::general_purpose::STANDARD.encode(b"x"),
        })
        .is_err());
        proxy_upload_abort(ProxyUploadSessionRequest {
            upload_id: begin.upload_id,
        })
        .expect("session should abort");
    }

    #[test]
    fn upload_rejects_unsafe_filename_and_oversize() {
        for file_name in ["", "..", "../server.jar", "bad\"name.jar"] {
            assert!(proxy_upload_begin(ProxyUploadBeginRequest {
                url: "http://127.0.0.1:5000/upload".to_string(),
                file_name: file_name.to_string(),
                token: "test".to_string(),
                file_size: 1,
            })
            .is_err());
        }
        assert!(proxy_upload_begin(ProxyUploadBeginRequest {
            url: "http://127.0.0.1:5000/upload".to_string(),
            file_name: "large.jar".to_string(),
            token: "test".to_string(),
            file_size: MAX_UPLOAD_BYTES + 1,
        })
        .is_err());
    }

    #[test]
    fn finish_streams_a_valid_multipart_request() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("test listener should bind");
        let address = listener
            .local_addr()
            .expect("listener should have an address");
        let server = std::thread::spawn(move || {
            let (mut socket, _) = listener.accept().expect("upload should connect");
            let mut request = Vec::new();
            let mut buffer = [0_u8; 8192];
            let header_end = loop {
                let count = socket
                    .read(&mut buffer)
                    .expect("request should be readable");
                assert!(count > 0, "request ended before headers");
                request.extend_from_slice(&buffer[..count]);
                if let Some(index) = request.windows(4).position(|part| part == b"\r\n\r\n") {
                    break index + 4;
                }
            };
            let headers = String::from_utf8_lossy(&request[..header_end]);
            let content_length = headers
                .lines()
                .find_map(|line| {
                    line.to_ascii_lowercase()
                        .strip_prefix("content-length: ")
                        .map(str::to_owned)
                })
                .expect("content length should exist")
                .parse::<usize>()
                .expect("content length should be numeric");
            while request.len() - header_end < content_length {
                let count = socket.read(&mut buffer).expect("body should be readable");
                assert!(count > 0, "request ended before body");
                request.extend_from_slice(&buffer[..count]);
            }
            socket
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
                .expect("response should be writable");
            request[header_end..header_end + content_length].to_vec()
        });

        let begin = proxy_upload_begin(ProxyUploadBeginRequest {
            url: format!("http://{address}/upload"),
            file_name: "server.jar".to_string(),
            token: "test-token".to_string(),
            file_size: 7,
        })
        .expect("session should start");
        proxy_upload_chunk(ProxyUploadChunkRequest {
            upload_id: begin.upload_id.clone(),
            file_data: base64::engine::general_purpose::STANDARD.encode(b"payload"),
        })
        .expect("chunk should be accepted");

        let response =
            tauri::async_runtime::block_on(proxy_upload_finish(ProxyUploadSessionRequest {
                upload_id: begin.upload_id,
            }));
        let multipart = server.join().expect("test server should finish");

        assert_eq!(response.status, 200);
        assert_eq!(response.body, "{}");
        assert!(multipart.windows(7).any(|part| part == b"payload"));
        assert!(multipart
            .windows(b"filename=\"server.jar\"".len())
            .any(|part| part == b"filename=\"server.jar\""));
    }
}

#[tauri::command]
async fn proxy_download(req: ProxyDownloadRequest) -> Result<ProxyDownloadResult, String> {
    validate_proxy_url(&req.url)?;
    if req.file_name.contains(['/', '\\', '\r', '\n']) || req.file_name.is_empty() {
        return Err("Invalid download filename".to_string());
    }

    tauri::async_runtime::spawn_blocking(move || {
        let Some(destination) = rfd::FileDialog::new()
            .set_file_name(&req.file_name)
            .save_file()
        else {
            return Ok(ProxyDownloadResult {
                saved: false,
                path: None,
            });
        };

        let response = agent()
            .get(&req.url)
            .set("Authorization", &format!("Bearer {}", req.token))
            .call()
            .map_err(|error| match error {
                ureq::Error::Status(status, response) => {
                    let detail = response.into_string().unwrap_or_default();
                    format!("Download failed with HTTP {status}: {detail}")
                }
                ureq::Error::Transport(error) => error.to_string(),
            })?;

        let parent = destination
            .parent()
            .ok_or_else(|| "Invalid destination directory".to_string())?;
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let temporary = parent.join(format!(".{}.{}.hsl-part", req.file_name, stamp));
        let backup = parent.join(format!(".{}.{}.hsl-backup", req.file_name, stamp));

        let mut source = response.into_reader();
        let mut target = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(|error| format!("Cannot create temporary download file: {error}"))?;
        if let Err(error) = std::io::copy(&mut source, &mut target) {
            let _ = std::fs::remove_file(&temporary);
            return Err(format!("Cannot save downloaded file: {error}"));
        }
        drop(target);

        let had_existing = destination.exists();
        if had_existing {
            std::fs::rename(&destination, &backup)
                .map_err(|error| format!("Cannot prepare existing destination: {error}"))?;
        }
        if let Err(error) = std::fs::rename(&temporary, &destination) {
            if had_existing {
                let _ = std::fs::rename(&backup, &destination);
            }
            let _ = std::fs::remove_file(&temporary);
            return Err(format!("Cannot finalize downloaded file: {error}"));
        }
        if had_existing {
            let _ = std::fs::remove_file(&backup);
        }

        Ok(ProxyDownloadResult {
            saved: true,
            path: Some(destination.to_string_lossy().into_owned()),
        })
    })
    .await
    .map_err(|error| format!("proxy_download task failed: {error}"))?
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
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            proxy_fetch,
            proxy_upload_begin,
            proxy_upload_chunk,
            proxy_upload_finish,
            proxy_upload_abort,
            proxy_download,
            win_minimize,
            win_toggle_maximize,
            win_close,
            win_is_maximized,
            win_start_dragging
        ])
        .setup(|app| {
            // Build tray menu
            let show = MenuItemBuilder::with_id("show", "显示窗口").build(app)?;
            let quit = MenuItemBuilder::with_id("quit", "退出").build(app)?;
            let menu = MenuBuilder::new(app).item(&show).item(&quit).build()?;

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
