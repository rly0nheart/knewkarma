# Python API

Build a `Reddit` client for scripts.

```python
from knewkarma import Reddit

reddit = Reddit(user_agent="MyKnewKarmaApp/1.0")
```

Or as a context manager:

```python
from knewkarma import Reddit

with Reddit(user_agent="MyKnewKarmaApp/1.0") as reddit:
    ...
```

## Users

### About

```python
user = reddit.user("spez").about()

print(user.name)
print(user.total_karma)
print(user.subreddit.display_name)
```

### Comments

```python
comments = reddit.user("spez").comments(limit=25)

for comment in comments:
    print(comment.body)
```

### Posts

```python
posts = reddit.user("spez").posts(limit=25)

for post in posts:
    print(post.title)
```

## Subreddits

### About

```python
subreddit = reddit.subreddit("python").about()

print(subreddit.display_name)
print(subreddit.public_description)
```

### Posts / Comments

```python
posts = reddit.subreddit("python").posts(listing="top", timeframe="week", limit=10)

for post in posts:
    print(post.title)
```

#### Streaming

Stream new posts as they appear, in the order they were posted:

```python
for post in reddit.subreddit("python").stream(skip_existing=True):
    print(post.title)
```

Comments streaming works the same way:

```python
for comment in reddit.subreddit("python").stream(kind="comments", skip_existing=True):
    print(comment.body)
```

> The stream runs until you leave the loop. `skip_existing` drops what is already there, so you only
> get posts or comments made from now on. `pause_after=N` yields `None` after N rounds bring nothing,
> so you can do other work. `on_wait` takes a function called with the seconds left before the next
> read.

## Search

```python
posts = reddit.search.posts("python asyncio", limit=10)
users = reddit.search.users("spez", limit=10)
subreddits = reddit.search.subreddits("python", limit=10)
```

## Models

Each model keeps the Reddit data on `.data` and `.raw`.

Fields also work as attributes:

```python
post.title
comment.body
user.name
subreddit.display_name
```

Nested data uses the same form:

```python
post.preview.images[0].source.url
user.subreddit.display_name
```
