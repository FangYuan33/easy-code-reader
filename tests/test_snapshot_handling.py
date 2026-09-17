"""The same resolver is used for search, binaries and matching sources."""

import pytest

from easy_code_reader.errors import ReaderError
from easy_code_reader.repository import MavenRepository


@pytest.mark.parametrize("version", ["1-SNAPSHOT", "1.0-SNAPSHOT", "1.0.0-RC1-SNAPSHOT"])
def test_normalized_binary_with_numeric_timestamp_cache_name(tmp_path, jar_factory, version):
    repo = MavenRepository(tmp_path)
    directory = tmp_path / "com/example/demo" / version
    base = version[:-len("SNAPSHOT")]
    ordinary = jar_factory(directory / f"demo-{version}.jar")
    old = jar_factory(directory / f"demo-{base}20260915.120000-9.jar")
    latest = jar_factory(directory / f"demo-{base}20260915.120000-10.jar")
    source = jar_factory(directory / f"demo-{base}20260915.120000-10-sources.jar")
    jar_factory(directory / f"demo-{base}20260915.120000-11-tests.jar")
    resolved = repo.resolve("com.example", "demo", version)
    assert resolved.binary == ordinary
    assert resolved.sources == source
    assert resolved.binary not in (latest, old)
    assert resolved.cache_jar_name == latest.name
    assert resolved.selection == "normalized_snapshot"
    assert resolved.resolved_version.endswith("-10")
    assert repo.search("demo")["matches"][0]["matched_versions"] == [version]


def test_does_not_mix_snapshot_builds(tmp_path, jar_factory):
    directory = tmp_path / "com/example/demo/1.0-SNAPSHOT"
    jar_factory(directory / "demo-1.0-20260915.120000-2.jar")
    jar_factory(directory / "demo-1.0-20260915.120000-1-sources.jar")
    jar_factory(directory / "demo-1.0-SNAPSHOT-sources.jar")
    resolved = MavenRepository(tmp_path).resolve("com.example", "demo", "1.0-SNAPSHOT")
    assert resolved.sources is None
    assert resolved.resolved_version == "1.0-20260915.120000-2"


def test_plain_snapshot_fallback(tmp_path, jar_factory):
    binary = jar_factory(tmp_path / "com/example/demo/1.0-SNAPSHOT/demo-1.0-SNAPSHOT.jar")
    resolved = MavenRepository(tmp_path).resolve("com.example", "demo", "1.0-SNAPSHOT")
    assert resolved.binary == binary
    assert resolved.selection == "snapshot"


def test_source_only_timestamp_is_searchable(tmp_path, jar_factory):
    path = jar_factory(tmp_path / "com/example/demo/1.0-SNAPSHOT/demo-1.0-20260915.120000-2-sources.jar")
    repo = MavenRepository(tmp_path)
    resolved = repo.resolve("com.example", "demo", "1.0-SNAPSHOT")
    assert resolved.binary is None
    assert resolved.sources == path
    assert resolved.selection == "sources_only"
    assert repo.search("demo")["total_matches"] == 1


def test_metadata_does_not_override_local_timestamp(tmp_path, jar_factory):
    binary = jar_factory(tmp_path / "com/example/demo/1.0-SNAPSHOT/demo-1.0-20260915.120000-2.jar")
    (binary.parent / "maven-metadata-local.xml").write_text('''<metadata><versioning><snapshotVersions>
    <snapshotVersion><extension>jar</extension><value>1.0-20260914.120000-1</value></snapshotVersion>
    </snapshotVersions></versioning></metadata>''')
    resolved = MavenRepository(tmp_path).resolve("com.example", "demo", "1.0-SNAPSHOT")
    assert resolved.binary == binary
    assert resolved.warnings


def test_classifier_cannot_replace_main_jar(tmp_path, jar_factory):
    jar_factory(tmp_path / "com/example/demo/1.0/demo-1.0-tests.jar")
    with pytest.raises(ReaderError, match="未找到 JAR 文件"):
        MavenRepository(tmp_path).resolve("com.example", "demo", "1.0")


@pytest.mark.parametrize("field,value", [("group_id", "/tmp"), ("group_id", "com..example"),
                                       ("artifact_id", "../demo"), ("artifact_id", "*"),
                                       ("version", "1.0/else"), ("version", "C:\\temp")])
def test_coordinates_reject_paths(tmp_path, field, value):
    args = dict(group_id="com.example", artifact_id="demo", version="1.0")
    args[field] = value
    with pytest.raises(ReaderError) as error:
        MavenRepository(tmp_path).resolve(**args)
    assert error.value.code == "INVALID_ARGUMENT"


def test_symlink_outside_repository(tmp_path, jar_factory):
    outside = jar_factory(tmp_path / "outside/demo-1.0.jar")
    directory = tmp_path / "repo/com/example/demo/1.0"
    directory.mkdir(parents=True)
    try:
        (directory / outside.name).symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ReaderError, match="超出"):
        MavenRepository(tmp_path / "repo").resolve("com.example", "demo", "1.0")


def test_normalized_sources_preferred(tmp_path, jar_factory):
    directory = tmp_path / "org/example/demo/1.0-SNAPSHOT"
    jar_factory(directory / "demo-1.0-20260915.120000-2.jar")
    jar_factory(directory / "demo-1.0-20260915.120000-2-sources.jar")
    ordinary = jar_factory(directory / "demo-1.0-SNAPSHOT.jar")
    sources = jar_factory(directory / "demo-1.0-SNAPSHOT-sources.jar")
    artifact = MavenRepository(tmp_path).resolve("org.example", "demo", "1.0-SNAPSHOT")
    assert artifact.binary == ordinary
    assert artifact.sources == sources
    assert artifact.cache_jar_name == "demo-1.0-20260915.120000-2.jar"


def test_timestamp_only_binary_fallback(tmp_path, jar_factory):
    directory = tmp_path / "org/example/demo/1.0-SNAPSHOT"
    timestamp = jar_factory(directory / "demo-1.0-20260915.120000-2.jar")
    sources = jar_factory(directory / "demo-1.0-20260915.120000-2-sources.jar")
    artifact = MavenRepository(tmp_path).resolve("org.example", "demo", "1.0-SNAPSHOT")
    assert artifact.binary == timestamp
    assert artifact.sources == sources
    assert artifact.cache_jar_name == timestamp.name


def test_normalized_source_only_preferred(tmp_path, jar_factory):
    directory = tmp_path / "org/example/demo/1.0-SNAPSHOT"
    jar_factory(directory / "demo-1.0-20260915.120000-2-sources.jar")
    sources = jar_factory(directory / "demo-1.0-SNAPSHOT-sources.jar")
    artifact = MavenRepository(tmp_path).resolve("org.example", "demo", "1.0-SNAPSHOT")
    assert artifact.sources == sources
    assert artifact.binary is None
