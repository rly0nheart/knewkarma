"""
Data models for Reddit's JSON API.

Reddit wraps every object as a thing: a dict with a ``kind`` tag and a ``data`` body. Each model
here wraps one ``data`` body whole and exposes every field it holds as an attribute. So a post
carries all 100-plus fields the API sends, not a chosen few.

Kinds: ``t1`` comment, ``t2`` user, ``t3`` post, ``t5`` subreddit, ``t6`` trophy, ``more`` (a
stub naming comment ids to fetch), and ``Listing`` (a page with paging cursors).
"""

import typing as t
from dataclasses import dataclass, field


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
    def from_data(cls, data: t.Dict[str, t.Any]) -> "RedditObject":
        """
        Wrap a thing's ``data`` body.

        :param data: The thing's ``data`` dict.
        :type data: t.Dict[str, t.Any]
        :returns: The wrapped object.
        :rtype: RedditObject
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

    builder = _BUILDERS.get(thing.get("kind"))
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
