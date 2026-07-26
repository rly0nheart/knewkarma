"""
The grouped Reddit API.

:class:`Reddit` is the one entry point. It hands out small handles, one per Reddit entity, and a
few collections for search and bulk feeds. Each handle method runs one read and returns models.
The reads run through :meth:`Endpoint.get` and :meth:`Endpoint.paginate`; :class:`RedditAuth`
sits behind them and supplies the session and token. Nothing here exposes them.

A read that returns many things returns a :class:`~knewkarma.core.models.Things` list, which is a
plain list that can also write itself to json or csv.
"""

import random
import time
import typing as t
from collections import OrderedDict

import requests

from .auth import RedditAuth
from .models import (
    Comment,
    Listing,
    MultiReddit,
    Post,
    Subreddit,
    Thing,
    Things,
    Trophy,
    User,
)

LISTINGS = t.Literal["controversial", "gilded", "hot", "new", "rising", "top"]
TIME_FILTERS = t.Literal["all", "hour", "day", "week", "month", "year"]
SORT = t.Literal["relevance", "hot", "top", "new", "comments"]
KINDS = t.Literal["posts", "comments"]

API_BASE = "https://oauth.reddit.com"
STATUS_URL = "https://www.redditstatus.com/api/v2/status.json"
PAGE_LIMIT = 100  # Reddit's per-request maximum.
MORE_CHILDREN_LIMIT = 100  # Most comment ids one bulk "load more" read takes.
MORE_REQUEST_BUDGET = 256  # Most requests one comment read spends following "load more" stubs.

STREAM_DELAY = 1.0  # Seconds a stream waits after its first empty round.
STREAM_MAX_DELAY = 16.0  # Longest a stream waits between rounds.
STREAM_SPREAD = 30  # How many rounds a stream takes to walk its limit down and back.
STREAM_TICK = 0.25  # How often a waiting stream reports the seconds left.

# So :meth:`Reddit.__handle` returns the exact handle subclass it builds.
Handle = t.TypeVar("Handle", bound="Endpoint")

__all__ = ["Reddit", "API_BASE", "STATUS_URL", "PAGE_LIMIT", "SORT", "UserEndpoint", "SubredditEndpoint"]


class SeenIds:
    """A set of ids that drops its oldest once full. :meth:`SubredditEndpoint.stream` dedups on it."""

    def __init__(self, capacity: int):
        """
        Set how many ids to hold.

        :param capacity: How many ids to remember.
        :type capacity: int
        """

        self.capacity = capacity
        self.ids: "OrderedDict[str, None]" = OrderedDict()

    def __contains__(self, thing_id: str) -> bool:
        seen = thing_id in self.ids
        if seen:
            self.ids.move_to_end(thing_id)
        return seen

    def __len__(self) -> int:
        return len(self.ids)

    def add(self, thing_id: str):
        """
        Remember an id, dropping the oldest when full.

        :param thing_id: The id to remember.
        :type thing_id: str
        """

        self.ids[thing_id] = None
        self.ids.move_to_end(thing_id)
        while len(self.ids) > self.capacity:
            self.ids.popitem(last=False)


class Budget:
    """
    How many more requests a comment walk may spend.

    :meth:`PostEndpoint.comments` sets one and the walk spends it. Without it a wide thread can
    hand back fresh stubs faster than they are followed, and the walk never ends on its own.
    """

    def __init__(self, limit: t.Optional[int]):
        """
        Set how many requests may be spent.

        :param limit: How many requests to allow, or None for no limit.
        :type limit: t.Optional[int]
        """

        self.left = limit

    def is_spent(self) -> bool:
        """
        Say whether the budget is gone. Ask before spending.

        :returns: True when nothing is left, so no more requests should go out.
        :rtype: bool
        """

        return self.left is not None and self.left <= 0

    def spend(self):
        """Take one request from the budget."""

        if self.left is not None:
            self.left -= 1


