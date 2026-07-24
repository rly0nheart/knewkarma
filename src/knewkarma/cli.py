"""
Command line for Knew Karma.

Built on argparse. Each subcommand calls a :class:`Reddit` handle, shows the result in a
table through a pager, and can export it to json or csv.
"""

import argparse
import typing as t
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import LISTINGS, SORT, TIME_FILTERS, Reddit, export, output
from .core.models import RedditObject
from .meta.about import Project
from .meta.license import License
from .meta.version import Version

EXPORT_DIR = "exports"

reddit = Reddit()


def _add_output(sub: argparse.ArgumentParser):
    """
    Add export options to a subcommand.

    :param sub: The subcommand parser.
    :type sub: argparse.ArgumentParser
    """

    sub.add_argument(
        "-e",
        "--export",
        default="",
        help="comma-separated formats to export: json,csv",
    )


def _add_limit(sub: argparse.ArgumentParser):
    """Add a result limit option to a subcommand."""

    sub.add_argument("-l", "--limit", type=int, default=100, help="maximum results")


def _add_sort(sub: argparse.ArgumentParser):
    """Add a Reddit search/comment sort option to a subcommand."""

    sub.add_argument(
        "-s", "--sort", choices=t.get_args(SORT), default="relevance", help="sort order"
    )


def _add_comment_sort(sub: argparse.ArgumentParser, default: str):
    """Add a Reddit comment sort option to a subcommand."""

    sub.add_argument("-s", "--sort", choices=t.get_args(SORT), default=default, help="sort order")


def _add_timeframe(sub: argparse.ArgumentParser):
    """Add a Reddit timeframe option to a subcommand."""

    sub.add_argument(
        "-t",
        "--timeframe",
        choices=t.get_args(TIME_FILTERS),
        default="all",
        help="time window for top and controversial",
    )


def _add_listing(sub: argparse.ArgumentParser):
    """Add a Reddit listing option to a subcommand."""

    sub.add_argument(
        "--listing",
        choices=t.get_args(LISTINGS),
        default="hot",
        help="listing sort for feeds",
    )


def _add_feed_options(sub: argparse.ArgumentParser):
    """Add options used by feed-style commands."""

    _add_limit(sub)
    _add_listing(sub)
    _add_timeframe(sub)
    _add_output(sub)


def _add_search_options(sub: argparse.ArgumentParser):
    """Add options used by search commands."""

    _add_limit(sub)
    _add_sort(sub)
    _add_timeframe(sub)
    _add_output(sub)


def execute(
        thunk: t.Callable[[], t.Union[RedditObject, t.Sequence[RedditObject], t.Sequence[str], None]],
        command: str,
        label: str,
        export_formats: str,
        status_msg: str,
):
    """
    Run one command: fetch the data, show it, then export it when asked.

    :param thunk: The function that fetches the data.
    :type thunk: t.Union[RedditObject, t.Sequence[RedditObject], t.Sequence[str], None]
    :param command: The subcommand name. Goes into the export filename.
    :type command: str
    :param label: A short label. Goes into the export filename.
    :type label: str
    :param export_formats: Comma-separated formats, or ``""`` for none.
    :type export_formats: str
    :param status_msg: The message to show while the fetch runs.
    :type status_msg: str
    """

    with output.console.status(f"[dim]{status_msg}[/]…") as status:
        def progress(count: int, target: t.Optional[int]):
            tally = f"{count}/{target}" if target else str(count)
            status.update(f"[dim]{status_msg}[/]… [{tally}]")

        reddit.on_progress = progress
        reddit.on_status = status.update
        try:
            data = thunk()
        finally:
            reddit.on_progress = None
            reddit.on_status = None

    output.show(data)

    formats = [fmt.strip() for fmt in export_formats.split(",") if fmt.strip()]
    if not formats or not data:
        return

    rows = data if isinstance(data, list) else [data]
    Path(EXPORT_DIR).mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = str(Path(EXPORT_DIR) / f"{command}-{label}-{stamp}")
    with output.console.status(f"[dim]Exporting {command} {label}[/]…"):
        written = export.write(rows, base, formats)
    for path in written:
        output.console.print(f"Wrote {path}")


def _cmd_post(args: argparse.Namespace):
    """Handle the ``post`` command."""

    execute(
        thunk=lambda: reddit.post(args.id).about(),
        command="post",
        label=args.id,
        export_formats=args.export,
        status_msg=f"Getting post {args.id}",
    )


def _cmd_post_comments(args: argparse.Namespace):
    """Handle the ``post ID comments`` command."""

    execute(
        thunk=lambda: reddit.post(args.id).comments(sort=args.sort, limit=args.limit, depth=args.depth),
        command="post",
        label=f"{args.id}-comments",
        export_formats=args.export,
        status_msg=f"Getting comments for post {args.id}",
    )


