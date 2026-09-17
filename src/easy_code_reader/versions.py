"""Maven ComparableVersion ordering, including nested hyphen/digit components.

Python adaptation of Apache Maven 3.9.9 ComparableVersion (Apache-2.0).
See NOTICE and https://maven.apache.org/pom.html#version-order-specification.
"""

from functools import total_ordering
from itertools import zip_longest

_QUALIFIERS = ("alpha", "beta", "milestone", "rc", "snapshot", "", "sp")
_ALIASES = {"ga": "", "final": "", "release": "", "cr": "rc"}


def _qualifier(value, followed_by_digit=False):
    if followed_by_digit:
        value = {"a": "alpha", "b": "beta", "m": "milestone"}.get(value, value)
    return _ALIASES.get(value, value)


def _rank(value):
    return (_QUALIFIERS.index(value), "") if value in _QUALIFIERS else (len(_QUALIFIERS), value)


def _compare(left, right):
    if left is None:
        return 0 if right is None else -_compare(right, None)
    if right is None:
        if isinstance(left, list):
            return next((c for item in left if (c := _compare(item, None))), 0)
        if isinstance(left, int):
            return (left > 0) - (left < 0)
        return (_rank(left) > _rank("")) - (_rank(left) < _rank(""))
    if type(left) is not type(right):
        order = {str: 0, list: 1, int: 2}
        return (order[type(left)] > order[type(right)]) - (order[type(left)] < order[type(right)])
    if isinstance(left, list):
        return next((c for a, b in zip_longest(left, right) if (c := _compare(a, b))), 0)
    if isinstance(left, str):
        left, right = _rank(left), _rank(right)
    return (left > right) - (left < right)


def _parse(value):
    root = []
    current = root
    stack = [root]
    start = 0
    numeric = False
    value = value.lower()

    def nest():
        child = []
        current.append(child)
        stack.append(child)
        return child

    def item(text):
        return int(text) if numeric else _qualifier(text)

    for index, character in enumerate(value):
        if character in ".-":
            current.append(0 if index == start else item(value[start:index]))
            start = index + 1
            if character == "-":
                current = nest()
        elif character.isdigit():
            if not numeric and index > start:
                if current:
                    current = nest()
                current.append(_qualifier(value[start:index], True))
                start = index
                current = nest()
            numeric = True
        else:
            if numeric and index > start:
                current.append(int(value[start:index]))
                start = index
                current = nest()
            numeric = False
    if start < len(value):
        if not numeric and current:
            current = nest()
        current.append(item(value[start:]))
    for components in reversed(stack):
        for index in range(len(components) - 1, -1, -1):
            element = components[index]
            if element == 0 or element == "" or element == []:
                del components[index]
            elif not isinstance(element, list):
                break
    return root


@total_ordering
class MavenVersion:
    def __init__(self, value: str):
        self.components = _parse(value)

    def __eq__(self, other):
        if not isinstance(other, MavenVersion):
            return NotImplemented
        return _compare(self.components, other.components) == 0

    def __lt__(self, other):
        if not isinstance(other, MavenVersion):
            return NotImplemented
        return _compare(self.components, other.components) < 0
