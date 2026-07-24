"""
The grouped Reddit API.

:class:`Reddit` is the one entry point. It hands out small handles, one per Reddit entity, and a
few collections for search and bulk feeds. Each handle method runs one read and returns models.
The reads run through :meth:`Endpoint._get` and :meth:`Endpoint.paginate`; :class:`RedditAuth`
sits behind them and supplies the session and token. Nothing here exposes them.
"""

import typing as t

import requests

from .auth import RedditAuth
from .models import (
    Comment,
    Listing,
    MultiReddit,
    Post,
    Subreddit,
    Thing,
    Trophy,
    User,
)

LISTINGS = t.Literal["controversial", "gilded", "hot", "new", "rising", "top"]
TIME_FILTERS = t.Literal["all", "hour", "day", "week", "month", "year"]
SORT = t.Literal["relevance", "hot", "top", "new", "comments"]

API_BASE = "https://oauth.reddit.com"
STATUS_URL = "https://www.redditstatus.com/api/v2/status.json"
PAGE_LIMIT = 100  # Reddit's per-request maximum.

# So :meth:`Reddit.__handle` returns the exact handle subclass it builds.
Handle = t.TypeVar("Handle", bound="Endpoint")

__all__ = ["Reddit", "API_BASE", "STATUS_URL", "PAGE_LIMIT", "SORT"]