def _cmd_feed(args: argparse.Namespace):
    """Handle the ``feed`` command."""

    execute(
        thunk=lambda: reddit.subreddit("").posts(
            listing=args.listing, limit=args.limit, timeframe=args.timeframe
        ),
        command="feed",
        label=args.listing,
        export_formats=args.export,
        status_msg=f"Getting {args.listing} feed",
    )


def _cmd_subreddit(args: argparse.Namespace):
    """Handle the ``subreddit NAME`` profile command."""

    execute(
        thunk=lambda: reddit.subreddit(args.name).about(),
        command="subreddit",
        label=f"{args.name}-profile",
        export_formats=args.export,
        status_msg=f"Getting r/{args.name} profile",
    )


def _cmd_subreddit_posts(args: argparse.Namespace):
    """Handle the ``subreddit NAME posts`` command."""

    execute(
        thunk=lambda: reddit.subreddit(args.name).posts(
            listing=args.listing, limit=args.limit, timeframe=args.timeframe
        ),
        command="subreddit",
        label=f"{args.name}-posts",
        export_formats=args.export,
        status_msg=f"Getting {args.limit} posts from r/{args.name}",
    )


def _cmd_subreddit_comments(args: argparse.Namespace):
    """Handle the ``subreddit NAME comments`` command."""

    execute(
        thunk=lambda: reddit.subreddit(args.name).comments(limit=args.limit),
        command="subreddit",
        label=f"{args.name}-comments",
        export_formats=args.export,
        status_msg=f"Getting comments from r/{args.name}",
    )


def _cmd_subreddit_search(args: argparse.Namespace):
    """Handle the ``subreddit NAME search QUERY`` command."""

    execute(
        thunk=lambda: reddit.subreddit(args.name).search(
            args.query,
            sort=args.sort,
            timeframe=args.timeframe,
            limit=args.limit,
        ),
        command="subreddit",
        label=f"{args.name}-search",
        export_formats=args.export,
        status_msg=f"Searching r/{args.name} for '{args.query}'",
    )


def _cmd_subreddit_wiki_pages(args: argparse.Namespace):
    """Handle the ``subreddit NAME wiki-pages`` command."""

    execute(thunk=lambda: reddit.subreddit(args.name).wiki_pages(), command="subreddit", label="subreddit-wiki-pages",
            export_formats=args.export, status_msg=f"Getting wiki pages for r/{args.name}")


def _cmd_subreddits(args: argparse.Namespace):
    """Handle the ``subreddits`` command."""

    kind = args.which
    execute(
        thunk=lambda: getattr(reddit.subreddits, kind)(limit=args.limit),
        command="subreddits",
        label=kind,
        export_formats=args.export,
        status_msg=f"Getting {kind} subreddits",
    )


def _cmd_user(args: argparse.Namespace):
    """Handle the ``user NAME`` profile command."""

    execute(
        thunk=lambda: reddit.user(args.username).about(),
        command="user",
        label=f"{args.username}-profile",
        export_formats=args.export,
        status_msg=f"Getting u/{args.username} profile",
    )


def _cmd_user_posts(args: argparse.Namespace):
    """Handle the ``user NAME posts`` command."""

    execute(
        thunk=lambda: reddit.user(args.username).posts(
            listing=args.listing, limit=args.limit, timeframe=args.timeframe
        ),
        command="user",
        label=f"{args.username}-posts",
        export_formats=args.export,
        status_msg=f"Getting {args.limit} posts from u/{args.username}",
    )


def _cmd_user_comments(args: argparse.Namespace):
    """Handle the ``user NAME comments`` command."""

    execute(
        thunk=lambda: reddit.user(args.username).comments(limit=args.limit, sort=args.sort),
        command="user",
        label=f"{args.username}-comments",
        export_formats=args.export,
        status_msg=f"Getting comments from u/{args.username}",
    )


def _cmd_user_overview(args: argparse.Namespace):
    """Handle the ``user NAME overview`` command."""

    execute(
        thunk=lambda: reddit.user(args.username).overview(limit=args.limit),
        command="user",
        label=f"{args.username}-overview",
        export_formats=args.export,
        status_msg=f"Getting overview for u/{args.username}",
    )


def _cmd_user_moderated(args: argparse.Namespace):
    """Handle the ``user NAME moderated`` command."""

    execute(
        thunk=lambda: reddit.user(args.name).moderated(),
        command="user",
        label=f"{args.name}-moderated",
        export_formats=args.export,
        status_msg=f"Getting subreddits moderated by u/{args.name}",
    )


