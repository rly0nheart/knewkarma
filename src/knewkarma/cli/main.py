"""
Command line for Knew Karma.

Built on argparse. Each subcommand calls a :class:`Reddit` handle, shows the result in a
table through a pager, and can export it to json or csv.
"""

import argparse
import sys
import typing as t
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.pretty import Pretty

from .. import KINDS, LISTINGS, SORT, TIME_FILTERS, Reddit
from ..core.api import SubredditEndpoint, UserEndpoint
from ..core.models import RedditObject, Things
from ..meta.about import Project
from ..meta.license import License
from ..meta.version import Version

EXPORT_DIR = "exports"
console = Console(log_time=False)
# What a command hands back: one model, a row of models or wiki page names, or nothing.
Result = t.Union[RedditObject, Things, None]


def __pretty_print(items: Result):
    """
    Show a result.

    A list of models pages through the pager, so the user scrolls through bulk results. A single
    model pretty-prints its fields, with no pager. An empty result prints a short note.

    :param items: A single model, a list of models, a list of wiki page names, or None.
    :type items: Result
    """

    if not isinstance(items, (list, tuple)):
        if items is None:
            console.log("No results.")
        else:
            console.print(Pretty(items))
        return

    rows = list(items)
    if not rows:
        console.log("No results.")
        return

    with console.pager(styles=True):
        for index, row in enumerate(rows):
            if index:
                console.print()
            console.print(Pretty(row))


def __add_output(sub: argparse.ArgumentParser):
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


def __add_limit(sub: argparse.ArgumentParser):
    """Add a result limit option to a subcommand."""

    sub.add_argument("-l", "--limit", type=int, default=100, help="maximum results")


def __add_sort(sub: argparse.ArgumentParser):
    """Add a Reddit search/comment sort option to a subcommand."""

    sub.add_argument(
        "-s", "--sort", choices=t.get_args(SORT), default="relevance", help="sort order"
    )


def __add_comment_sort(sub: argparse.ArgumentParser, default: str):
    """Add a Reddit comment sort option to a subcommand."""

    sub.add_argument("-s", "--sort", choices=t.get_args(SORT), default=default, help="sort order")


def __add_timeframe(sub: argparse.ArgumentParser):
    """Add a Reddit timeframe option to a subcommand."""

    sub.add_argument(
        "-t",
        "--timeframe",
        choices=t.get_args(TIME_FILTERS),
        default="all",
        help="time window for top and controversial",
    )


def __add_listing(sub: argparse.ArgumentParser):
    """Add a Reddit listing option to a subcommand."""

    sub.add_argument(
        "--listing",
        choices=t.get_args(LISTINGS),
        default="hot",
        help="listing sort for feeds",
    )


def __add_feed_options(sub: argparse.ArgumentParser):
    """Add options used by feed-style commands."""

    __add_limit(sub)
    __add_listing(sub)
    __add_timeframe(sub)
    __add_output(sub)


def __add_search_options(sub: argparse.ArgumentParser):
    """Add options used by search commands."""

    __add_limit(sub)
    __add_sort(sub)
    __add_timeframe(sub)
    __add_output(sub)


def __run_command(
        reddit: Reddit,
        thunk: t.Callable[[], Result],
        command: str,
        label: str,
        export_formats: str,
        status_msg: str,
):
    """
    Run one command: fetch the data, show it, then export it when asked.

    :param reddit: The Reddit handle to read through.
    :type reddit: Reddit
    :param thunk: The function that fetches the data.
    :type thunk: t.Callable[[], Result]
    :param command: The subcommand name. Goes into the export filename.
    :type command: str
    :param label: A short label. Goes into the export filename.
    :type label: str
    :param export_formats: Comma-separated formats, or ``""`` for none.
    :type export_formats: str
    :param status_msg: The message to show while the fetch runs.
    :type status_msg: str
    """

    with console.status(f"[dim]{status_msg}[/]…") as status:
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

    __pretty_print(items=data)

    formats = [fmt.strip() for fmt in export_formats.split(",") if fmt.strip()]
    if not formats or not data:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = Path(EXPORT_DIR) / f"{command}-{label}-{stamp}"
    written: t.List[str] = []
    with console.status(f"[dim]Exporting {command} {label}[/]…"):
        for fmt in formats:
            if fmt == "json":
                written.append(data.to_json(f"{base}.json"))
            elif fmt == "csv":
                written.append(data.to_csv(f"{base}.csv"))

    for path in written:
        console.log(f"Wrote {path}")


