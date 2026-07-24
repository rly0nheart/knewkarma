"""
Anonymous Reddit auth.

:class:`RedditAuth` mints an app-only token with Reddit's ``installed_client`` grant and hands out
a valid bearer token for reads over ``oauth.reddit.com``. It needs no account and no client secret.
The default client id and user agent come from the RedReader app, whose anonymous flow this follows.
The reads themselves live in :mod:`api`; this class only owns the session and the token.
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


class RedditAuth:
    """Owns the session and hands out a valid anonymous bearer token."""

    def __init__(
            self,
            user_agent: t.Optional[str] = None,
            session: t.Optional[requests.Session] = None,
    ):
        """
        Set up the auth.

        :param user_agent: User agent to send. Falls back to ``KNEWKARMA_USER_AGENT``, then to
            RedReader's user agent.
        :type user_agent: t.Optional[str]
        :param session: An existing requests session to reuse.
        :type session: t.Optional[requests.Session]
        """

        self.__user_agent = (
                user_agent or os.getenv("KNEWKARMA_USER_AGENT") or "org.quantumbadger.redreader/1.25.2"
        )
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = self.__user_agent
        self.__token: t.Optional[str] = None
        self.__token_expiry: float = 0.0
        self.on_status: t.Optional[t.Callable[[str], None]] = None

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