def _cmd_user_trophies(args: argparse.Namespace):
    """Handle the ``user NAME trophies`` command."""

    execute(
        thunk=lambda: reddit.user(args.name).trophies(),
        command="user",
        label=f"{args.name}-trophies",
        export_formats=args.export,
        status_msg=f"Getting trophies for u/{args.name}",
    )


def _cmd_users(args: argparse.Namespace):
    """Handle the ``users`` command."""

    kind = args.which
    execute(
        thunk=lambda: getattr(reddit.users, kind)(limit=args.limit),
        command="users",
        label=kind,
        export_formats=args.export,
        status_msg=f"Getting {kind} users",
    )


def _cmd_search(args: argparse.Namespace):
    """Handle the ``search`` command."""

    if args.kind == "subreddits":
        execute(
            thunk=lambda: reddit.search.subreddits(args.query, limit=args.limit),
            command="search",
            label="subreddits",
            export_formats=args.export,
            status_msg=f"Searching subreddits for '{args.query}'",
        )
    elif args.kind == "users":
        execute(
            thunk=lambda: reddit.search.users(args.query, limit=args.limit),
            command="search",
            label="users",
            export_formats=args.export,
            status_msg=f"Searching users for '{args.query}'",
        )
    else:
        execute(
            thunk=lambda: reddit.search.posts(
                args.query, sort=args.sort, timeframe=args.timeframe, limit=args.limit
            ),
            command="search",
            label="posts",
            export_formats=args.export,
            status_msg=f"Searching posts for '{args.query}'",
        )


def _cmd_license(args: argparse.Namespace):
    """Handle the ``license`` conditions command."""

    output.console.print(License.conditions)


