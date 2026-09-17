"""Maven numeric, qualifier, alias and separator ordering regressions."""

import pytest

from easy_code_reader.versions import MavenVersion


@pytest.mark.parametrize("left,right", [
    ("1.9.0", "1.10.0"), ("1-alpha", "1-beta"), ("1-beta", "1-milestone"),
    ("1-milestone", "1-rc"), ("1-rc", "1-SNAPSHOT"), ("1-SNAPSHOT", "1"),
    ("1", "1-sp"), ("1-sp", "1-unknown"), ("1-1", "1.1"),
    ("1.0.RC2", "1.0-RC3"), ("1.0-RC3", "1.0.1"), ("1-alpha2", "1-alpha10"),
    ("1.0.0.X1", "1.0.0-X2"), ("1-xyz", "1.1"),
])
def test_maven_version_order(left, right):
    assert MavenVersion(left) < MavenVersion(right)


@pytest.mark.parametrize("left,right", [("1", "1.0.0"), ("1-ga", "1"), ("1-final", "1"),
                                       ("1-release", "1"), ("1-cr1", "1-rc1"),
                                       ("1-a1", "1-alpha-1"), ("1-b1", "1-beta-1"),
                                       ("1-m1", "1-milestone-1"), ("1-0", "1"),
                                       ("1.0.0-0.0.0", "1"), ("01.002", "1.2")])
def test_maven_version_equivalence(left, right):
    assert MavenVersion(left) == MavenVersion(right)
