const paths: Record<string, React.ReactNode> = {
  home: <><path d="m4 11 8-7 8 7"/><path d="M6 10v10h12V10M10 20v-6h4v6"/></>,
  servers: <><rect x="3" y="4" width="18" height="6" rx="1"/><rect x="3" y="14" width="18" height="6" rx="1"/><path d="M7 7h.01M7 17h.01"/></>,
  install: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 19h16"/></>,
  import: <><path d="M5 4h9l5 5v11H5z"/><path d="M14 4v5h5M12 11v6M9 14l3 3 3-3"/></>,
  market: <><path d="M4 8h16l-1 12H5zM7 8a5 5 0 0 1 10 0"/><path d="M9 12v1M15 12v1"/></>,
  addons: <path d="M8 3h8v5h5v8h-5v5H8v-5H3V8h5z"/>,
  diagnostics: <><path d="M12 3 4 6v5c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A8 8 0 0 0 15 6l-.3-2.6h-4L10.4 6A8 8 0 0 0 9 7.1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 1.4.8l.3 2.6h4l.3-2.6a8 8 0 0 0 1.4-.8l2.4 1 2-3.4-2-1.5c.1-.3.2-.7.2-1z"/></>,
  about: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  tasks: <><path d="M6 3h12v18H6z"/><path d="M9 8h6M9 12h6M9 16h4"/></>,
};

export default function WorkspaceIcon({ name }: { name: string }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}
