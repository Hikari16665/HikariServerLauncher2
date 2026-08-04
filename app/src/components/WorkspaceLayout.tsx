import { Outlet, useLocation } from "react-router-dom";
import TitleBar from "./TitleBar";

const titles: Record<string, string> = { servers: "服务器", install: "安装服务器", import: "导入服务器", market: "市场", addons: "附加管理", diagnostics: "服务器检测", settings: "设置", about: "关于", tasks: "任务" };

export default function WorkspaceLayout() {
  const segment = useLocation().pathname.split("/")[1] || "workspace";
  return <div className="workspace-page-window"><TitleBar title={titles[segment] || "服务器"} compact/><main className="workspace-page-content"><Outlet/></main></div>;
}