class Endpoint:
    """
    Base for the handles.

    It holds the shared :class:`RedditAuth` and the two read primitives every handle needs:
    :meth:`get` for one request and :meth:`paginate` for a listing walk.
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

        On a 401 it mints a new token once and retries. On a 429 it waits the delay Reddit names
        and retries once. A 404 returns None, so callers read a missing user, subreddit, or post as
        None. Every other error status raises, so a failure stops the run instead of looking like
        no results.

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
        response = self.send(url=url, query=query)
        if response.status_code == 401:
            response = self.send(url=url, query=query, fresh_token=True)
        if response.status_code == 429:
            self.auth.rate_limit.back_off(response.headers)
            response = self.send(url=url, query=query)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def send(
            self,
            url: str,
            query: t.Dict[str, t.Any],
            fresh_token: bool = False,
    ) -> requests.Response:
        """
        Wait for the rate limit, send one request, then feed its headers back to the rate limit.

        :param url: The full URL.
        :type url: str
        :param query: Query parameters.
        :type query: t.Dict[str, t.Any]
        :param fresh_token: Whether to mint a new token instead of using the current one.
        :type fresh_token: bool
        :returns: The response, whatever its status.
        :rtype: requests.Response
        """

        token = self.auth.mint_token() if fresh_token else self.auth.get_bearer_token()
        self.auth.rate_limit.wait()
        response = self.auth.session.get(
            url,
            params=query,
            headers={"Authorization": f"bearer {token}"},
            timeout=30,
        )
        self.auth.rate_limit.update(response.headers)
        return response

    def paginate(
            self,
            path: str,
            limit: t.Optional[int],
            params: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> Things[Thing]:
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
        :rtype: Things[Thing]
        """

        collected: Things[Thing] = Things()
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

            listing = Listing.from_response(payload=payload)
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
        return User.from_data(data=payload.get("data", {}))

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
    ) -> Things[Post]:
        """
        Get the user's submitted posts.

        :param listing: Sort of the posts.
        :type listing: LISTINGS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param timeframe: Time window for ``top`` and ``controversial``.
        :type timeframe: TIME_FILTERS
        :returns: The posts.
        :rtype: Things[Post]
        """

        params = {"sort": listing, "t": timeframe}
        things = self.paginate(path=f"/user/{self.username}/submitted", limit=limit, params=params)
        return Things(thing for thing in things if isinstance(thing, Post))

    def comments(
            self,
            limit: t.Optional[int] = PAGE_LIMIT,
            sort: SORT = "new",
    ) -> Things[Comment]:
        """
        Get the user's comments.

        :param limit: Most comments to return, or None for all.
        :type limit: t.Optional[int]
        :param sort: Sort of the comments.
        :type sort: SORT
        :returns: The comments.
        :rtype: Things[Comment]
        """

        params = {"sort": sort}
        things = self.paginate(path=f"/user/{self.username}/comments", limit=limit, params=params)
        return Things(thing for thing in things if isinstance(thing, Comment))

    def overview(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[Thing]:
        """
        Get the user's posts and comments together, newest first.

        :param limit: Most items to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The posts and comments.
        :rtype: Things[Thing]
        """

        return self.paginate(path=f"/user/{self.username}/overview", limit=limit)

    def moderated(self) -> Things[Subreddit]:
        """
        List the subreddits the user moderates.

        :returns: The moderated subreddits.
        :rtype: Things[Subreddit]
        """

        payload = self.get(path=f"/user/{self.username}/moderated_subreddits.json")
        if payload is None:
            return Things()
        return Things(Subreddit.from_data(data=item) for item in payload.get("data", []))

    def trophies(self) -> Things[Trophy]:
        """
        Get the user's trophies.

        :returns: The trophies.
        :rtype: Things[Trophy]
        """

        payload = self.get(path=f"/user/{self.username}/trophies.json")
        if payload is None:
            return Things()
        return Things(
            Trophy.from_data(data=item.get("data", {}))
            for item in payload.get("data", {}).get("trophies", [])
        )

    def multireddits(self) -> Things[MultiReddit]:
        """
        List the user's public multireddits.

        :returns: The multireddits.
        :rtype: Things[MultiReddit]
        """

        payload = self.get(path=f"/api/multi/user/{self.username}")
        if payload is None:
            return Things()
        return Things(MultiReddit.from_data(data=item.get("data", {})) for item in payload)


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
        return Subreddit.from_data(data=payload.get("data", {}))

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
    ) -> Things[Post]:
        """
        Get posts from the subreddit.

        :param listing: Sort of the feed.
        :type listing: LISTINGS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param timeframe: Time window for ``top`` and ``controversial``.
        :type timeframe: TIME_FILTERS
        :returns: The posts.
        :rtype: Things[Post]
        """

        base = f"/r/{self.name}" if self.name else ""
        params = {"t": timeframe} if listing in ("top", "controversial") else None
        things = self.paginate(path=f"{base}/{listing}", limit=limit, params=params)
        return Things(thing for thing in things if isinstance(thing, Post))

    def stream(
            self,
            kind: KINDS = "posts",
            skip_existing: bool = False,
            pause_after: t.Optional[int] = None,
            on_wait: t.Optional[t.Callable[[float], None]] = None,
    ) -> t.Iterator[t.Optional[Thing]]:
        """
        Yield new posts or comments as they appear, in the order they were made, until you leave
        the loop.

        :param kind: Whether to read the ``new`` listing or the subreddit's comments.
        :type kind: KINDS
        :param skip_existing: Whether to drop the things already there when the stream starts.
        :type skip_existing: bool
        :param pause_after: Yield None after this many quiet rounds, or None to never pause.
        :type pause_after: t.Optional[int]
        :param on_wait: Called with the seconds left before the next read, as the wait counts down.
        :type on_wait: t.Optional[t.Callable[[float], None]]
        :returns: The posts or comments, and None on a pause.
        :rtype: t.Iterator[t.Optional[Thing]]
        """

        base = f"/r/{self.name}" if self.name else ""
        path, model = (
            (f"{base}/comments.json", Comment) if kind == "comments" else (f"{base}/new.json", Post)
        )
        seen = SeenIds(PAGE_LIMIT * 3)  # a few pages, so one busy round cannot flush it
        delay = STREAM_DELAY
        quiet_rounds = 0
        spread = 0
        before: t.Optional[str] = None
        first_round = True

        while True:
            limit = PAGE_LIMIT
            if before is None:
                # Walk the limit down so Reddit cannot answer every round from one cached page.
                limit -= spread
                spread = (spread + 1) % STREAM_SPREAD

            params: t.Dict[str, t.Any] = {"limit": limit}
            if before is not None:
                params["before"] = before  # only things newer than the last one handed out

            payload = self.get(path=path, params=params)
            children = Listing.from_response(payload=payload).children if payload else []

            fresh: t.List[Thing] = []
            for thing in children:
                if not isinstance(thing, model) or thing.name in seen:
                    continue
                seen.add(thing.name)
                fresh.append(thing)

            before = fresh[0].name if fresh else None  # a quiet round drops back to a plain read
            if first_round and skip_existing:
                fresh = []  # they sit in `seen` now, so they will not come back
            first_round = False

            if fresh:
                delay = STREAM_DELAY
                quiet_rounds = 0
                yield from reversed(fresh)
                continue

            quiet_rounds += 1
            if pause_after is not None and quiet_rounds >= pause_after:
                quiet_rounds = 0
                yield None

            wait = delay * random.uniform(0.97, 1.03)
            while wait > 0:
                if on_wait:
                    on_wait(wait)
                nap = min(STREAM_TICK, wait)
                time.sleep(nap)
                wait -= nap
            delay = min(delay * 2, STREAM_MAX_DELAY)

    def comments(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[Comment]:
        """
        Get the subreddit's recent comments.

        :param limit: Most comments to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The recent comments.
        :rtype: Things[Comment]
        """

        base = f"/r/{self.name}" if self.name else ""
        things = self.paginate(path=f"{base}/comments", limit=limit)
        return Things(thing for thing in things if isinstance(thing, Comment))

    def search(
            self,
            query: str,
            sort: SORT = "relevance",
            timeframe: TIME_FILTERS = "all",
            limit: t.Optional[int] = PAGE_LIMIT,
    ) -> Things[Post]:
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
        :rtype: Things[Post]
        """

        base = f"/r/{self.name}" if self.name else ""
        params = {"q": query, "restrict_sr": "on", "sort": sort, "t": timeframe}
        things = self.paginate(path=f"{base}/search", limit=limit, params=params)
        return Things(thing for thing in things if isinstance(thing, Post))

    def wiki_pages(self) -> Things[str]:
        """
        List the subreddit's wiki page names.

        :returns: The wiki page names.
        :rtype: Things[str]
        """

        payload = self.get(path=f"/r/{self.name}/wiki/pages.json")
        if payload is None:
            return Things()
        return Things(payload.get("data", []))


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
        listing = Listing.from_response(payload=payload[0])
        posts = [thing for thing in listing.children if isinstance(thing, Post)]
        return posts[0] if posts else None

    def comments(
            self,
            sort: SORT = "top",
            limit: t.Optional[int] = PAGE_LIMIT,
            depth: t.Optional[int] = 1,
            budget: t.Optional[int] = MORE_REQUEST_BUDGET,
    ) -> Things[Comment]:
        """
        Get the post's comments.

        Reddit sends the comment tree with the long or deep parts cut off behind ``load more``
        stubs. ``depth`` sets how far to follow them, counting from the top of the tree:

        - ``0`` follows nothing. You get the first response as it came.
        - ``1`` follows the stubs at the top level, so you get every top-level comment.
        - ``n`` also follows stubs down to reply level ``n``.
        - ``None`` follows every stub until the tree runs out.

        Stubs are read in bulk, a hundred ids a request. A wide thread still hands back fresh stubs
        as it goes, so ``budget`` caps what one read may spend. Once it runs out the stubs left are
        handed back as they are, the same as a stub past ``depth``, so you can see what was not
        followed.

        :param sort: Comment sort.
        :type sort: SORT
        :param limit: Most comments the first request returns, before any stub is followed.
        :type limit: t.Optional[int]
        :param depth: How far to follow ``load more`` stubs. See above.
        :type depth: t.Optional[int]
        :param budget: Most requests to spend following stubs, or None for no cap.
        :type budget: t.Optional[int]
        :returns: The comments, each with its nested replies.
        :rtype: Things[Comment]
        """

        params: t.Dict[str, t.Any] = {"sort": sort}
        if limit is not None:
            params["limit"] = limit
        payload = self.get(path=f"/comments/{self.id}.json", params=params)
        if payload is None:
            return Things()

        raw_children = payload[1].get("data", {}).get("children", [])
        expanded = self.follow_more_stubs(
            children=raw_children, sort=sort, depth=depth, level=0, budget=Budget(budget)
        )
        listing = Listing.from_response(payload={"data": {"children": expanded}})
        return Things(child for child in listing.children if isinstance(child, Comment))

    def follow_more_stubs(
            self,
            children: t.List[t.Dict[str, t.Any]],
            sort: SORT,
            depth: t.Optional[int],
            level: int,
            seen: t.Optional[t.Set[t.Tuple[t.Any, ...]]] = None,
            budget: t.Optional[Budget] = None,
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Walk a raw comment listing and follow ``load more`` stubs up to ``depth``.

        This works on Reddit's raw ``{kind, data}`` dicts so it can splice fetched comments back
        into the tree where their stub sat. A stub at a level below ``depth`` is fetched and its
        comments take its place. A stub at or past ``depth`` stays as it is.

        A fetched stub stands for siblings, not replies, so following one keeps the same ``level``.
        That means ``depth`` alone cannot end a run of stubs at one level, so each stub followed is
        remembered and never followed twice. A stub that resolves to itself is left in place on the
        second sighting instead of being chased again.

        The listing handed in is left as it was. A comment whose replies change is copied rather
        than written through, so the caller's payload still reads the way it arrived.

        :param children: The raw children of one listing.
        :type children: t.List[t.Dict[str, t.Any]]
        :param sort: Comment sort.
        :type sort: SORT
        :param depth: How far to follow stubs, or None for all the way.
        :type depth: t.Optional[int]
        :param level: The nesting level of these children. The top level is 0.
        :type level: int
        :param seen: Stubs already followed on this walk. Starts empty.
        :type seen: t.Optional[t.Set[t.Tuple[t.Any, ...]]]
        :param budget: What the walk may still spend. None lets it run as far as the tree goes.
        :type budget: t.Optional[Budget]
        :returns: The children with stubs followed where ``depth`` and ``budget`` allow.
        :rtype: t.List[t.Dict[str, t.Any]]
        """

        seen = set() if seen is None else seen
        budget = Budget(None) if budget is None else budget
        out: t.List[t.Dict[str, t.Any]] = []
        for child in children:
            kind = child.get("kind")
            if kind == "more":
                data = child.get("data", {})
                # What makes one stub distinct: a "continue this thread" stub carries no children
                # and a shared id, so the parent it points at is part of the identity.
                key = (data.get("name"), data.get("parent_id"), tuple(data.get("children") or ()))
                if (depth is None or level < depth) and key not in seen and not budget.is_spent():
                    seen.add(key)
                    fetched = self.fetch_more_comments(more_data=data, sort=sort, budget=budget)
                    out.extend(
                        self.follow_more_stubs(
                            children=fetched, sort=sort, depth=depth, level=level,
                            seen=seen, budget=budget,
                        )
                    )
                else:
                    out.append(child)
            elif kind == "t1":
                replies = child.get("data", {}).get("replies")
                if isinstance(replies, dict):
                    followed = self.follow_more_stubs(
                        children=replies.get("data", {}).get("children", []),
                        sort=sort,
                        depth=depth,
                        level=level + 1,
                        seen=seen,
                        budget=budget,
                    )
                    # Copy down to the one list that changed, so the caller's dicts stay put.
                    child = {
                        **child,
                        "data": {
                            **child["data"],
                            "replies": {
                                **replies,
                                "data": {**replies.get("data", {}), "children": followed},
                            },
                        },
                    }
                out.append(child)
            else:
                out.append(child)
        return out

    def fetch_more_comments(
            self,
            more_data: t.Dict[str, t.Any],
            sort: SORT,
            budget: t.Optional[Budget] = None,
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Fetch the raw comments behind one ``load more`` stub.

        The stub names the child ids it stands for. Those go to Reddit's bulk endpoint,
        ``MORE_CHILDREN_LIMIT`` at a time, so a stub naming thousands of ids costs one request per
        hundred rather than one per id. A "continue this thread" stub names no children, so this
        reads its ``parent_id`` on its own instead.

        The bulk endpoint answers with a flat list: a reply arrives beside its parent rather than
        inside it. :meth:`nest_flat_comments` puts it back before the result is handed on, so the
        tree here reads the same as one read a comment at a time.

        :param more_data: The stub's ``data`` body.
        :type more_data: t.Dict[str, t.Any]
        :param sort: Comment sort.
        :type sort: SORT
        :param budget: What the walk may still spend. Reads stop once it runs out, so a stub wider
            than the budget comes back part read rather than not at all.
        :type budget: t.Optional[Budget]
        :returns: The raw child dicts the stub stood for, nested.
        :rtype: t.List[t.Dict[str, t.Any]]
        """

        budget = Budget(None) if budget is None else budget
        ids = [child_id.split("_")[-1] for child_id in more_data.get("children") or []]
        if not ids:
            parent = more_data.get("parent_id")
            if not parent or budget.is_spent():
                return []
            budget.spend()
            payload = self.get(
                path=f"/comments/{self.id}/comment/{parent.split('_')[-1]}.json",
                params={"sort": sort, "context": 0},
            )
            if payload is None:
                return []
            return list(payload[1].get("data", {}).get("children", []))

        flat: t.List[t.Dict[str, t.Any]] = []
        for start in range(0, len(ids), MORE_CHILDREN_LIMIT):
            if budget.is_spent():
                break
            budget.spend()
            payload = self.get(
                path="/api/morechildren",
                params={
                    "link_id": f"t3_{self.id}",
                    "children": ",".join(ids[start:start + MORE_CHILDREN_LIMIT]),
                    "sort": sort,
                    "api_type": "json",
                },
            )
            # This endpoint reports trouble in the body with a 200, so raise_for_status sees none.
            if payload is None or payload.get("json", {}).get("errors"):
                continue
            flat.extend(payload.get("json", {}).get("data", {}).get("things", []))

        return self.nest_flat_comments(things=flat)

    @staticmethod
    def nest_flat_comments(things: t.List[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
        """
        Rebuild a comment tree from the flat list the bulk endpoint returns.

        Every thing carries a ``parent_id``. One whose parent is also in the list belongs inside
        that parent's ``replies``; the rest are the roots this stub stood for. Order is kept, so
        the sort Reddit applied survives.

        The things are fetched fresh and owned here, so they are nested in place.

        :param things: The flat ``{kind, data}`` things from one or more bulk reads.
        :type things: t.List[t.Dict[str, t.Any]]
        :returns: The roots, each with its replies nested inside it.
        :rtype: t.List[t.Dict[str, t.Any]]
        """

        by_id = {
            thing["data"]["id"]: thing
            for thing in things
            if thing.get("kind") == "t1" and thing.get("data", {}).get("id")
        }

        roots: t.List[t.Dict[str, t.Any]] = []
        for thing in things:
            parent = thing.get("data", {}).get("parent_id") or ""
            host = by_id.get(parent.split("_")[-1])
            if host is None or host is thing:
                roots.append(thing)
                continue

            replies = host["data"].get("replies")
            if not isinstance(replies, dict):
                replies = {"kind": "Listing", "data": {"children": []}}
                host["data"]["replies"] = replies
            replies.setdefault("data", {}).setdefault("children", []).append(thing)

        return roots


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
    ) -> Things[Post]:
        """
        Get posts from the multireddit.

        :param listing: Sort of the feed.
        :type listing: LISTINGS
        :param limit: Most posts to return, or None for all.
        :type limit: t.Optional[int]
        :param timeframe: Time window for ``top`` and ``controversial``.
        :type timeframe: TIME_FILTERS
        :returns: The posts.
        :rtype: Things[Post]
        """

        params = {"t": timeframe} if listing in ("top", "controversial") else None
        things = self.paginate(
            path=f"/user/{self.owner}/m/{self.name}/{listing}", limit=limit, params=params
        )
        return Things(thing for thing in things if isinstance(thing, Post))


class Search(Endpoint):
    """Search across Reddit. Reach it as :attr:`Reddit.search`."""

    def posts(
            self,
            query: str,
            sort: SORT = "relevance",
            timeframe: TIME_FILTERS = "all",
            limit: t.Optional[int] = PAGE_LIMIT,
            include_nsfw: bool = True,
    ) -> Things[Post]:
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
        :rtype: Things[Post]
        """

        params: t.Dict[str, t.Any] = {"q": query, "sort": sort, "t": timeframe}
        if include_nsfw:
            params["include_over_18"] = "on"
        things = self.paginate(path="/search", limit=limit, params=params)
        return Things(thing for thing in things if isinstance(thing, Post))

    def subreddits(
            self,
            query: str,
            limit: t.Optional[int] = PAGE_LIMIT,
    ) -> Things[Subreddit]:
        """
        Search subreddits by name and description.

        :param query: Search text.
        :type query: str
        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The matching subreddits.
        :rtype: Things[Subreddit]
        """

        things = self.paginate(path="/subreddits/search", limit=limit, params={"q": query})
        return Things(thing for thing in things if isinstance(thing, Subreddit))

    def users(
            self,
            query: str,
            limit: t.Optional[int] = PAGE_LIMIT,
    ) -> Things[User]:
        """
        Search users by name.

        :param query: Search text.
        :type query: str
        :param limit: Most users to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The matching users.
        :rtype: Things[User]
        """

        things = self.paginate(path="/users/search", limit=limit, params={"q": query})
        return Things(thing for thing in things if isinstance(thing, User))


class SubredditsFeed(Endpoint):
    """Bulk subreddit feeds. Reach it as :attr:`Reddit.subreddits`."""

    def popular(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[Subreddit]:
        """
        Get the popular subreddits feed.

        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The subreddits.
        :rtype: Things[Subreddit]
        """

        things = self.paginate(path="/subreddits/popular", limit=limit)
        return Things(thing for thing in things if isinstance(thing, Subreddit))

    def new(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[Subreddit]:
        """
        Get the new subreddits feed.

        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The subreddits.
        :rtype: Things[Subreddit]
        """

        things = self.paginate(path="/subreddits/new", limit=limit)
        return Things(thing for thing in things if isinstance(thing, Subreddit))

    def default(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[Subreddit]:
        """
        Get the default subreddits feed.

        :param limit: Most subreddits to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The subreddits.
        :rtype: Things[Subreddit]
        """

        things = self.paginate(path="/subreddits/default", limit=limit)
        return Things(thing for thing in things if isinstance(thing, Subreddit))


class UsersFeed(Endpoint):
    """Bulk user feeds. Reach it as :attr:`Reddit.users`."""

    def popular(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[User]:
        """
        Get the popular users feed.

        Each user carries only a name. Call :meth:`UserEndpoint.about` for the rest.

        :param limit: Most users to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The users.
        :rtype: Things[User]
        """

        things = self.paginate(path="/users/popular", limit=limit)
        return Things(
            User.from_profile_subreddit(data=thing.raw)
            for thing in things
            if isinstance(thing, Subreddit)
        )

    def new(self, limit: t.Optional[int] = PAGE_LIMIT) -> Things[User]:
        """
        Get the new users feed.

        Each user carries only a name. Call :meth:`UserEndpoint.about` for the rest.

        :param limit: Most users to return, or None for all.
        :type limit: t.Optional[int]
        :returns: The users.
        :rtype: Things[User]
        """

        things = self.paginate(path="/users/new", limit=limit)
        return Things(
            User.from_profile_subreddit(data=thing.raw)
            for thing in things
            if isinstance(thing, Subreddit)
        )


class Reddit:
    """
    The Reddit API, grouped by entity.

    Build one as a context manager so the session it owns is closed on exit, then reach an entity
    through its handle:

    .. code-block:: python

        with Reddit() as reddit:
            reddit.user("spez").about()
            reddit.subreddit("python").posts(listing="top", timeframe="week")
            reddit.search.posts("climate")

    A handle is cheap and runs no request. The read happens when you call a method on it.
    """

    def __init__(self, user_agent: t.Optional[str] = None):
        """
        Set up the API.

        :param user_agent: User agent to send. Falls back to ``KNEWKARMA_USER_AGENT``, then to a
            built-in one.
        :type user_agent: t.Optional[str]
        """

        self.__auth = RedditAuth(user_agent=user_agent)
        self.on_progress: t.Optional[t.Callable[[int, t.Optional[int]], None]] = None

    def close(self):
        """Close the session. See :meth:`RedditAuth.close`."""

        self.__auth.close()

    def __enter__(self) -> "Reddit":
        """
        Enter the context and return this instance.

        :returns: This instance.
        :rtype: Reddit
        """

        return self

    def __exit__(self, *exc_info: t.Any):
        """Leave the context and close the session."""

        self.close()

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
    def on_status(self, callback: t.Optional[t.Callable[[str], None]]):
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
