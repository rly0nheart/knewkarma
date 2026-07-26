"""
Data models for Reddit's JSON API.

Reddit wraps every object as a thing: a dict with a ``kind`` tag and a ``data`` body. Each model
here wraps one ``data`` body whole and exposes every field it holds as an attribute. So a post
carries all 100-plus fields the API sends, not a chosen few.

Kinds: ``t1`` comment, ``t2`` user, ``t3`` post, ``t5`` subreddit, ``t6`` trophy, ``more`` (a
stub naming comment ids to fetch), and ``Listing`` (a page with paging cursors).

Every model, and the :class:`Things` list the API hands back, writes itself out:

.. code-block:: python

    from knewkarma import Reddit

    with Reddit() as client:
        posts = client.subreddit("askscience").posts(limit=10)

        posts.to_csv("posts.csv")           # one row per post
        posts[0].to_json("post.json")       # one object
        posts[0].to_dict()                  # the fields as a plain dict
"""

import csv
import json
import typing as t
from dataclasses import dataclass, field
from pathlib import Path


class RedditObject:
    """
    A namespace over a Reddit thing's ``data`` dict.

    It lazily converts dictionaries to attribute namespaces, so ``post.preview.images[0]`` and
    ``post.preview.images[0].source.url`` work. A missing field raises ``AttributeError``. The
    original dict stays available as ``data`` and ``raw``.
    """

    def __init__(self, data: t.Optional[t.Dict[str, t.Any]] = None):
        """
        Wrap a data dict.

        :param data: The thing's ``data`` body.
        :type data: t.Optional[t.Dict[str, t.Any]]
        """

        object.__setattr__(self, "data", data or {})

    @classmethod
    def _convert(cls, value: t.Any) -> t.Any:
        """
        Convert nested Reddit values to attribute namespaces.

        :param value: A Reddit response value.
        :type value: t.Any
        :returns: The converted value.
        :rtype: t.Any
        """

        if isinstance(value, dict):
            return RedditObject(value)
        if isinstance(value, list):
            return [cls._convert(item) for item in value]
        return value

    def __getattr__(self, name: str) -> t.Any:
        try:
            value = self.data[name]
        except KeyError:
            raise AttributeError(name) from None

        converted = self._convert(value)
        object.__setattr__(self, name, converted)
        return converted

    @classmethod
    def from_data(cls, data: t.Dict[str, t.Any]) -> t.Self:
        """
        Wrap a thing's ``data`` body.

        :param data: The thing's ``data`` dict.
        :type data: t.Dict[str, t.Any]
        :returns: The wrapped object, of the class it was called on.
        :rtype: t.Self
        """

        return cls(data)

    def __rich_repr__(self) -> t.Iterator[t.Tuple[str, t.Any]]:
        for key, value in self.data.items():
            yield key, getattr(self, key)

    @property
    def raw(self) -> t.Dict[str, t.Any]:
        """
        Return the whole data dict.

        :returns: Every field the API sent.
        :rtype: t.Dict[str, t.Any]
        """

        return self.data

    @staticmethod
    def __write(path: str, text: str) -> str:
        """
        Write text to a file, making the parent directory when it is missing.

        :param path: Output file path.
        :type path: str
        :param text: What to write.
        :type text: str
        :returns: The path written.
        :rtype: str
        """

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return str(target)

    def to_dict(self) -> t.Dict[str, t.Any]:
        """
        Return the thing's fields as a plain dict.

        The dict is a shallow copy, so changing it leaves the model alone.

        :returns: Every field the API sent.
        :rtype: t.Dict[str, t.Any]
        """

        return dict(self.data)

    def to_json(self, path: str, indent: int = 2) -> str:
        """
        Write the thing to a json file as one object.

        .. code-block:: python

            from knewkarma import Reddit

            with Reddit() as client:
                client.user("spez").posts(limit=5)[0].to_json("post.json")

        :param path: Output file path. Missing parent directories are made.
        :type path: str
        :param indent: Spaces to indent by. ``0`` writes it on one line.
        :type indent: int
        :returns: The path written.
        :rtype: str
        """

        return self.__write(
            path, json.dumps(self.to_dict(), indent=indent or None, ensure_ascii=False)
        )

    def to_csv(self, path: str) -> str:
        """
        Write the thing to a csv file as one row.

        .. code-block:: python

            from knewkarma import Reddit

            with Reddit() as client:
                client.user("spez").posts(limit=5)[0].to_csv("post.csv")

        :param path: Output file path. Missing parent directories are made.
        :type path: str
        :returns: The path written.
        :rtype: str
        """

        return Things([self]).to_csv(path)


class Post(RedditObject):
    """A Reddit post, kind ``t3``."""


class Comment(RedditObject):
    """A Reddit comment, kind ``t1``."""


class Subreddit(RedditObject):
    """A subreddit, kind ``t5``."""


class User(RedditObject):
    """A user account, kind ``t2``."""

    @classmethod
    def from_profile_subreddit(cls, data: t.Dict[str, t.Any]) -> "User":
        """
        Wrap a profile subreddit as a user.

        Reddit's ``/users/new`` and ``/users/popular`` feeds return each user as a ``t5`` profile
        subreddit whose ``display_name`` is ``u_<name>``. This wraps that dict and adds a ``name``
        field. Call :meth:`UserEndpoint.about` for karma and the rest.

        :param data: The ``data`` dict of a ``t5`` profile subreddit.
        :type data: t.Dict[str, t.Any]
        :returns: The user.
        :rtype: User
        """

        display_name = data.get("display_name", "")
        name = display_name[2:] if display_name.startswith("u_") else display_name
        return cls({"name": name, **data})


