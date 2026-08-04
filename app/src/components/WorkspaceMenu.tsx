import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";
import WorkspaceIcon from "./WorkspaceIcon";

const items = [
  ["servers", "/servers", "服务器", "运行、停止与管理实例"],
  ["install", "/install", "安装服务器", "创建服务端和运行环境"],
  ["import", "/import", "导入服务器", "从 mrpack 创建服务器"],
  ["market", "/market", "市场", "安装兼容模组或插件"],
  ["addons", "/addons", "附加管理", "启用、停用或删除附加"],
  ["diagnostics", "/diagnostics", "服务器检测", "检查配置与兼容问题"],
  ["settings", "/settings", "设置", "连接、下载与主题"],
  ["about", "/about", "关于", "版本与开源许可"],
] as const;

export default function WorkspaceMenu() {
  const ready = useSettings((state) => state.onboardingDone && Boolean(state.token));
  const open = (label: string, route: string, title: string) => invoke("open_workspace_window", { label, route, title });
  return <main className="workspace-menu-window">
    <header data-tauri-drag-region><div><strong>HSL2</strong><span>工作区</span></div><button aria-label="打开主页" onClick={() => invoke("show_home")}><WorkspaceIcon name="home" /></button></header>
    {!ready && <button className="workspace-menu-setup" onClick={() => invoke("show_home")}>请先在主页完成连接设置</button>}
    <nav>{items.map(([icon, route, title, detail]) => <button key={route} disabled={!ready} onClick={() => open(icon, route, title)}><i><WorkspaceIcon name={icon}/></i><span><strong>{title}</strong><small>{detail}</small></span><b>›</b></button>)}</nav>
  </main>;
}
