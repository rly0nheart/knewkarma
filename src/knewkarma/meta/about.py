__all__ = ["Author", "Project"]


class Author:
    name: str = "Ritchie Mwewa"
    username: str = "rly0nheart"
    gravatar: str = f"https://gravatar.com/{username}"


class Project:
    name: str = "Knew Karma"
    package: str = "knewkarma"
    summary: str = f"Zero-auth toolkit for Reddit-data analysis -- by {Author.name}"
    description: str = f"""
{name} (/nuː ‘kɑːrmə/) is an analysis toolkit designed to provide an extensive range of
functionalities for exploring and analysing Reddit data. It includes a Command-Line Interface (CLI), and an
Application Programming Interface (API) to enable an easy integration in other Python Projects.
"""

# -------------------------------- END ----------------------------------------- #