def __cmd_post(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``post`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.post(args.id).about(),
        command="post",
        label=args.id,
        export_formats=args.export,
        status_msg=f"Getting post {args.id}",
    )


def __cmd_post_comments(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``post ID comments`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.post(args.id).comments(sort=args.sort, limit=args.limit, depth=args.depth),
        command="post",
        label=f"{args.id}-comments",
        export_formats=args.export,
        status_msg=f"Getting comments for post {args.id}",
    )


def __cmd_feed(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``feed`` command."""

    if args.stream:
        __stream(reddit=reddit, name="")
        return

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.subreddit("").posts(
            listing=args.listing, limit=args.limit, timeframe=args.timeframe
        ),
        command="feed",
        label=args.listing,
        export_formats=args.export,
        status_msg=f"Getting {args.listing} feed",
    )


def __cmd_subreddit(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``subreddit NAME`` profile command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.subreddit(args.name).about(),
        command="subreddit",
        label=f"{args.name}-profile",
        export_formats=args.export,
        status_msg=f"Getting r/{args.name} profile",
    )


def __stream(reddit: Reddit, name: str, kind: KINDS = "posts"):
    """
    Handle the ``--stream`` option on the ``posts``, ``comments``, and ``feed`` commands.

    :param reddit: The Reddit handle to read through.
    :type reddit: Reddit
    :param name: The subreddit name, or ``""`` for the front page.
    :type name: str
    :param kind: Whether to stream posts or comments.
    :type kind: KINDS
    """

    source = f"r/{name}" if name else "the front page"
    console.log(f"Streaming new {kind} from {source}. Press [yellow]Ctrl+C[/] to stop.")
    with console.status(f"[dim]Waiting for {kind}[/]…") as status:
        def waiting(seconds: float):
            status.update(
                f"[dim]Waiting for {kind}[/]… [italic]checking again in[/] {seconds:.0f}s"
            )

        for thing in reddit.subreddit(name).stream(kind=kind, skip_existing=True, on_wait=waiting):
            console.print()
            __pretty_print(items=thing)


def __cmd_subreddit_posts(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``subreddit NAME posts`` command."""

    if args.stream:
        __stream(reddit=reddit, name=args.name)
        return

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.subreddit(args.name).posts(
            listing=args.listing, limit=args.limit, timeframe=args.timeframe
        ),
        command="subreddit",
        label=f"{args.name}-posts",
        export_formats=args.export,
        status_msg=f"Getting {args.limit} posts from r/{args.name}",
    )


