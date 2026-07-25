# Commands

The command names the target first. The action comes next.

Use this form:

```console
knewkarma TARGET NAME ACTION
```

Options change the action. They do not choose the action.

## Help

```console
knewkarma --help
knewkarma user --help
knewkarma subreddit python posts --help
```

## Posts

```console
knewkarma post POST_ID
knewkarma post POST_ID comments --sort top --limit 100
knewkarma post POST_ID comments --depth 2
```

## Feeds

```console
knewkarma feed
knewkarma feed hot
knewkarma feed new
knewkarma feed top --timeframe week
knewkarma feed rising
knewkarma feed controversial
knewkarma feed --stream
```

`knewkarma feed` means `hot`.

## Search

```console
knewkarma search posts QUERY
knewkarma search subreddits QUERY
knewkarma search users QUERY
```

Post search accepts `--sort`, `--timeframe`, `--limit`, and `--export`.

## Subreddit

```console
knewkarma subreddit SUBREDDIT
knewkarma subreddit SUBREDDIT profile
knewkarma subreddit SUBREDDIT posts --listing hot --limit 100
knewkarma subreddit SUBREDDIT comments --limit 100
knewkarma subreddit SUBREDDIT search QUERY --sort relevance --timeframe all
knewkarma subreddit SUBREDDIT wiki-pages
knewkarma subreddit SUBREDDIT posts --stream
knewkarma subreddit SUBREDDIT comments --stream
```

`knewkarma subreddit SUBREDDIT` means `profile`.

`--stream` prints each new post or comment as it appears and runs until Ctrl+C. It ignores
`--limit`, `--listing`, `--timeframe`, and `--export`.

## Subreddit Lists

```console
knewkarma subreddits
knewkarma subreddits popular
knewkarma subreddits new
knewkarma subreddits default
```

`knewkarma subreddits` means `popular`.

## User

```console
knewkarma user USER
knewkarma user USER profile
knewkarma user USER posts --listing hot --limit 100
knewkarma user USER comments --sort new --limit 100
knewkarma user USER overview --limit 100
knewkarma user USER moderated
knewkarma user USER trophies
```

`knewkarma user USER` means `profile`.

## User Lists

```console
knewkarma users
knewkarma users popular
knewkarma users new
```

`knewkarma users` means `popular`.

## Export

Use `--export` on commands that return Reddit objects.

```console
knewkarma subreddit AskScience posts --export=json,csv
```

Knew Karma writes files under `exports/`.

## License

```console
knewkarma license conditions
knewkarma license warranty
```
