import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _ensure_overrides():
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    yield
    app.dependency_overrides.pop(dependencies.require_admin, None)


# ---------------------------------------------------------------------------
# Helper: build the 11-tuple returned by _load_backup_service()
# ---------------------------------------------------------------------------


def _make_tuple(
    create_manual_rv=True,
    get_auto_rv=None,
    update_auto_side_effect=None,
    list_files_rv=None,
    get_info_rv=None,
    delete_file_rv=True,
    read_file_rv=b"backup-data",
    restore_rv=True,
):
    backup_system = MagicMock()
    start_bs = MagicMock()
    stop_bs = MagicMock()

    create_manual = MagicMock(return_value=create_manual_rv)

    if get_auto_rv is None:
        get_auto_rv = {"enabled": True, "interval_hours": 6, "max_backups": 28}
    get_auto = MagicMock(return_value=get_auto_rv)

    update_auto = MagicMock(side_effect=update_auto_side_effect)

    if list_files_rv is None:
        list_files_rv = []
    list_files = MagicMock(return_value=list_files_rv)

    if get_info_rv is None:
        get_info_rv = {"count": 0, "total_size_mb": 0.0, "files": []}
    get_info = MagicMock(return_value=get_info_rv)

    delete_file = MagicMock(return_value=delete_file_rv)

    read_file = MagicMock(return_value=read_file_rv)
    if isinstance(read_file_rv, type) and issubclass(read_file_rv, Exception):
        read_file = MagicMock(side_effect=read_file_rv)

    restore_db = MagicMock(return_value=restore_rv)

    return (
        backup_system,
        start_bs,
        stop_bs,
        create_manual,
        get_auto,
        update_auto,
        list_files,
        get_info,
        delete_file,
        read_file,
        restore_db,
    )


# ---------------------------------------------------------------------------
# _sanitize_backup_filename
# ---------------------------------------------------------------------------


