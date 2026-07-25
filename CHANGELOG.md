# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [9.1.1] - 2026-07-25

### Added

- Stream a subreddit's posts or comments as they appear: `reddit.subreddit("python").stream()` and
  `.stream(kind="comments")`, or `--stream` on `posts`, `comments`, and `feed`.
- Reads now pace themselves against Reddit's rate limit. A limited read waits and retries instead
  of failing.

### Fixed

- `knewkarma subreddit NAME wiki-pages` takes `--export`, and names its files like the other
  commands.

## [9.0.1] - 2026-07-25

### Added

- `Reddit` and `RedditAuth` are now context managers. Use `with Reddit() as reddit:` to close the
  underlying network session automatically on exit.

### Removed

- The `session` parameter on `Reddit` and `RedditAuth`. The client always creates and owns its own
  `requests.Session` now.

## [8.0.4] - 2026-07-24

### Added

- Anonymous Reddit access. Reads public data with an app-only token, so it needs no account and no API secret.
- Grouped API on a single `Reddit` entry point: `reddit.user(...)`, `reddit.subreddit(...)`, `reddit.post(...)`,
  `reddit.multireddit(...)`, and the `reddit.search`, `reddit.subreddits`, and `reddit.users` collections.
- Comment reads with a `depth` control that follows Reddit's "load more" stubs as far as you ask.

### Changed

- Split the client into `RedditAuth` (session and token) and `Endpoint` reads (`get`, `paginate`).
- The version now comes from the installed distribution metadata instead of a hard-coded value.
- Rebuilt the documentation and moved the project to Codeberg.

### Fixed

- Dedup bulk results

### Removed

- PRAW, and the old flat, module-per-entity API it backed.

## [7.2.0] - 2025-12-17

- Add engines
- Show response data inside a rich table, and only use dataframes when exporting to files
- Major update to post display format
- Refine viewing posts and comments
- Add render methods for other retirevable reddit data
- Drop using ups and downs to represent upvotes and downvotes as these arent very reliable. Instead, I'm using score and
  place it in between up and down arrows
- Drop aiohttp.ClientSession, for requests.Session
- Clean CLI logic and proper implementation of the license command
- Minor module and class renaming
- Rename cli functions and add references to options and arguments to prevent shadowing warnings
- Remove unnecessarry logs
- Re-enable getting post comments

## [7.1.3] - 2024-10-27

- Deleted more unused code... :)

## [7.1.0] - 2024-10-24

- Applying fix for kraw.Connection in KRAW 0.2.5
- Manual check for updates: use 'knewkarma updates --check/--install'
- Added proxy support

## [7.0.10] - 2024-10-19

- Patch for error in User.profile, Subreddit.profile, and Subreddit.wiki_page.

## [7.0.0] - 2024-10-05