class Endpoint:
    """
    Base for the handles.

    It holds the shared :class:`RedditAuth` and the two read primitives every handle needs:
    :meth:`_get` for one request and :meth:`paginate` for a listing walk.
    """

    def __init__(self, auth: RedditAuth):
        """
        Bind to the shared auth.

        :param auth: The shared auth.
        :type auth: RedditAuth
        """

        self.auth = auth
        self.on_progress: t.Optional[t.Callable[[int, t.Optional[int]], None]] = None

    def get(self, path: str, params: t.Optional[t.Dict[str, t.Any]] = None) -> t.Any:
        """
        Send a GET to the API and return the parsed JSON.

        On a 401 it mints a new token once and retries. A 404 returns None, so callers read a
        missing user, subreddit, or post as None. Every other error status raises, so a rate limit,
        an auth failure, or a server fault stops the run instead of looking like no results.

        :param path: Path under ``oauth.reddit.com``, for example ``/r/pics/hot``.
        :type path: str
        :param params: Query parameters.
        :type params: t.Optional[t.Dict[str, t.Any]]
        :returns: The parsed JSON body, or None when the thing is not found.
        :rtype: t.Any
        :raises requests.HTTPError: On any error status other than 404.
        """

        url = f"{API_BASE}{path}"
        query = {"raw_json": 1, **(params or {})}  # raw_json=1 returns unescaped text
        response = self.auth.session.get(
            url,
            params=query,
            headers={"Authorization": f"bearer {self.auth.get_bearer_token()}"},
            timeout=30,
        )
        if response.status_code == 401:
            response = self.auth.session.get(
                url,
                params=query,
                headers={"Authorization": f"bearer {self.auth.mint_token()}"},
                timeout=30,
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def paginate(
            self,
            path: str,
            limit: t.Optional[int],
            params: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> t.List[Thing]:
        """
        Walk a listing across pages and return its things.

        The walk follows the ``after`` cursor. It drops any thing whose bare id it has already
        seen, the way RedReader dedups a feed. A ``limit`` of None reads until the listing ends.
        After each page it calls :attr:`on_progress` with the running count and the limit.

        :param path: Listing path, without the ``.json`` suffix.
        :type path: str
        :param limit: Maximum things to return, or None for all.
        :type limit: t.Optional[int]
        :param params: Extra query parameters, such as ``sort`` or ``t``.
        :type params: t.Optional[t.Dict[str, t.Any]]
        :returns: The collected things, in order.
        :rtype: t.List[Thing]
        """

        collected: t.List[Thing] = []
        seen: t.Set[str] = set()
        after: t.Optional[str] = None
        query = dict(params or {})

        while limit is None or len(collected) < limit:
            room = PAGE_LIMIT if limit is None else min(PAGE_LIMIT, limit - len(collected))
            query["limit"] = room
            if after:
                query["after"] = after

            payload = self.get(path=f"{path}.json", params=query)
            if payload is None:
                break

            listing = Listing.from_response(payload)
            if not listing.children:
                break

            for thing in listing.children:
                key = getattr(thing, "id", None)
                if key is not None and key in seen:
                    continue
                if key is not None:
                    seen.add(str(key))
                collected.append(thing)
                if limit is not None and len(collected) >= limit:
                    break

            if self.on_progress:
                self.on_progress(len(collected), limit)

            if not listing.after:
                break
            after = listing.after

        return collected


class UserEndpoint(Endpoint):
    """Reads for one user. Get it from :meth:`Reddit.user`."""

    def __init__(self, auth: RedditAuth, username: str):
        """
        Bind to a username. This runs no request.

        :param auth: The shared auth.
        :type auth: RedditAuth
        :param username: The user's name.
        :type username: str
        """

        super().__init__(auth)
        self.username = username

    def about(self) -> t.Optional[User]:
        """
        Get the user's profile.

        :returns: The user, or None when the account does not exist.
        :rtype: t.Optional[User]
        """

        payload = self.get(path=f"/user/{self.username}/about.json")
        if not payload or payload.get("kind") != "t2":
            return None
        return User.from_data(payload.get("data", {}))

    def exists(self) -> bool:
        """
        Say whether the account exists.

        Reddit's name-availability check answers this in one light request. A taken name means the
        account exists. A free name, a malformed name, or a 404 means it does not.

        :returns: True when the account exists.
        :rtype: bool
        """

        is_available = self.get(path="/api/username_available.json", params={"user": self.username})
        return is_available is False

    def posts(
            self,
            listing: LISTINGS = "new",
            limit: t.Optional[int] = PAGE_LIMIT,
            timeframe: TIME_FILTERS = "all",
    ) -> t.List[Post]:
        """
        Get the user's submitted posts.

        :param listing: Sort of the posts.
        :type listing: LISTINGS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param timeframe: Time window for ``top`` and ``controversial``.
        :type timeframe: TIME_FILTERS
        :returns: The posts.
        :rtype: t.List[Post]
        """

        params = {"sort": listing, "t": timeframe}
        things = self.paginate(path=f"/user/{self.username}/submitted", limit=limit, params=params)
        return [thing for thing in things if isinstance(thing, Post)]

    def comments(
            self,
            limit: t.Optional[int] = PAGE_LIMIT,
            sort: SORT = "new",
    ) -> t.List[Comment]:
        """
        Get the user's comments.

        :param limit: Most comments to return, or None for all.
        :type limit: t.Optional[int]
        :param sort: Sort of the comments.
        :type sort: SORT
        :returns: The comments.
        :rtype: t.List[Comment]
        """

        params = {"sort": sort}
        things = self.paginate(path=f"/user/{self.username}/comments", limit=limit, params=params)
        return [thing for thing in things if isinstance(thing, Comment)]

    def overview(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[Thing]:
        """
        Get the user's posts and comments together, newest first.

        :param limit: Most items to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The posts and comments.
        :rtype: t.List[Thing]
        """

        return self.paginate(path=f"/user/{self.username}/overview", limit=limit)

    def moderated(self) -> t.List[Subreddit]:
        """
        List the subreddits the user moderates.

        :returns: The moderated subreddits.
        :rtype: t.List[Subreddit]
        """

        payload = self.get(path=f"/user/{self.username}/moderated_subreddits.json")
        if payload is None:
            return []
        return [Subreddit.from_data(item) for item in payload.get("data", [])]

    def trophies(self) -> t.List[Trophy]:
        """
        Get the user's trophies.

        :returns: The trophies.
        :rtype: t.List[Trophy]
        """

        payload = self.get(path=f"/user/{self.username}/trophies.json")
        if payload is None:
            return []
        return [
            Trophy.from_data(item.get("data", {}))
            for item in payload.get("data", {}).get("trophies", [])
        ]

    def multireddits(self) -> t.List[MultiReddit]:
        """
        List the user's public multireddits.

        :returns: The multireddits.
        :rtype: t.List[MultiReddit]
        """

        payload = self.get(path=f"/api/multi/user/{self.username}")
        if payload is None:
            return []
        return [MultiReddit.from_data(item.get("data", {})) for item in payload]


class SubredditEndpoint(Endpoint):
    """Reads for one subreddit. Get it from :meth:`Reddit.subreddit`."""

    def __init__(self, auth: RedditAuth, name: str):
        """
        Bind to a subreddit name. This runs no request.

        :param auth: The shared auth.
        :type auth: RedditAuth
        :param name: The subreddit name.
        :type name: str
        """

        super().__init__(auth)
        self.name = name

    def about(self) -> t.Optional[Subreddit]:
        """
        Get the subreddit's profile.

        :returns: The subreddit, or None when it does not exist.
        :rtype: t.Optional[Subreddit]
        """

        payload = self.get(path=f"/r/{self.name}/about.json")
        if not payload or payload.get("kind") != "t5":
            return None
        return Subreddit.from_data(payload.get("data", {}))

    def exists(self) -> bool:
        """
        Say whether the subreddit exists and is reachable.

        :returns: True when the subreddit exists.
        :rtype: bool
        """

        return self.about() is not None

    def posts(
            self,
            listing: LISTINGS = "hot",
            limit: t.Optional[int] = PAGE_LIMIT,
            timeframe: TIME_FILTERS = "all",
    ) -> t.List[Post]:
        """
        Get posts from the subreddit.

        :param listing: Sort of the feed.
        :type listing: LISTINGS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param timeframe: Time window for ``top`` and ``controversial``.
        :type timeframe: TIME_FILTERS
        :returns: The posts.
        :rtype: t.List[Post]
        """

        base = f"/r/{self.name}" if self.name else ""
        params = {"t": timeframe} if listing in ("top", "controversial") else None
        things = self.paginate(path=f"{base}/{listing}", limit=limit, params=params)
        return [thing for thing in things if isinstance(thing, Post)]

    def comments(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[Comment]:
        """
        Get the subreddit's recent comments.

        :param limit: Most comments to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The recent comments.
        :rtype: t.List[Comment]
        """

        things = self.paginate(path=f"/r/{self.name}/comments", limit=limit)
        return [thing for thing in things if isinstance(thing, Comment)]

    def search(
            self,
            query: str,
            sort: SORT = "relevance",
            timeframe: TIME_FILTERS = "all",
            limit: t.Optional[int] = PAGE_LIMIT,
    ) -> t.List[Post]:
        """
        Search posts inside the subreddit.

        :param query: Search text.
        :type query: str
        :param sort: Sort of the results.
        :type sort: SORT
        :param timeframe: Time window.
        :type timeframe: TIME_FILTERS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The matching posts.
        :rtype: t.List[Post]
        """

        params = {"q": query, "restrict_sr": "on", "sort": sort, "t": timeframe}
        things = self.paginate(path=f"/r/{self.name}/search", limit=limit, params=params)
        return [thing for thing in things if isinstance(thing, Post)]

    def wiki_pages(self) -> t.List[str]:
        """
        List the subreddit's wiki page names.

        :returns: The wiki page names.
        :rtype: t.List[str]
        """

        payload = self.get(path=f"/r/{self.name}/wiki/pages.json")
        if payload is None:
            return []
        return list(payload.get("data", []))


class PostEndpoint(Endpoint):
    """Reads for one post. Get it from :meth:`Reddit.post`."""

    def __init__(self, auth: RedditAuth, post_id: str):
        """
        Bind to a post id. This runs no request.

        :param auth: The shared auth.
        :type auth: RedditAuth
        :param post_id: The post id, with or without the ``t3_`` prefix.
        :type post_id: str
        """

        super().__init__(auth)
        self.id = post_id[3:] if post_id.startswith("t3_") else post_id

    def about(self, sort: SORT = "top") -> t.Optional[Post]:
        """
        Get the post.

        :param sort: Comment sort passed to the endpoint.
        :type sort: SORT
        :returns: The post, or None when it does not exist.
        :rtype: t.Optional[Post]
        """

        payload = self.get(path=f"/comments/{self.id}.json", params={"limit": 1, "sort": sort})
        if payload is None:
            return None
        listing = Listing.from_response(payload[0])
        posts = [thing for thing in listing.children if isinstance(thing, Post)]
        return posts[0] if posts else None

    def comments(
            self,
            sort: SORT = "top",
            limit: t.Optional[int] = PAGE_LIMIT,
            depth: t.Optional[int] = 1,
    ) -> t.List[Comment]:
        """
        Get the post's comments.

        Reddit sends the comment tree with the long or deep parts cut off behind ``load more``
        stubs. ``depth`` sets how far to follow them, counting from the top of the tree:

        - ``0`` follows nothing. You get the first response as it came.
        - ``1`` follows the stubs at the top level, so you get every top-level comment.
        - ``n`` also follows stubs down to reply level ``n``.
        - ``None`` follows every stub until the tree runs out.

        Each stub costs one request per child id. A busy thread holds thousands of ids, so a high
        ``depth`` can fire thousands of requests. Keep ``depth`` low, or raise it when you must.

        :param sort: Comment sort.
        :type sort: SORT
        :param limit: Most comments the first request returns, before any stub is followed.
        :type limit: t.Optional[int]
        :param depth: How far to follow ``load more`` stubs. See above.
        :type depth: t.Optional[int]
        :returns: The comments, each with its nested replies.
        :rtype: t.List[Comment]
        """

        params: t.Dict[str, t.Any] = {"sort": sort}
        if limit is not None:
            params["limit"] = limit
        payload = self.get(path=f"/comments/{self.id}.json", params=params)
        if payload is None:
            return []

        raw_children = payload[1].get("data", {}).get("children", [])
        expanded = self.__follow(raw_children, sort, depth, level=0)
        listing = Listing.from_response({"data": {"children": expanded}})
        return [child for child in listing.children if isinstance(child, Comment)]

    def __follow(
            self,
            raw_children: t.List[t.Dict[str, t.Any]],
            sort: SORT,
            depth: t.Optional[int],
            level: int,
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Walk a raw comment listing and follow ``load more`` stubs up to ``depth``.

        This works on Reddit's raw ``{kind, data}`` dicts so it can splice fetched comments back
        into the tree where their stub sat. A stub at a level below ``depth`` is fetched and its
        comments take its place. A stub at or past ``depth`` stays as it is.

        :param raw_children: The raw children of one listing.
        :type raw_children: t.List[t.Dict[str, t.Any]]
        :param sort: Comment sort.
        :type sort: SORT
        :param depth: How far to follow stubs, or None for all the way.
        :type depth: t.Optional[int]
        :param level: The nesting level of these children. The top level is 0.
        :type level: int
        :returns: The children with stubs followed where ``depth`` allows.
        :rtype: t.List[t.Dict[str, t.Any]]
        """

        out: t.List[t.Dict[str, t.Any]] = []
        for node in raw_children:
            kind = node.get("kind")
            if kind == "more":
                if depth is None or level < depth:
                    fetched = self.__fetch_more(node.get("data", {}), sort)
                    out.extend(self.__follow(fetched, sort, depth, level))
                else:
                    out.append(node)
            elif kind == "t1":
                replies = node.get("data", {}).get("replies")
                if isinstance(replies, dict):
                    node["data"]["replies"]["data"]["children"] = self.__follow(
                        replies.get("data", {}).get("children", []), sort, depth, level + 1
                    )
                out.append(node)
            else:
                out.append(node)
        return out

    def __fetch_more(
            self,
            more_data: t.Dict[str, t.Any],
            sort: SORT,
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Fetch the raw comments behind one ``load more`` stub.

        The stub names child ids to fetch, one request each. A "continue this thread" stub names no
        children, so this follows its ``parent_id`` instead.

        :param more_data: The stub's ``data`` body.
        :type more_data: t.Dict[str, t.Any]
        :param sort: Comment sort.
        :type sort: SORT
        :returns: The raw child dicts the stub stood for.
        :rtype: t.List[t.Dict[str, t.Any]]
        """

        ids = more_data.get("children") or (
            [more_data["parent_id"]] if more_data.get("parent_id") else []
        )
        raw: t.List[t.Dict[str, t.Any]] = []
        for child_id in ids:
            bare = child_id.split("_")[-1]
            payload = self.get(
                path=f"/comments/{self.id}/comment/{bare}.json",
                params={"sort": sort, "context": 0},
            )
            if payload is None:
                continue
            raw.extend(payload[1].get("data", {}).get("children", []))
        return raw


class MultiRedditEndpoint(Endpoint):
    """Reads for one multireddit. Get it from :meth:`Reddit.multireddit`."""

    def __init__(self, auth: RedditAuth, owner: str, name: str):
        """
        Bind to a multireddit owner and name. This runs no request.

        :param auth: The shared auth.
        :type auth: RedditAuth
        :param owner: The owner's name.
        :type owner: str
        :param name: The multireddit's name.
        :type name: str
        """

        super().__init__(auth)
        self.owner = owner
        self.name = name

    def posts(
            self,
            listing: LISTINGS = "hot",
            limit: t.Optional[int] = PAGE_LIMIT,
            timeframe: TIME_FILTERS = "all",
    ) -> t.List[Post]:
        """
        Get posts from the multireddit.

        :param listing: Sort of the feed.
        :type listing: LISTINGS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param timeframe: Time window for ``top`` and ``controversial``.
        :type timeframe: TIME_FILTERS
        :returns: The posts.
        :rtype: t.List[Post]
        """

        params = {"t": timeframe} if listing in ("top", "controversial") else None
        things = self.paginate(
            path=f"/user/{self.owner}/m/{self.name}/{listing}", limit=limit, params=params
        )
        return [thing for thing in things if isinstance(thing, Post)]


class Search(Endpoint):
    """Search across Reddit. Reach it as :attr:`Reddit.search`."""

    def posts(
            self,
            query: str,
            sort: SORT = "relevance",
            timeframe: TIME_FILTERS = "all",
            limit: t.Optional[int] = PAGE_LIMIT,
            include_nsfw: bool = True,
    ) -> t.List[Post]:
        """
        Search posts across Reddit.

        :param query: Search text.
        :type query: str
        :param sort: Sort of the results.
        :type sort: SORT
        :param timeframe: Time window.
        :type timeframe: TIME_FILTERS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param include_nsfw: Whether to include NSFW results.
        :type include_nsfw: bool
        :returns: The matching posts.
        :rtype: t.List[Post]
        """

        params: t.Dict[str, t.Any] = {"q": query, "sort": sort, "t": timeframe}
        if include_nsfw:
            params["include_over_18"] = "on"
        things = self.paginate(path="/search", limit=limit, params=params)
        return [thing for thing in things if isinstance(thing, Post)]

    def subreddits(
            self,
            query: str,
            limit: t.Optional[int] = PAGE_LIMIT,
    ) -> t.List[Subreddit]:
        """
        Search subreddits by name and description.

        :param query: Search text.
        :type query: str
        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The matching subreddits.
        :rtype: t.List[Subreddit]
        """

        things = self.paginate(path="/subreddits/search", limit=limit, params={"q": query})
        return [thing for thing in things if isinstance(thing, Subreddit)]

    def users(
            self,
            query: str,
            limit: t.Optional[int] = PAGE_LIMIT,
    ) -> t.List[User]:
        """
        Search users by name.

        :param query: Search text.
        :type query: str
        :param limit: Most users to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The matching users.
        :rtype: t.List[User]
        """

        things = self.paginate(path="/users/search", limit=limit, params={"q": query})
        return [thing for thing in things if isinstance(thing, User)]


class SubredditsFeed(Endpoint):
    """Bulk subreddit feeds. Reach it as :attr:`Reddit.subreddits`."""

    def popular(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[Subreddit]:
        """
        Get the popular subreddits feed.

        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The subreddits.
        :rtype: t.List[Subreddit]
        """

        things = self.paginate(path="/subreddits/popular", limit=limit)
        return [thing for thing in things if isinstance(thing, Subreddit)]

    def new(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[Subreddit]:
        """
        Get the new subreddits feed.

        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The subreddits.
        :rtype: t.List[Subreddit]
        """

        things = self.paginate(path="/subreddits/new", limit=limit)
        return [thing for thing in things if isinstance(thing, Subreddit)]

    def default(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[Subreddit]:
        """
        Get the default subreddits feed.

        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The subreddits.
        :rtype: t.List[Subreddit]
        """

        things = self.paginate(path="/subreddits/default", limit=limit)
        return [thing for thing in things if isinstance(thing, Subreddit)]


class UsersFeed(Endpoint):
    """Bulk user feeds. Reach it as :attr:`Reddit.users`."""

    def popular(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[User]:
        """
        Get the popular users feed.

        Each user carries only a name. Call :meth:`UserEndpoint.about` for the rest.

        :param limit: Most users to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The users.
        :rtype: t.List[User]
        """

        things = self.paginate(path="/users/popular", limit=limit)
        return [
            User.from_profile_subreddit(thing.raw)
            for thing in things
            if isinstance(thing, Subreddit)
        ]

    def new(self, limit: t.Optional[int] = PAGE_LIMIT) -> t.List[User]:
        """
        Get the new users feed.

        Each user carries only a name. Call :meth:`UserEndpoint.about` for the rest.

        :param limit: Most users to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The users.
        :rtype: t.List[User]
        """

        things = self.paginate(path="/users/new", limit=limit)
        return [
            User.from_profile_subreddit(thing.raw)
            for thing in things
            if isinstance(thing, Subreddit)
        ]


class Reddit:
    """
    The Reddit API, grouped by entity.

    Build one, then reach an entity through its handle::

        reddit = Reddit()
        reddit.user("spez").about()
        reddit.subreddit("python").posts(listing="top", timeframe="week")
        reddit.search.posts("climate")

    A handle is cheap and runs no request. The read happens when you call a method on it.
    """

    def __init__(
            self,
            user_agent: t.Optional[str] = None,
            session: t.Optional[requests.Session] = None,
    ):
        """
        Set up the API.

        :param user_agent: User agent to send. Falls back to ``KNEWKARMA_USER_AGENT``, then to a
            built-in one.
        :type user_agent: t.Optional[str]
        :param session: An existing requests session to reuse.
        :type session: t.Optional[requests.Session]
        """

        self.__auth = RedditAuth(user_agent=user_agent, session=session)
        self.on_progress: t.Optional[t.Callable[[int, t.Optional[int]], None]] = None

    def __handle(self, cls: t.Callable[..., Handle], *args: str) -> Handle:
        """
        Build a handle on the shared auth and stamp the progress callback onto it.

        :param cls: The handle class to build.
        :type cls: t.Callable[..., Handle]
        :param args: Extra names the handle needs, such as a username or a subreddit name.
        :type args: str
        :returns: The handle.
        :rtype: Handle
        """

        handle = cls(self.__auth, *args)
        handle.on_progress = self.on_progress
        return handle

    @property
    def on_status(self) -> t.Optional[t.Callable[[str], None]]:
        """
        The status callback. It runs with a short message when the auth mints a token.

        :returns: The callback, or None.
        :rtype: t.Optional[t.Callable[[str], None]]
        """

        return self.__auth.on_status

    @on_status.setter
    def on_status(self, callback: t.Optional[t.Callable[[str], None]]) -> None:
        self.__auth.on_status = callback

    @property
    def search(self) -> Search:
        """
        A handle for searching Reddit.

        :returns: The search handle.
        :rtype: Search
        """

        return self.__handle(Search)

    @property
    def subreddits(self) -> SubredditsFeed:
        """
        A handle for the bulk subreddit feeds.

        :returns: The subreddit feeds handle.
        :rtype: SubredditsFeed
        """

        return self.__handle(SubredditsFeed)

    @property
    def users(self) -> UsersFeed:
        """
        A handle for the bulk user feeds.

        :returns: The user feeds handle.
        :rtype: UsersFeed
        """

        return self.__handle(UsersFeed)

    def user(self, username: str) -> UserEndpoint:
        """
        Get a handle for one user.

        :param username: The user's name.
        :type username: str
        :returns: The user handle.
        :rtype: UserEndpoint
        """

        return self.__handle(UserEndpoint, username)

    def subreddit(self, name: str) -> SubredditEndpoint:
        """
        Get a handle for one subreddit.

        :param name: The subreddit name, or ``""`` for the front page.
        :type name: str
        :returns: The subreddit handle.
        :rtype: SubredditEndpoint
        """

        return self.__handle(SubredditEndpoint, name)

    def post(self, post_id: str) -> PostEndpoint:
        """
        Get a handle for one post.

        :param post_id: The post id, with or without the ``t3_`` prefix.
        :type post_id: str
        :returns: The post handle.
        :rtype: PostEndpoint
        """

        return self.__handle(PostEndpoint, post_id)

    def multireddit(self, owner: str, name: str) -> MultiRedditEndpoint:
        """
        Get a handle for one multireddit.

        :param owner: The owner's name.
        :type owner: str
        :param name: The multireddit's name.
        :type name: str
        :returns: The multireddit handle.
        :rtype: MultiRedditEndpoint
        """

        return self.__handle(MultiRedditEndpoint, owner, name)

    def status(self) -> t.Dict[str, str]:
        """
        Read Reddit's status page.

        :returns: The status, with ``indicator`` (``none`` means all is well) and ``description``.
        :rtype: t.Dict[str, str]
        :raises requests.HTTPError: When the status request fails.
        """

        response = self.__auth.session.get(STATUS_URL, timeout=10)
        response.raise_for_status()
        return response.json().get("status", {})
