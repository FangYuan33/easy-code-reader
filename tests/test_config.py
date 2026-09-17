"""Configuration is resolved per instance and works without writable packages."""

import subprocess
import sys

import pytest

from easy_code_reader.config import Config
from easy_code_reader.errors import ReaderError


def test_settings_priority_and_variables(tmp_path):
    home = tmp_path / "home"
    settings = home / ".m2/settings.xml"
    settings.parent.mkdir(parents=True)
    settings.write_text('<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"><localRepository>${user.home}/${env.REPO}</localRepository></settings>')
    config = Config.load(env={"REPO": "repo"}, home=home)
    assert config.maven_repo == home / "repo"
    assert Config.load(env={"MAVEN_REPO": str(tmp_path / "explicit")}, home=home).maven_repo == tmp_path / "explicit"
    assert Config.load(str(tmp_path / "cli"), env={"MAVEN_REPO": "env"}, home=home).maven_repo == tmp_path / "cli"


def test_maven_install_is_not_repository(tmp_path):
    home = tmp_path / "home"
    install = tmp_path / "maven"
    assert Config.load(env={"MAVEN_HOME": str(install)}, home=home).maven_repo == home / ".m2/repository"
    (install / "conf").mkdir(parents=True)
    (install / "conf/settings.xml").write_text(f'<settings><localRepository>{tmp_path}/global</localRepository></settings>')
    assert Config.load(env={"M2_HOME": str(install)}, home=home).maven_repo == tmp_path / "global"


def test_unresolved_settings_error_can_be_overridden(tmp_path):
    settings = tmp_path / ".m2/settings.xml"
    settings.parent.mkdir()
    settings.write_text('<settings><localRepository>${env.UNKNOWN}</localRepository></settings>')
    with pytest.raises(ReaderError, match="无法解析"):
        Config.load(env={}, home=tmp_path)
    assert Config.load(str(tmp_path / "explicit"), env={}, home=tmp_path).maven_repo == tmp_path / "explicit"


def test_server_configs_do_not_leak(tmp_path):
    from easy_code_reader.server import EasyCodeReaderServer
    first = EasyCodeReaderServer(str(tmp_path / "one"))
    second = EasyCodeReaderServer(str(tmp_path / "two"))
    assert first.maven_home != second.maven_home
    assert Config.load(env={}, home=tmp_path).maven_repo == tmp_path / ".m2/repository"


@pytest.mark.parametrize("kwargs", [{"decompile_timeout": 0}, {"decompile_timeout": float("nan")}])
def test_invalid_execution_settings(tmp_path, kwargs):
    with pytest.raises(ReaderError):
        Config.load(str(tmp_path), **kwargs)


def test_import_does_not_create_file_handler():
    command = '''from unittest.mock import patch
with patch("logging.FileHandler", side_effect=PermissionError("read-only")):
    import easy_code_reader.server
'''
    result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