- Bump cryptography from 43.0.0 to 43.0.1
- Bump rich from 13.7.1 to 13.8.0
- Bump rich from 13.8.0 to 13.8.1
- 3 tests are failing! :( (I can't figure out why)
- 1 failing test fixed
- Bump pandas from 2.2.2 to 2.2.3
- Bump rich from 13.8.1 to 13.9.1
- Bump rich from 13.9.1 to 13.9.2

## [6.1.5] - 2024-08-12

- Working on creating a collective on Open Collective for potential sponsors of Knew Karma

## [6.1.3] - 2024-08-10

- Patch for version checker

## [6.1.2] - 2024-08-10

- Results in panel was a bad idea

## [6.0.3] - 2024-08-08

- Patch for failing file exports

## [5.4.0] - 2024-07-31

- rename the 'keyword' params in 'knewkarma.User().search_comments()' and 'knewkarma.User().search_posts()' to 'query',
  and improved searching in these methods.

## [5.3.15] - 2024-07-29

- Move to , and drop the suffix parameter. Improve data checking in . If invalid data is provided, raise a exception.
  Optimise code

## [5.3.14] - 2024-07-29

- Add code examples to doc strings

## [5.3.12] - 2024-07-28

- Major updates to documentation: knewkarma.readthedocs.io
- Major updates to docs: https://knewkarma.readthedocs.io
- Major updates to documentation: https://knewkarma.readthedocs.io

## [5.3.10] - 2024-07-27

- Clear screen on start

## [5.3.5] - 2024-07-26

- Minor updates
- Add favicon.ico to readthedocs page
- chnage readthedocs theme

## [5.3.0] - 2024-07-22

- 5.3.0 RC1

## [5.2.0] - 2024-07-21

- Major code structure changes
- Update lock file
- Doc string updates
- Update doc strings
- Adding icon to app menu

## [5.0.0] - 2024-07-03

- Discontinue GUI releases (sorry people)
- Discontinue GUI releases
- Major API changes.
- Simplified getting posts from listings
- Updated/improved tests

## [4.2.0.0] - 2024-06-23

- Resize GUI. Redesign About Window (not yet done)
- Fix workflow run failure
- Delete docs/.tmp
- Minor update in api.py
- Update Dockerfile
- Fix typo in help.py
- Allow checking for updates with just the -u/--update
- Move banner to _utils.py
- Update GUI About Box and Main Form

## [4.1.0.0] - 2024-04-12

- Add new splash screen to GUI
- Update setup project
- fix .resx file
- Add some nice screenshots

## [4.0.0.0] - 2024-04-03

- Get bulk data in batches of 100
- Add progress bar to bulk data retrievals
- SHow exported files in a tree-like structure
- Add statuses
- Automatic sleep timer when getting bulk data
- Option to specify output time format --time-format (, LANG=en_ZM LANGUAGE=en_ZM:en LC_CTYPE="en_ZM" LC_NUMERIC="en_ZM"
  LC_TIME="en_ZM" LC_COLLATE="en_ZM" LC_MONETARY="en_ZM" LC_MESSAGES="en_ZM" LC_PAPER="en_ZM" LC_NAME="en_ZM"
  LC_ADDRESS="en_ZM" LC_TELEPHONE="en_ZM" LC_MEASUREMENT="en_ZM" LC_IDENTIFICATION="en_ZM" LC_ALL=)
- Release candidate 4
- Tried to make it add an icon in the app menu, didn't go very well, so I'll have it without it... for now
- Bum version 3.5 -> 4.0
- Update help message
- Update help message and docs

## [3.4.0.0] - 2023-12-22

- Added api tests
- Rename 'Knew Karma' directory to 'Knew Karma GUI'
- Added counter in posts and comments ouptut
- Removed 'examples' directory (code examples will be available in the README)
- Consistency in base.py
- Update parser
- Minor fix in api.py
- Python Library: Showing expected and default values to sort and timeframe parameters

## [3.3.0.0] - 2023-12-04

- Improved output file naming by adding timestamps. Optimised code in the api module. Fix call functions running twice.
- Optimised code in ApiHandler and CoreUtils

## [3.2.0.0] - 2023-12-03

- Add -t/--timeframe flag for specifying the timeframe from which posts/comments will be fetched from, defaults to 'all'
- Improved output with rich.pretty
- Minor unimportant changes
- Improved data writing to files. Showing Awardee Karma in User data output. Separated data classes to a different file:
  data.py. Doc strings in base.py ;)

## [3.0.0.0] - 2023-12-01

- Working as a Python library. Getting more than 100 posts/comments (beta). Dropped dependency on plyer
- Sending asynchronous requests. Implemented run-time profiling
- Refactored to be used as a Python library while maintaining the CLI functionality. Implement sending asyncronous
  requests and runtime profiling (CLI)
- Update: _cli.py
- Update: _cli.py. Major changes in code structure
- Fully asynchronous. Further code optimisations and restructuring
- Update: README.md
- Improve file writer cli and parser
- Added posts pagination in GUI
- Fix cli parser

## [2.4.2.0] - 2023-11-26

- Fix notification bug in api.py:get_updates

## [2.4.1.0] - 2023-11-25

- Patch AttributeError in executor.py

## [2.4.0.0] - 2023-11-25

- Use PyPI to get updates
- Set default operation mode to 'User'
- Check for updates in interactive CLI
- Improved update checking function.
- Update: coreutils.py, executor.py, knewkarma.py

## [2.3.1.0] - 2023-11-23

- patch

## [2.3.0.0] - 2023-11-23

- Minor improvement: api.py, coreutils.py masonry.py
- Minor improvement: api.py, masonry.py
- Major improvement: coreutils.py, masonry.py, knewkarma.py, delete: parser.py

## [2.2.0.0] - 2023-11-22

- 2.2.0.0 - Code optimisations
- 2.2.0.0 - Update api.py
- Update parser.py: Set default bulk data output limit to 50

