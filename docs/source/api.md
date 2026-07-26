# Python API

Build a `Reddit` client for scripts.

```python
from knewkarma import Reddit

client = Reddit()
```

Or as a context manager:

```python
from knewkarma import Reddit

with Reddit() as client:
    ...
```

## Users

### About

```python
user = client.user("spez").about()

print(user.name)
print(user.total_karma)
print(user.subreddit.display_name)
```

### Comments

```python
comments = client.user("spez").comments(limit=25)

for comment in comments:
    print(comment.body)
```

### Posts

```python
posts = client.user("spez").posts(limit=25)

for post in posts:
    print(post.title)
```

## Subreddits

### About

```python
subreddit = client.subreddit("python").about()

print(subreddit.display_name)
print(subreddit.public_description)
```

### Posts / Comments

```python
posts = client.subreddit("python").posts(listing="top", timeframe="week", limit=10)

for post in posts:
    print(post.title)
```

#### Streaming

Stream new posts as they appear, in the order they were posted:

```python
for post in client.subreddit("python").stream(skip_existing=True):
    print(post.title)
```

Comments streaming works the same way:

```python
for comment in client.subreddit("python").stream(kind="comments", skip_existing=True):
    print(comment.body)
```

> The stream runs until you leave the loop. `skip_existing` drops what is already there, so you only
> get posts or comments made from now on. `pause_after=N` yields `None` after N rounds bring nothing,
> so you can do other work. `on_wait` takes a function called with the seconds left before the next
> read.

## Posts

```python
post = client.post("1ungote").about()

print(post.title)
```

### Comments

Reddit cuts the long parts of a comment tree off behind `load more` stubs. `depth` sets how far to
follow them:

```python
comments = client.post("1ungote").comments(sort="top", depth=1)

for comment in comments:
    print(comment.body)
```

| `depth` | follows                                         |
|---------|-------------------------------------------------|
| `0`     | nothing, you get the first response as it came  |
| `1`     | the top-level stubs, so every top-level comment |
| `n`     | stubs down to reply level `n`                   |
| `None`  | every stub until the tree runs out              |

Following stubs costs requests. `budget` caps how many one read may spend, and defaults to `256`:

```python
comments = client.post("1ungote").comments(depth=None, budget=1000)
```

Once the budget runs out, the stubs still left come back unfollowed, the same as a stub past
`depth`. So a read is never cut short without a trace, and `budget=None` lifts the cap entirely.

## Search

```python
posts = client.search.posts("python asyncio", limit=10)
users = client.search.users("spez", limit=10)
subreddits = client.search.subreddits("python", limit=10)
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

## Export

Every model writes itself out. So does the list a read hands back:

```python
posts = client.subreddit("python").posts(limit=50)

posts.to_dict()  # a list of dicts
posts.to_json("posts.json")  # a json array
posts.to_csv("posts.csv")  # one row per post
```

One thing writes itself out the same way:

```python
post = posts[0]

post.to_dict()  # the fields, as a plain dict
post.to_json("post.json")  # one json object
post.to_csv("post.csv")  # one csv row
```

Reads that fetch a single thing, such as `about()`, return `None` when it is not there, so check
before writing:

```python
user = client.user("spez").about()
if user:
    user.to_json("spez.json")
```

`to_json` and `to_csv` return the path they wrote, and make missing parent directories:

```python
path = posts.to_json("out/2026/posts.json", indent=0)
```

`indent` sets the json formatting. `0` writes it on one line.

A read that returns many things returns a `Things` list. It is a real list, so it indexes, slices
and iterates as always. It just also carries the three methods above.

In csv, a field that nests (a post's `preview`, say) is written as json, so it can be read back:

```python
import csv, json

row = next(csv.DictReader(open("posts.csv")))
preview = json.loads(row["preview"])
```

Columns are the union of every row's fields, since things of the same kind can still differ.
