import pytest

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


def test_remove_server_deletes_only_direct_workspace_children(tmp_path):
    workspace = WorkspaceManager()
    previous_path = workspace._workspace_path
    previous_servers = workspace._servers
    workspace._workspace_path = str(tmp_path)
    workspace._servers = ServerCollection()
    try:
        server = workspace.create_server("Disposable", ServerType.VANILLA)
        server_path = tmp_path / server.uuid

        assert workspace.remove_server(server.uuid, delete_files=True)
        assert not server_path.exists()
        assert workspace.get_server_by_uuid(server.uuid) is None
    finally:
        workspace._workspace_path = previous_path
        workspace._servers = previous_servers


def test_remove_server_refuses_path_outside_workspace(tmp_path):
    workspace = WorkspaceManager()
    previous_path = workspace._workspace_path
    previous_servers = workspace._servers
    workspace._workspace_path = str(tmp_path / "workspace")
    workspace._servers = ServerCollection()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        server = workspace.create_server("Tampered", ServerType.VANILLA)
        server.path = str(outside)

        with pytest.raises(ValueError, match="工作区之外"):
            workspace.remove_server(server.uuid, delete_files=True)

        assert outside.exists()
        assert workspace.get_server_by_uuid(server.uuid) is server
    finally:
        workspace._workspace_path = previous_path
        workspace._servers = previous_servers
