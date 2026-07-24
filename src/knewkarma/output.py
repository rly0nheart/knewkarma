"""
Result output.

Pretty-prints a single model, or pages through a list of models, using ``rich``.
"""

import typing as t

from rich.console import Console
from rich.pretty import Pretty

from .core.models import RedditObject

console = Console()


def show(
        items: t.Union[RedditObject, t.Sequence[RedditObject], t.Sequence[str], None],
        title: t.Optional[str] = None,
) -> None:
    """
    Show a result.

    A list of models pages through the pager, so the user scrolls through bulk results. A single
    model pretty-prints its fields, with no pager. An empty result prints a short note.

    :param items: A single model, a list of models, a list of wiki page names, or None.
    :type items: t.Union[RedditObject, t.Sequence[RedditObject], t.Sequence[str], None]
    :param title: A heading for the table.
    :type title: t.Optional[str]
    """

    if not isinstance(items, (list, tuple)):
        if items is None:
            console.print("No results.")
        else:
            console.print(Pretty(items))
        return

    rows = list(items)
    if not rows:
        console.print("No results.")
        return

    with console.pager(styles=True):
        if title:
            console.print(title)
            console.print()
        for index, row in enumerate(rows):
            if index:
                console.print()
            console.print(Pretty(row))
