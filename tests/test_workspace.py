from core.workspace import ServerCollection, ServerType, WorkspaceManager


def test_create_server_preserves_selected_java_version(tmp_path):
    workspace = WorkspaceManager()
    previous_path = workspace._workspace_path
    previous_servers = workspace._servers
    workspace._workspace_path = str(tmp_path)
    workspace._servers = ServerCollection()
    try:
        server = workspace.create_server(
            name="Fabric 1.20.1",
            server_type=ServerType.FABRIC,
            java_version="17",
        )

        assert server.java_version == "17"
        assert workspace.get_server_by_uuid(server.uuid) is server
        assert "java_version: '17'" in (tmp_path / server.uuid / ".hslmeta").read_text(
            encoding="utf-8"
        )
    finally:
        workspace._workspace_path = previous_path
        workspace._servers = previous_servers