class TestSanitizeBackupFilename:
    """Tests for the _sanitize_backup_filename helper directly."""

    def test_path_traversal_stripped_by_basename(self):
        """os.path.basename strips path components; remaining must match regex."""
        from api.routes.settings import _sanitize_backup_filename
        from fastapi import HTTPException

        result = _sanitize_backup_filename("../../../etc/passwd.dump")
        assert result == "passwd.dump"

    def test_non_dump_extension_raises(self):
        """File without .dump suffix raises HTTPException 400."""
        from api.routes.settings import _sanitize_backup_filename
        from fastapi import HTTPException
        import pytest

        with pytest.raises(HTTPException) as exc_info:
            _sanitize_backup_filename("evil.exe")
        assert exc_info.value.status_code == 400

    def test_valid_dump_name_passes(self):
        """A valid .dump filename passes sanitization unchanged."""
        from api.routes.settings import _sanitize_backup_filename

        result = _sanitize_backup_filename("backup_2024.dump")
        assert result == "backup_2024.dump"

    @patch("api.routes.settings._load_backup_service")
    def test_bad_characters_in_filename(self, mock_bs):
        """Filenames with spaces/special chars return 400."""
        mock_bs.return_value = _make_tuple()
        r = client.delete(
            "/api/settings/backup/bad file!.dump",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# get_backups – size formatting & mtime handling (lines 122-134)
# ---------------------------------------------------------------------------


class TestGetBackupsFormatting:
    """Covers size KB / MB branches and mtime datetime vs string."""

    @patch("api.routes.settings._load_backup_service")
    def test_size_kb_branch(self, mock_bs):
        """File size < 1 MB → formatted as KB."""
        files = [
            {
                "name": "small.dump",
                "size": 512 * 1024,  # 512 KB
                "mtime": "2024-01-01 10:00:00",
                "type": "auto",
            }
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert "KB" in data[0]["size"]

    @patch("api.routes.settings._load_backup_service")
    def test_size_mb_branch(self, mock_bs):
        """File size >= 1 MB → formatted as MB."""
        files = [
            {
                "name": "large.dump",
                "size": 5 * 1024 * 1024,  # 5 MB
                "mtime": "2024-01-01 10:00:00",
                "type": "manual",
            }
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "MB" in data[0]["size"]

    @patch("api.routes.settings._load_backup_service")
    def test_mtime_as_datetime_object(self, mock_bs):
        """mtime that is a datetime object is formatted via strftime."""
        dt = datetime(2024, 6, 15, 12, 30, 45)
        files = [
            {
                "name": "snap.dump",
                "size": 1024,
                "mtime": dt,
                "type": "auto",
            }
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data[0]["time"] == "2024-06-15 12:30:45"

    @patch("api.routes.settings._load_backup_service")
    def test_mtime_as_string_passthrough(self, mock_bs):
        """mtime that is a plain string is converted via str()."""
        files = [
            {
                "name": "snap2.dump",
                "size": 1024,
                "mtime": "2024-01-02 09:00:00",
                "type": "auto",
            }
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data[0]["time"] == "2024-01-02 09:00:00"

    @patch("api.routes.settings._load_backup_service")
    def test_multiple_files_sorted_descending(self, mock_bs):
        """Backups are returned sorted by time descending."""
        files = [
            {
                "name": "old.dump",
                "size": 1024,
                "mtime": "2024-01-01 00:00:00",
                "type": "auto",
            },
            {
                "name": "new.dump",
                "size": 1024,
                "mtime": "2024-06-01 00:00:00",
                "type": "auto",
            },
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data[0]["name"] == "new.dump"
        assert data[1]["name"] == "old.dump"


# ---------------------------------------------------------------------------
# create_backup – failure paths (lines 157-164)
# ---------------------------------------------------------------------------


class TestCreateBackupFailure:
    """Covers success=False and generic Exception in create_backup."""

    @patch("api.routes.settings._load_backup_service")
    def test_create_backup_returns_false(self, mock_bs):
        """When create_manual_backup() returns False → 500."""
        mock_bs.return_value = _make_tuple(create_manual_rv=False)
        r = client.post(
            "/api/settings/backup",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "备份失败" in r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_create_backup_raises_exception(self, mock_bs):
        """When create_manual_backup() raises → 500 with detail."""
        tup = list(_make_tuple())
        tup[3] = MagicMock(side_effect=RuntimeError("disk full"))
        mock_bs.return_value = tuple(tup)
        r = client.post(
            "/api/settings/backup",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "备份失败，请联系管理员" == r.json()["detail"]


# ---------------------------------------------------------------------------
# get_backup_settings – disabled branch (lines 176-186, 183-184)
# ---------------------------------------------------------------------------


class TestGetBackupSettingsDisabled:
    """Covers enabled=False path → next_backup is None."""

    @patch("api.routes.settings._load_backup_service")
    def test_disabled_backup_settings(self, mock_bs):
        """When enabled=False, next_backup must be None."""
        settings = {"enabled": False, "interval_hours": 6, "max_backups": 10}
        mock_bs.return_value = _make_tuple(get_auto_rv=settings)
        r = client.get(
            "/api/settings/backup/settings",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is False
        assert data["next_backup"] is None

    @patch("api.routes.settings._load_backup_service")
    def test_enabled_backup_settings_has_next_backup(self, mock_bs):
        """When enabled=True, next_backup must be a non-empty string."""
        settings = {"enabled": True, "interval_hours": 12, "max_backups": 14}
        mock_bs.return_value = _make_tuple(get_auto_rv=settings)
        r = client.get(
            "/api/settings/backup/settings",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["next_backup"] is not None
        assert len(data["next_backup"]) > 0


# ---------------------------------------------------------------------------
# update_backup_settings – empty kwargs (lines 209, 213, 216) & exception (221-222)
# ---------------------------------------------------------------------------


class TestUpdateBackupSettings:
    """Covers empty-kwargs early return and exception path."""

    @patch("api.routes.settings._load_backup_service")
    def test_empty_kwargs_returns_no_update_message(self, mock_bs):
        """POST with no fields set → 'no update needed' message."""
        mock_bs.return_value = _make_tuple()
        r = client.put(
            "/api/settings/backup/settings",
            json={},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert "没有需要更新" in r.json()["message"]

    @patch("api.routes.settings._load_backup_service")
    def test_update_only_enabled(self, mock_bs):
        """Only 'enabled' provided → kwargs has one key, no error."""
        mock_bs.return_value = _make_tuple()
        r = client.put(
            "/api/settings/backup/settings",
            json={"enabled": False},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert "已更新" in r.json()["message"]

    @patch("api.routes.settings._load_backup_service")
    def test_update_only_interval_hours(self, mock_bs):
        """Only 'interval_hours' provided → single kwarg path."""
        mock_bs.return_value = _make_tuple()
        r = client.put(
            "/api/settings/backup/settings",
            json={"interval_hours": 24},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_update_only_max_backups(self, mock_bs):
        """Only 'max_backups' provided → single kwarg path."""
        mock_bs.return_value = _make_tuple()
        r = client.put(
            "/api/settings/backup/settings",
            json={"max_backups": 7},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_update_raises_exception(self, mock_bs):
        """When update_auto_backup_settings() raises → 500."""
        mock_bs.return_value = _make_tuple(
            update_auto_side_effect=RuntimeError("db error")
        )
        r = client.put(
            "/api/settings/backup/settings",
            json={"interval_hours": 3},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "更新失败，请联系管理员" == r.json()["detail"]


# ---------------------------------------------------------------------------
# get_backup_stats – file list formatting (lines 235-247)
# ---------------------------------------------------------------------------


class TestGetBackupStatsWithFiles:
    """Covers size KB/MB and mtime branches inside get_backup_stats."""

    @patch("api.routes.settings._load_backup_service")
    def test_stats_file_size_kb(self, mock_bs):
        """Files < 1 MB rendered as KB in stats."""
        info = {
            "count": 1,
            "total_size_mb": 0.5,
            "files": [
                {
                    "name": "small.dump",
                    "size": 200 * 1024,  # 200 KB
                    "mtime": "2024-03-01 08:00:00",
                    "type": "auto",
                }
            ],
        }
        mock_bs.return_value = _make_tuple(get_info_rv=info)
        r = client.get(
            "/api/settings/backup/stats",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["files"]) == 1
        assert "KB" in data["files"][0]["size"]

    @patch("api.routes.settings._load_backup_service")
    def test_stats_file_size_mb(self, mock_bs):
        """Files >= 1 MB rendered as MB in stats."""
        info = {
            "count": 1,
            "total_size_mb": 3.0,
            "files": [
                {
                    "name": "big.dump",
                    "size": 3 * 1024 * 1024,  # 3 MB
                    "mtime": "2024-03-01 08:00:00",
                    "type": "manual",
                }
            ],
        }
        mock_bs.return_value = _make_tuple(get_info_rv=info)
        r = client.get(
            "/api/settings/backup/stats",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "MB" in data["files"][0]["size"]

    @patch("api.routes.settings._load_backup_service")
    def test_stats_mtime_datetime_object(self, mock_bs):
        """mtime datetime object is formatted correctly in stats."""
        dt = datetime(2025, 1, 20, 15, 0, 0)
        info = {
            "count": 1,
            "total_size_mb": 0.1,
            "files": [
                {
                    "name": "dt.dump",
                    "size": 1024,
                    "mtime": dt,
                    "type": "auto",
                }
            ],
        }
        mock_bs.return_value = _make_tuple(get_info_rv=info)
        r = client.get(
            "/api/settings/backup/stats",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["files"][0]["time"] == "2025-01-20 15:00:00"

    @patch("api.routes.settings._load_backup_service")
    def test_stats_mtime_string(self, mock_bs):
        """mtime string is preserved via str() in stats."""
        info = {
            "count": 1,
            "total_size_mb": 0.1,
            "files": [
                {
                    "name": "str.dump",
                    "size": 1024,
                    "mtime": "2025-02-10 11:22:33",
                    "type": "auto",
                }
            ],
        }
        mock_bs.return_value = _make_tuple(get_info_rv=info)
        r = client.get(
            "/api/settings/backup/stats",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["files"][0]["time"] == "2025-02-10 11:22:33"


# ---------------------------------------------------------------------------
# download_backup – FileNotFoundError & generic Exception (lines 271, 275-278)
# ---------------------------------------------------------------------------


class TestDownloadBackupErrors:
    """Covers FileNotFoundError and generic Exception in download_backup."""

    @patch("api.routes.settings._load_backup_service")
    def test_download_file_not_found(self, mock_bs):
        """FileNotFoundError from read_backup_file → 404."""
        tup = list(_make_tuple())
        tup[9] = MagicMock(side_effect=FileNotFoundError("no such file"))
        mock_bs.return_value = tuple(tup)
        r = client.get(
            "/api/settings/backup/myfile.dump/download",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 404
        assert "不存在" in r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_download_generic_exception(self, mock_bs):
        """Generic Exception from read_backup_file → 500."""
        tup = list(_make_tuple())
        tup[9] = MagicMock(side_effect=OSError("permission denied"))
        mock_bs.return_value = tuple(tup)
        r = client.get(
            "/api/settings/backup/myfile.dump/download",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "读取文件失败，请联系管理员" == r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_download_non_dump_extension_rejected(self, mock_bs):
        """Non-.dump filename is rejected with 400."""
        mock_bs.return_value = _make_tuple()
        r = client.get(
            "/api/settings/backup/backup.tar/download",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# delete_backup – failure paths (lines 297, 304-311)
# ---------------------------------------------------------------------------


class TestDeleteBackupFailure:
    """Covers success=False and generic Exception in delete_backup."""

    @patch("api.routes.settings._load_backup_service")
    def test_delete_returns_false(self, mock_bs):
        """When delete_backup_file() returns False → 404."""
        mock_bs.return_value = _make_tuple(delete_file_rv=False)
        r = client.delete(
            "/api/settings/backup/myfile.dump",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 404
        assert "不存在" in r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_delete_raises_exception(self, mock_bs):
        """When delete_backup_file() raises → 500."""
        tup = list(_make_tuple())
        tup[8] = MagicMock(side_effect=RuntimeError("io error"))
        mock_bs.return_value = tuple(tup)
        r = client.delete(
            "/api/settings/backup/myfile.dump",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "删除失败，请联系管理员" == r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_delete_non_dump_extension(self, mock_bs):
        """Non-.dump filename sanitize returns 400 before delete."""
        mock_bs.return_value = _make_tuple()
        r = client.delete(
            "/api/settings/backup/file.txt",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# restore_backup – bad extension & failure paths (lines 328, 338-345)
# ---------------------------------------------------------------------------


class TestRestoreBackupFailure:
    """Covers bad extension, success=False, generic Exception."""

    @patch("api.routes.settings._load_backup_service")
    def test_restore_non_dump_extension(self, mock_bs):
        """Non-.dump file is rejected with 400 (fails regex validation)."""
        mock_bs.return_value = _make_tuple()
        r = client.post(
            "/api/settings/backup/backup.sql/restore",
            json={"create_snapshot": True},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400

    @patch("api.routes.settings._load_backup_service")
    def test_restore_returns_false(self, mock_bs):
        """When restore_database() returns False → 500."""
        tup = list(_make_tuple(restore_rv=False))
        tup[10] = MagicMock(return_value=False)
        mock_bs.return_value = tuple(tup)
        r = client.post(
            "/api/settings/backup/myfile.dump/restore",
            json={"create_snapshot": True},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "恢复失败" in r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_restore_raises_exception(self, mock_bs):
        """When restore_database() raises → 500 with detail."""
        tup = list(_make_tuple())
        tup[10] = MagicMock(side_effect=RuntimeError("restore crashed"))
        mock_bs.return_value = tuple(tup)
        r = client.post(
            "/api/settings/backup/myfile.dump/restore",
            json={"create_snapshot": False},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 500
        assert "恢复失败，请联系管理员" == r.json()["detail"]

    @patch("api.routes.settings._load_backup_service")
    def test_restore_success_with_snapshot(self, mock_bs):
        """Successful restore with create_snapshot=True."""
        mock_bs.return_value = _make_tuple(restore_rv=True)
        r = client.post(
            "/api/settings/backup/good.dump/restore",
            json={"create_snapshot": True},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert "good.dump" in r.json()["message"]


# ---------------------------------------------------------------------------
# Exact size boundary tests
# ---------------------------------------------------------------------------


class TestSizeBoundary:
    """Exact 1 MB boundary: size == 1024*1024 should render as MB."""

    @patch("api.routes.settings._load_backup_service")
    def test_exact_1mb_renders_as_mb(self, mock_bs):
        """size == 1024*1024 is NOT < 1024*1024 so renders as MB."""
        files = [
            {
                "name": "exact.dump",
                "size": 1024 * 1024,
                "mtime": "2024-01-01 00:00:00",
                "type": "auto",
            }
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "MB" in data[0]["size"]

    @patch("api.routes.settings._load_backup_service")
    def test_just_under_1mb_renders_as_kb(self, mock_bs):
        """size == 1024*1024 - 1 renders as KB."""
        files = [
            {
                "name": "under.dump",
                "size": 1024 * 1024 - 1,
                "mtime": "2024-01-01 00:00:00",
                "type": "auto",
            }
        ]
        mock_bs.return_value = _make_tuple(list_files_rv=files)
        r = client.get(
            "/api/settings/backups",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "KB" in data[0]["size"]


class TestSuccessPaths:
    @patch("api.routes.settings._load_backup_service")
    def test_create_backup_success(self, mock_bs):
        mock_bs.return_value = _make_tuple(create_manual_rv=True)
        r = client.post(
            "/api/settings/backup",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert "备份成功" in r.json()["message"]

    @patch("api.routes.settings._load_backup_service")
    def test_download_backup_success(self, mock_bs):
        mock_bs.return_value = _make_tuple(read_file_rv=b"binary_data")
        r = client.get(
            "/api/settings/backup/test.dump/download",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert r.content == b"binary_data"

    @patch("api.routes.settings._load_backup_service")
    def test_delete_backup_success(self, mock_bs):
        mock_bs.return_value = _make_tuple(delete_file_rv=True)
        r = client.delete(
            "/api/settings/backup/test.dump",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert "test.dump" in r.json()["message"]