def _cmd_license_warranty(args: argparse.Namespace):
    """Handle the ``license warranty`` command."""

    output.console.print(License.warranty)


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser.

    :returns: The parser.
    :rtype: argparse.ArgumentParser
    """

    parser = argparse.ArgumentParser(prog="knewkarma", description=Project.summary)
    parser.add_argument("-v", "--version", action="version", version=Version.full_version)
    subparsers = parser.add_subparsers(dest="command", required=True)

    post = subparsers.add_parser("post", help="a single post and its comments")
    post.add_argument("id", help="the post id")
    _add_output(post)
    post.set_defaults(func=_cmd_post)
    post_actions = post.add_subparsers(dest="post_action")
    post_comments = post_actions.add_parser("comments", help="get comments for the post")
    _add_limit(post_comments)
    _add_comment_sort(post_comments, "top")
    post_comments.add_argument(
        "-d",
        "--depth",
        type=int,
        default=1,
        help="how deep to load comments: 0 first batch only, 1 all top-level comments, "
             "higher also loads nested replies",
    )
    _add_output(post_comments)
    post_comments.set_defaults(func=_cmd_post_comments)

    feed = subparsers.add_parser("feed", help="front-page post feeds")
    feed.add_argument(
        "listing",
        nargs="?",
        choices=("hot", "new", "top", "rising", "controversial"),
        default="hot",
        help="front-page listing to read",
    )
    _add_limit(feed)
    _add_timeframe(feed)
    _add_output(feed)
    feed.set_defaults(func=_cmd_feed)

    subreddit = subparsers.add_parser("subreddit", help="data from one subreddit")
    subreddit.add_argument("name", help="the subreddit name")
    _add_output(subreddit)
    subreddit.set_defaults(func=_cmd_subreddit)
    subreddit_actions = subreddit.add_subparsers(dest="subreddit_action")

    subreddit_profile = subreddit_actions.add_parser("profile", help="get the subreddit profile")
    _add_output(subreddit_profile)
    subreddit_profile.set_defaults(func=_cmd_subreddit)

    subreddit_posts = subreddit_actions.add_parser("posts", help="get posts from the subreddit")
    _add_feed_options(subreddit_posts)
    subreddit_posts.set_defaults(func=_cmd_subreddit_posts)

    subreddit_comments = subreddit_actions.add_parser(
        "comments", help="get recent comments from the subreddit"
    )
    _add_limit(subreddit_comments)
    _add_output(subreddit_comments)
    subreddit_comments.set_defaults(func=_cmd_subreddit_comments)

    subreddit_search = subreddit_actions.add_parser(
        "search", help="search posts inside the subreddit"
    )
    subreddit_search.add_argument("query", help="the search text")
    _add_search_options(subreddit_search)
    subreddit_search.set_defaults(func=_cmd_subreddit_search)

    subreddit_wiki_pages = subreddit_actions.add_parser(
        "wiki-pages", help="list wiki pages in the subreddit"
    )
    subreddit_wiki_pages.set_defaults(func=_cmd_subreddit_wiki_pages)

    subreddits = subparsers.add_parser("subreddits", help="bulk subreddit feeds")
    subreddits.add_argument(
        "which",
        nargs="?",
        choices=("default", "new", "popular"),
        default="popular",
        help="which subreddit feed to read",
    )
    _add_limit(subreddits)
    _add_output(subreddits)
    subreddits.set_defaults(func=_cmd_subreddits)

    user = subparsers.add_parser("user", help="data about one user")
    user.add_argument("username", help="the user's name")
    _add_output(user)
    user.set_defaults(func=_cmd_user)
    user_actions = user.add_subparsers(dest="user_action")

    user_profile = user_actions.add_parser("profile", help="get the user profile")
    _add_output(user_profile)
    user_profile.set_defaults(func=_cmd_user)

    user_posts = user_actions.add_parser("posts", help="get posts submitted by the user")
    _add_feed_options(user_posts)
    user_posts.set_defaults(func=_cmd_user_posts)

    user_comments = user_actions.add_parser("comments", help="get comments by the user")
    _add_limit(user_comments)
    _add_comment_sort(user_comments, "new")
    _add_output(user_comments)
    user_comments.set_defaults(func=_cmd_user_comments)

    user_overview = user_actions.add_parser("overview", help="get posts and comments by the user")
    _add_limit(user_overview)
    _add_output(user_overview)
    user_overview.set_defaults(func=_cmd_user_overview)

    user_moderated = user_actions.add_parser("moderated", help="get moderated subreddits")
    _add_output(user_moderated)
    user_moderated.set_defaults(func=_cmd_user_moderated)

    user_trophies = user_actions.add_parser("trophies", help="get user trophies")
    _add_output(user_trophies)
    user_trophies.set_defaults(func=_cmd_user_trophies)

    users = subparsers.add_parser("users", help="bulk user feeds")
    users.add_argument(
        "which",
        nargs="?",
        choices=("new", "popular"),
        default="popular",
        help="which user feed to read",
    )
    _add_limit(users)
    _add_output(users)
    users.set_defaults(func=_cmd_users)

    search = subparsers.add_parser("search", help="search posts, subreddits, or users")
    search_actions = search.add_subparsers(dest="kind", required=True)

    search_posts = search_actions.add_parser("posts", help="search posts")
    search_posts.add_argument("query", help="the search text")
    _add_search_options(search_posts)
    search_posts.set_defaults(func=_cmd_search)

    search_subreddits = search_actions.add_parser("subreddits", help="search subreddits")
    search_subreddits.add_argument("query", help="the search text")
    _add_limit(search_subreddits)
    _add_output(search_subreddits)
    search_subreddits.set_defaults(func=_cmd_search)

    search_users = search_actions.add_parser("users", help="search users")
    search_users.add_argument("query", help="the search text")
    _add_limit(search_users)
    _add_output(search_users)
    search_users.set_defaults(func=_cmd_search)

    lic = subparsers.add_parser("license", help="show the license")
    license_actions = lic.add_subparsers(dest="license_action", required=True)

    conditions = license_actions.add_parser("conditions", help="show the conditions")
    conditions.set_defaults(func=_cmd_license)

    warranty = license_actions.add_parser("warranty", help="show the warranty")
    warranty.set_defaults(func=_cmd_license_warranty)

    return parser


def _report_status():
    """Check Reddit's status page and print a line about it."""

    try:
        with output.console.status("[dim]Checking Reddit status[/]…"):
            status = reddit.status()
    except requests.RequestException:
        output.console.print("[yellow]Could not reach Reddit's status page.[/]")
        return

    indicator = status.get("indicator", "unknown")
    description = status.get("description", "Unknown")
    if indicator == "none":
        output.console.print(f"[green]{description}[/]")
    else:
        output.console.print(f"[yellow]{indicator}: {description}[/]")


def main(argv: t.Optional[t.Sequence[str]] = None):
    """
    Run the command line.

    Catches a Ctrl-C and any error so the program ends with a clear line rather than a traceback,
    then reports how long it ran. A plain ``--help`` or ``--version`` exits before that line.

    :param argv: Arguments to parse. Defaults to ``sys.argv``.
    :type argv: t.Optional[t.Sequence[str]]
    """

    start = datetime.now(timezone.utc)
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        if args.command != "license":
            _report_status()
        args.func(args)
    except KeyboardInterrupt:
        output.console.print("\n[yellow]User interruption detected[/]")
    except Exception as e:
        output.console.print(f"An error occurred: [red]{e}[/]")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    output.console.print(f"[dim]Finished in {elapsed:.2f}s[/]")


if __name__ == "__main__":
    main()