def __cmd_subreddit_comments(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``subreddit NAME comments`` command."""

    if args.stream:
        __stream(reddit=reddit, name=args.name, kind="comments")
        return

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.subreddit(args.name).comments(limit=args.limit),
        command="subreddit",
        label=f"{args.name}-comments",
        export_formats=args.export,
        status_msg=f"Getting comments from r/{args.name}",
    )


def __cmd_subreddit_search(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``subreddit NAME search QUERY`` command."""

    __run_command(
        reddit=reddit,
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


def __cmd_subreddit_wiki_pages(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``subreddit NAME wiki-pages`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.subreddit(args.name).wiki_pages(),
        command="subreddit",
        label=f"{args.name}-wiki-pages",
        export_formats=args.export,
        status_msg=f"Getting wiki pages for r/{args.name}",
    )


def __cmd_subreddits(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``subreddits`` command."""

    kind = args.which
    __run_command(
        reddit=reddit,
        thunk=lambda: getattr(reddit.subreddits, kind)(limit=args.limit),
        command="subreddits",
        label=kind,
        export_formats=args.export,
        status_msg=f"Getting {kind} subreddits",
    )


def __cmd_user(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``user NAME`` profile command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.user(args.username).about(),
        command="user",
        label=f"{args.username}-profile",
        export_formats=args.export,
        status_msg=f"Getting u/{args.username} profile",
    )


def __cmd_user_posts(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``user NAME posts`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.user(args.username).posts(
            listing=args.listing, limit=args.limit, timeframe=args.timeframe
        ),
        command="user",
        label=f"{args.username}-posts",
        export_formats=args.export,
        status_msg=f"Getting {args.limit} posts from u/{args.username}",
    )


def __cmd_user_comments(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``user NAME comments`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.user(args.username).comments(limit=args.limit, sort=args.sort),
        command="user",
        label=f"{args.username}-comments",
        export_formats=args.export,
        status_msg=f"Getting comments from u/{args.username}",
    )


def __cmd_user_overview(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``user NAME overview`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.user(args.username).overview(limit=args.limit),
        command="user",
        label=f"{args.username}-overview",
        export_formats=args.export,
        status_msg=f"Getting overview for u/{args.username}",
    )


def __cmd_user_moderated(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``user NAME moderated`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.user(args.username).moderated(),
        command="user",
        label=f"{args.username}-moderated",
        export_formats=args.export,
        status_msg=f"Getting subreddits moderated by u/{args.username}",
    )


def __cmd_user_trophies(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``user NAME trophies`` command."""

    __run_command(
        reddit=reddit,
        thunk=lambda: reddit.user(args.username).trophies(),
        command="user",
        label=f"{args.username}-trophies",
        export_formats=args.export,
        status_msg=f"Getting trophies for u/{args.username}",
    )


def __cmd_users(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``users`` command."""

    kind = args.which
    __run_command(
        reddit=reddit,
        thunk=lambda: getattr(reddit.users, kind)(limit=args.limit),
        command="users",
        label=kind,
        export_formats=args.export,
        status_msg=f"Getting {kind} users",
    )


def __cmd_search(args: argparse.Namespace, reddit: Reddit):
    """Handle the ``search`` command."""

    if args.kind == "subreddits":
        __run_command(
            reddit=reddit,
            thunk=lambda: reddit.search.subreddits(args.query, limit=args.limit),
            command="search",
            label="subreddits",
            export_formats=args.export,
            status_msg=f"Searching subreddits for '{args.query}'",
        )
    elif args.kind == "users":
        __run_command(
            reddit=reddit,
            thunk=lambda: reddit.search.users(args.query, limit=args.limit),
            command="search",
            label="users",
            export_formats=args.export,
            status_msg=f"Searching users for '{args.query}'",
        )
    else:
        __run_command(
            reddit=reddit,
            thunk=lambda: reddit.search.posts(
                args.query, sort=args.sort, timeframe=args.timeframe, limit=args.limit
            ),
            command="search",
            label="posts",
            export_formats=args.export,
            status_msg=f"Searching posts for '{args.query}'",
        )


def __target_exists(args: argparse.Namespace, reddit: Reddit) -> bool:
    """
    Check that the user or subreddit a command names is there, before anything is fetched.

    Commands that name no user or subreddit pass straight through.

    :param args: The parsed arguments.
    :type args: argparse.Namespace
    :param reddit: The Reddit handle to read through.
    :type reddit: Reddit
    :returns: True when the target is there, or when the command names none.
    :rtype: bool
    """

    handle: t.Union[UserEndpoint, SubredditEndpoint]
    if args.command == "user":
        handle, label, kind = reddit.user(args.username), f"u/{args.username}", "user"
    elif args.command == "subreddit":
        handle, label, kind = reddit.subreddit(args.name), f"r/{args.name}", "subreddit"
    else:
        return True

    with console.status(f"[dim]Checking {kind} ({label}) availability[/]…"):
        found = handle.exists()
    if found:
        console.log(f"[green]{kind.title()} {label} exists[/].")
    else:
        console.log(f"[yellow]{kind.title()} {label} does not exist[/].")
    return found


def __cmd_license():
    """Handle the ``license`` conditions command."""

    console.print(License.conditions)


def __cmd_license_warranty():
    """Handle the ``license warranty`` command."""

    console.print(License.warranty)


def __build_parser() -> argparse.ArgumentParser:
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
    __add_output(post)
    post.set_defaults(func=__cmd_post)
    post_actions = post.add_subparsers(dest="post_action")
    post_comments = post_actions.add_parser("comments", help="get comments for the post")
    __add_limit(post_comments)
    __add_comment_sort(post_comments, "top")
    post_comments.add_argument(
        "-d",
        "--depth",
        type=int,
        default=1,
        help="how deep to load comments: 0 first batch only, 1 all top-level comments, "
             "higher also loads nested replies",
    )
    __add_output(post_comments)
    post_comments.set_defaults(func=__cmd_post_comments)

    feed = subparsers.add_parser("feed", help="front-page post feeds")
    feed.add_argument(
        "listing",
        nargs="?",
        choices=("hot", "new", "top", "rising", "controversial"),
        default="hot",
        help="front-page listing to read",
    )
    feed.add_argument(
        "--stream",
        action="store_true",
        help="print new posts as they appear until Ctrl+C, ignoring the listing, --limit, "
             "--timeframe and --export",
    )
    __add_limit(feed)
    __add_timeframe(feed)
    __add_output(feed)
    feed.set_defaults(func=__cmd_feed)

    subreddit = subparsers.add_parser("subreddit", help="data from one subreddit")
    subreddit.add_argument("name", help="the subreddit name")
    __add_output(subreddit)
    subreddit.set_defaults(func=__cmd_subreddit)
    subreddit_actions = subreddit.add_subparsers(dest="subreddit_action")

    subreddit_profile = subreddit_actions.add_parser("profile", help="get the subreddit profile")
    __add_output(subreddit_profile)
    subreddit_profile.set_defaults(func=__cmd_subreddit)

    subreddit_posts = subreddit_actions.add_parser("posts", help="get posts from the subreddit")
    subreddit_posts.add_argument(
        "--stream",
        action="store_true",
        help="print new posts as they appear until Ctrl+C, ignoring --limit, --listing, "
             "--timeframe and --export",
    )
    __add_feed_options(subreddit_posts)
    subreddit_posts.set_defaults(func=__cmd_subreddit_posts)

    subreddit_comments = subreddit_actions.add_parser(
        "comments", help="get recent comments from the subreddit"
    )
    subreddit_comments.add_argument(
        "--stream",
        action="store_true",
        help="print new comments as they appear until Ctrl+C, ignoring --limit and --export",
    )
    __add_limit(subreddit_comments)
    __add_output(subreddit_comments)
    subreddit_comments.set_defaults(func=__cmd_subreddit_comments)

    subreddit_search = subreddit_actions.add_parser(
        "search", help="search posts inside the subreddit"
    )
    subreddit_search.add_argument("query", help="the search text")
    __add_search_options(subreddit_search)
    subreddit_search.set_defaults(func=__cmd_subreddit_search)

    subreddit_wiki_pages = subreddit_actions.add_parser(
        "wiki-pages", help="list wiki pages in the subreddit"
    )
    __add_output(subreddit_wiki_pages)
    subreddit_wiki_pages.set_defaults(func=__cmd_subreddit_wiki_pages)

    subreddits = subparsers.add_parser("subreddits", help="bulk subreddit feeds")
    subreddits.add_argument(
        "which",
        nargs="?",
        choices=("default", "new", "popular"),
        default="popular",
        help="which subreddit feed to read",
    )
    __add_limit(subreddits)
    __add_output(subreddits)
    subreddits.set_defaults(func=__cmd_subreddits)

    user = subparsers.add_parser("user", help="data about one user")
    user.add_argument("username", help="the user's name")
    __add_output(user)
    user.set_defaults(func=__cmd_user)
    user_actions = user.add_subparsers(dest="user_action")

    user_profile = user_actions.add_parser("profile", help="get the user profile")
    __add_output(user_profile)
    user_profile.set_defaults(func=__cmd_user)

    user_posts = user_actions.add_parser("posts", help="get posts submitted by the user")
    __add_feed_options(user_posts)
    user_posts.set_defaults(func=__cmd_user_posts)

    user_comments = user_actions.add_parser("comments", help="get comments by the user")
    __add_limit(user_comments)
    __add_comment_sort(user_comments, "new")
    __add_output(user_comments)
    user_comments.set_defaults(func=__cmd_user_comments)

    user_overview = user_actions.add_parser("overview", help="get posts and comments by the user")
    __add_limit(user_overview)
    __add_output(user_overview)
    user_overview.set_defaults(func=__cmd_user_overview)

    user_moderated = user_actions.add_parser("moderated", help="get moderated subreddits")
    __add_output(user_moderated)
    user_moderated.set_defaults(func=__cmd_user_moderated)

    user_trophies = user_actions.add_parser("trophies", help="get user trophies")
    __add_output(user_trophies)
    user_trophies.set_defaults(func=__cmd_user_trophies)

    users = subparsers.add_parser("users", help="bulk user feeds")
    users.add_argument(
        "which",
        nargs="?",
        choices=("new", "popular"),
        default="popular",
        help="which user feed to read",
    )
    __add_limit(users)
    __add_output(users)
    users.set_defaults(func=__cmd_users)

    search = subparsers.add_parser("search", help="search posts, subreddits, or users")
    search_actions = search.add_subparsers(dest="kind", required=True)

    search_posts = search_actions.add_parser("posts", help="search posts")
    search_posts.add_argument("query", help="the search text")
    __add_search_options(search_posts)
    search_posts.set_defaults(func=__cmd_search)

    search_subreddits = search_actions.add_parser("subreddits", help="search subreddits")
    search_subreddits.add_argument("query", help="the search text")
    __add_limit(search_subreddits)
    __add_output(search_subreddits)
    search_subreddits.set_defaults(func=__cmd_search)

    search_users = search_actions.add_parser("users", help="search users")
    search_users.add_argument("query", help="the search text")
    __add_limit(search_users)
    __add_output(search_users)
    search_users.set_defaults(func=__cmd_search)

    lic = subparsers.add_parser("license", help="show the license")
    license_actions = lic.add_subparsers(dest="license_action", required=True)

    conditions = license_actions.add_parser("conditions", help="show the conditions")
    conditions.set_defaults(func=__cmd_license)

    warranty = license_actions.add_parser("warranty", help="show the warranty")
    warranty.set_defaults(func=__cmd_license_warranty)

    return parser


def run_cli(argv: t.Optional[t.Sequence[str]] = None):
    """
    Run the command line.

    Catches a Ctrl-C and any error so the program ends with a clear line rather than a traceback,
    then reports how long it ran. A plain ``--help`` or ``--version`` exits before that line.

    An error exits non-zero, so a script can tell a failed run from an empty one. A Ctrl-C is the
    user's own doing, so it stays a success.

    :param argv: Arguments to parse. Defaults to ``sys.argv``.
    :type argv: t.Optional[t.Sequence[str]]
    """

    start_time = datetime.now(timezone.utc)
    console.set_window_title(title=f"{Project.name} v{Version.release}")
    failed = False
    try:
        parser = __build_parser()
        args = parser.parse_args(argv)
        if args.command == "license":
            args.func()
        else:
            with Reddit() as reddit:
                if __target_exists(args=args, reddit=reddit):
                    args.func(args=args, reddit=reddit)
    except KeyboardInterrupt:
        console.log("\nUser interruption detected ([yellow]Ctrl+C[/])")
    except Exception as e:
        console.log(f"An error occurred: [red]{e}[/]")
        failed = True

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    console.log(f"Finished in {elapsed:.2f}s")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
