# Python API

Build a `Reddit` client for scripts.

```python
from knewkarma import Reddit

reddit = Reddit()
```

## Users

```python
user = reddit.user("spez").about()

print(user.name)
print(user.total_karma)
print(user.subreddit.display_name)
```

```python
comments = reddit.user("spez").comments(limit=25)

for comment in comments:
    print(comment.body)
```

## Subreddits

```python
subreddit = reddit.subreddit("python").about()

print(subreddit.display_name)
print(subreddit.public_description)
```

```python
posts = reddit.subreddit("python").posts(listing="top", timeframe="week", limit=10)

for post in posts:
    print(post.title)
```

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