class Trophy(RedditObject):
    """A user trophy, kind ``t6``."""


class MultiReddit(RedditObject):
    """A user's public multireddit: a named set of subreddits."""


class More(RedditObject):
    """A ``more`` stub naming comment ids to fetch in follow-up calls."""


# A parsed thing is any one of the models above.
Thing = t.Union[Post, Comment, More, Subreddit, User, Trophy]


class Things[T](list[T]):
    """
    The list of things a read hands back. It writes itself out the way one thing does.

    It is a plain list, so it indexes, slices and iterates as always. It just also carries
    :meth:`to_dict`, :meth:`to_json` and :meth:`to_csv`:

    .. code-block:: python

        from knewkarma import Reddit

        with Reddit() as client:
            posts = client.subreddit("python").posts(limit=50)
            posts.to_csv("posts.csv")
            posts[0].to_json("first.json")
    """

    @staticmethod
    def __as_row(item: t.Any) -> t.Dict[str, t.Any]:
        """
        Turn one item into a flat row.

        :param item: A model, or a plain value such as a wiki page name.
        :type item: t.Any
        :returns: The item's fields, or ``{"value": item}`` for a plain value.
        :rtype: t.Dict[str, t.Any]
        """

        if isinstance(item, RedditObject):
            return item.to_dict()
        return {"value": item}

    @staticmethod
    def __as_cell(value: t.Any) -> t.Any:
        """
        Make one value fit in a csv cell.

        Reddit nests dicts and lists inside a thing's fields. A csv cell holds text, so those go in
        as json rather than as a Python repr, which keeps them readable by whatever opens the file
        next.

        :param value: A field value.
        :type value: t.Any
        :returns: The value, or its json form when it nests.
        :rtype: t.Any
        """

        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value

    @staticmethod
    def __prepare(path: str) -> Path:
        """
        Make the parent directory of an output path when it is missing.

        :param path: Output file path.
        :type path: str
        :returns: The path, ready to write to.
        :rtype: Path
        """

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def to_dict(self) -> t.List[t.Dict[str, t.Any]]:
        """
        Return the things as a list of plain dicts.

        :returns: One dict of fields per thing.
        :rtype: t.List[t.Dict[str, t.Any]]
        """

        return [self.__as_row(item) for item in self]

    def to_json(self, path: str, indent: int = 2) -> str:
        """
        Write the things to a json file as one array.

        :param path: Output file path. Missing parent directories are made.
        :type path: str
        :param indent: Spaces to indent by. ``0`` writes it on one line.
        :type indent: int
        :returns: The path written.
        :rtype: str
        """

        target = self.__prepare(path)
        target.write_text(
            json.dumps(self.to_dict(), indent=indent or None, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(target)

    def to_csv(self, path: str) -> str:
        """
        Write the things to a csv file, one row each.

        The columns are the union of every row's keys, in the order they were first seen, since
        things of the same kind can still carry different fields.

        :param path: Output file path. Missing parent directories are made.
        :type path: str
        :returns: The path written.
        :rtype: str
        """

        target = self.__prepare(path)
        rows = self.to_dict()

        fieldnames: t.List[str] = []
        seen: t.Set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)

        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: self.__as_cell(value) for key, value in row.items()})
        return str(target)


_BUILDERS: t.Dict[str, t.Callable[[t.Dict[str, t.Any]], Thing]] = {
    "t1": Comment.from_data,
    "t2": User.from_data,
    "t3": Post.from_data,
    "t5": Subreddit.from_data,
    "t6": Trophy.from_data,
    "more": More.from_data,
}


def parse_thing(thing: t.Dict[str, t.Any]) -> t.Optional[Thing]:
    """
    Parse one ``{kind, data}`` thing into its model.

    :param thing: A thing wrapper.
    :type thing: t.Dict[str, t.Any]
    :returns: The matching model, or None when the kind is unknown.
    :rtype: t.Optional[Thing]
    """

    builder = _BUILDERS.get(thing.get("kind", ""))
    if builder is None:
        return None
    return builder(thing.get("data", {}))


@dataclass
class Listing:
    """A page of things with Reddit's paging cursors."""

    after: t.Optional[str]
    before: t.Optional[str]
    dist: t.Optional[int]
    children: t.List[Thing] = field(default_factory=list)

    @classmethod
    def from_response(cls, payload: t.Dict[str, t.Any]) -> "Listing":
        """
        Parse a listing response into a page of models.

        :param payload: A ``{kind:"Listing", data:{...}}`` response.
        :type payload: t.Dict[str, t.Any]
        :returns: The parsed page.
        :rtype: Listing
        """

        data = payload.get("data", {})
        children: t.List[Thing] = []
        for child in data.get("children", []):
            parsed = parse_thing(child)
            if parsed is not None:
                children.append(parsed)

        return cls(
            after=data.get("after"),
            before=data.get("before"),
            dist=data.get("dist"),
            children=children,
        )
