"""
Anonymous Reddit auth.

:class:`RedditAuth` mints an app-only token with Reddit's ``installed_client`` grant and hands out
a valid bearer token for reads over ``oauth.reddit.com``. It needs no account and no client secret.
The default client id and user agent come from the RedReader app, whose anonymous flow this follows.
The reads themselves live in :mod:`api`; this class owns the session, the token, and the pacing
that :class:`RateLimit` sets from Reddit's rate limit headers.
"""

import json
import os
import time
import typing as t
from pathlib import Path

import requests

_TOKEN_MARGIN = 60  # Refresh this many seconds before expiry.
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "knewkarma"
_TOKEN_CACHE = _CACHE_DIR / "token.json"

_WINDOW = 600  # Reddit's rate limit window, in seconds.
_MAX_SPACING = 10  # Longest a request waits to spread itself over the window.
_RETRY_AFTER = 5  # Seconds to wait after a 429 that names no delay.


class RateLimit:
    """Spreads requests over Reddit's rate limit window, from the headers it sends back."""

    def __init__(self):
        """Start with no reading. The first response fills one in."""

        self.remaining: t.Optional[float] = None
        self.used: float = 0.0
        self.__next_request: float = 0.0

    def wait(self):
        """Sleep until the next request is due."""

        nap = self.__next_request - time.monotonic()
        if nap > 0:
            time.sleep(nap)

    def update(self, headers: t.Mapping[str, str]):
        """
        Read the rate limit headers and work out when the next request is due.

        :param headers: The response headers.
        :type headers: t.Mapping[str, str]
        """

        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if remaining is None or reset is None:
            if self.remaining is not None:  # no headers, so count the request off ourselves
                self.remaining -= 1
                self.used += 1
            return

        self.remaining = left = float(remaining)
        self.used = float(headers.get("x-ratelimit-used") or 0)
        to_reset = float(reset)
        now = time.monotonic()

        if left <= 0:
            self.__next_request = now + to_reset
            return

        # Wait out the gap between the time left at an even pace and the time really left.
        share = left + self.used
        on_pace = _WINDOW - _WINDOW / share * self.used if share else 0.0
        self.__next_request = now + min(to_reset, max(to_reset - on_pace, 0.0), _MAX_SPACING)

    @staticmethod
    def pause(headers: t.Mapping[str, str]) -> float:
        """
        Say how long to wait after a 429, from ``retry-after`` or the reset header.

        :param headers: The response headers.
        :type headers: t.Mapping[str, str]
        :returns: The seconds to wait.
        :rtype: float
        """

        delay = headers.get("retry-after") or headers.get("x-ratelimit-reset") or ""
        try:
            return max(float(delay), 0.0)
        except ValueError:
            return float(_RETRY_AFTER)


class RedditAuth:
    """Owns the session and hands out a valid anonymous bearer token."""

    def __init__(self, user_agent: t.Optional[str] = None):
        """
        Set up the auth.

        :param user_agent: User agent to send. Falls back to ``KNEWKARMA_USER_AGENT``, then to
            RedReader's user agent.
        :type user_agent: t.Optional[str]
        """

        self.__user_agent = (
                user_agent or os.getenv("KNEWKARMA_USER_AGENT") or "org.quantumbadger.redreader/1.25.2"
        )
        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.__user_agent
        self.rate_limit = RateLimit()
        self.__token: str = ""
        self.__token_expiry: float = 0.0
        self.on_status: t.Optional[t.Callable[[str], None]] = None

    def close(self):
        """Close the session."""

        self.session.close()

    def __enter__(self) -> "RedditAuth":
        """
        Enter the context and return this auth.

        :returns: This auth.
        :rtype: RedditAuth
        """

        return self

    def __exit__(self, *exc_info: t.Any):
        """Leave the context and close the session."""

        self.close()

    @staticmethod
    def __is_still_fresh(expiry: float) -> bool:
        """
        Report whether a token expiry is still ahead of us, with a safety margin.

        :param expiry: The token's expiry, in Unix seconds.
        :type expiry: float
        :returns: True when the token is still good to use.
        :rtype: bool
        """

        return time.time() < expiry - _TOKEN_MARGIN

    @staticmethod
    def __load_cached_token() -> t.Optional[t.Tuple[str, float]]:
        """
        Read the token from disk.

        :returns: The token and its expiry, or None when there is no readable cache.
        :rtype: t.Optional[t.Tuple[str, float]]
        """

        try:
            cached = json.loads(_TOKEN_CACHE.read_text())
            return cached["access_token"], float(cached["expires_at"])
        except (OSError, ValueError, KeyError):
            return None

    @staticmethod
    def __save_cached_token(token: str, expiry: float):
        """
        Write the token to disk.

        :param token: The bearer token.
        :type token: str
        :param expiry: The token's expiry, in Unix seconds.
        :type expiry: float
        """

        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _TOKEN_CACHE.write_text(json.dumps({"access_token": token, "expires_at": expiry}))
            _TOKEN_CACHE.chmod(0o600)
        except OSError:
            pass

    def mint_token(self) -> str:
        """
        Mint a fresh anonymous token, then cache it in memory and on disk.

        :returns: The bearer token.
        :rtype: str
        :raises requests.HTTPError: When the token request fails.
        """

        if self.on_status:
            self.on_status("Authenticating with Reddit...")

        response = self.session.post(
            url="https://www.reddit.com/api/v1/access_token",
            auth=("yH0aTnJEt6qUgGn835B4vg", ""),
            data={
                "grant_type": "https://oauth.reddit.com/grants/installed_client",
                "device_id": "DO_NOT_TRACK_THIS_DEVICE",
            },
            headers={"User-Agent": self.__user_agent},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self.__token = payload["access_token"]
        self.__token_expiry = time.time() + payload.get("expires_in", 3600)
        self.__save_cached_token(str(self.__token), self.__token_expiry)
        return str(self.__token)

    def get_bearer_token(self) -> str:
        """
        Return a valid bearer token.

        It reuses the in-memory token, then the disk cache, and mints a fresh one only when both
        are stale.

        :returns: The bearer token.
        :rtype: str
        """

        if self.__token and self.__is_still_fresh(self.__token_expiry):
            return self.__token

        cached = self.__load_cached_token()
        if cached and self.__is_still_fresh(cached[1]):
            self.__token, self.__token_expiry = cached
            return self.__token

        return self.mint_token()
