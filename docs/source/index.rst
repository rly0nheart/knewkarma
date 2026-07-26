Knew Karma
==========

**Knew Karma** (*/nuː ‘kɑːrmə/*) is a no-auth data analysis toolkit designed to provide an extensive range of
functionalities for exploring and analysing Reddit data.

.. raw:: html

   <p>
     <a href="https://codeberg.org/knewkarma/knewkarma"><img alt="Code Style" src="https://img.shields.io/badge/code%20style-black-000000?logo=codeberg&link=https%3A%2F%2Fcodeberg.org%2Fknewkarma%2Fknewkarma"></a>
     <a href="https://pepy.tech/project/knewkarma"><img alt="Downloads" src="https://img.shields.io/pepy/dt/knewkarma?logo=pypi"></a>
     <a href="https://pypi.org/project/knewkarma"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/knewkarma?logo=pypi&link=https%3A%2F%2Fpypi.org%2Fproject%2Fknewkarma"></a>
   </p>

What it can read
----------------

.. list-table::
   :widths: 25 35 40
   :header-rows: 1

   * - Area
     - Command
     - Result
   * - Post
     - ``knewkarma post ID``
     - One post.
   * - Post
     - ``knewkarma post ID comments``
     - Comments on one post.
   * - Feed
     - ``knewkarma feed top``
     - Posts from a Reddit feed.
   * - Search
     - ``knewkarma search posts QUERY``
     - Posts that match a query.
   * - Search
     - ``knewkarma search subreddits QUERY``
     - Communities that match a query.
   * - Search
     - ``knewkarma search users QUERY``
     - Users that match a query.
   * - Subreddit
     - ``knewkarma subreddit NAME``
     - A community profile.
   * - Subreddit
     - ``knewkarma subreddit NAME posts``
     - Posts from one community.
   * - Subreddit
     - ``knewkarma subreddit NAME comments``
     - Recent comments from one community.
   * - Subreddit
     - ``knewkarma subreddit NAME search QUERY``
     - Posts in one community that match a query.
   * - Subreddit
     - ``knewkarma subreddit NAME wiki-pages``
     - Wiki page names.
   * - User
     - ``knewkarma user NAME``
     - A user profile.
   * - User
     - ``knewkarma user NAME posts``
     - Posts by one user.
   * - User
     - ``knewkarma user NAME comments``
     - Comments by one user.
   * - User
     - ``knewkarma user NAME overview``
     - Posts and comments by one user.
   * - User
     - ``knewkarma user NAME moderated``
     - Communities moderated by one user.
   * - User
     - ``knewkarma user NAME trophies``
     - User trophies.
   * - Lists
     - ``knewkarma subreddits popular``
     - Public community lists.
   * - Lists
     - ``knewkarma users popular``
     - Public user lists.

Start here
----------

.. code-block:: console

   knewkarma user spez
   knewkarma user spez posts --limit 25
   knewkarma subreddit python posts --listing top --timeframe week
   knewkarma search posts "python asyncio"

.. toctree::
   :maxdepth: 2

   installation
   cli
   api
