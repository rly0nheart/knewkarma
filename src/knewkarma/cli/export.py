"""
Export.

Writes models to json or csv with the standard library. It flattens each model to its named
fields and drops the raw dict and nested replies.
"""

import csv
import json
import typing as t
from pathlib import Path

from ..core.models import RedditObject


def _row(item: t.Union[RedditObject, str]) -> t.Dict[str, t.Any]:
    """
    Turn a model into a dict of its fields.

    :param item: A model, or a plain string such as a wiki page name.
    :type item: t.Union[RedditObject, str]
    :returns: Every field the model holds.
    :rtype: t.Dict[str, t.Any]
    """

    if isinstance(item, RedditObject):
        return dict(item.data)
    return {"value": item}


def to_json(items: t.Sequence[t.Union[RedditObject, str]], path: str) -> None:
    """
    Write models to a json file.

    :param items: The models to write.
    :type items: t.Sequence[t.Union[RedditObject, str]]
    :param path: Output file path.
    :type path: str
    """

    rows = [_row(item) for item in items]
    Path(path).write_text(json.dumps(rows, indent=2, ensure_ascii=False))


def to_csv(items: t.Sequence[t.Union[RedditObject, str]], path: str) -> None:
    """
    Write models to a csv file.

    The columns are the union of every model's fields, since items can carry different keys.

    :param items: The models to write.
    :type items: t.Sequence[t.Union[RedditObject, str]]
    :param path: Output file path.
    :type path: str
    """

    rows = [_row(item) for item in items]
    if not rows:
        return

    fieldnames: t.List[str] = []
    seen: t.Set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write(items: t.Sequence[t.Union[RedditObject, str]], base_path: str, formats: t.Sequence[str]) -> t.List[str]:
    """
    Write models in the named formats.

    :param items: The models to write.
    :type items: t.Sequence[t.Union[RedditObject, str]]
    :param base_path: Output path without an extension.
    :type base_path: str
    :param formats: Formats to write, from ``json`` and ``csv``.
    :type formats: t.Sequence[str]
    :returns: The paths written.
    :rtype: t.List[str]
    """

    written: t.List[str] = []
    for fmt in formats:
        path = f"{base_path}.{fmt}"
        if fmt == "json":
            to_json(items, path)
        elif fmt == "csv":
            to_csv(items, path)
        else:
            continue
        written.append(path)
    return written
