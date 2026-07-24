import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from knewkarma.meta.about import Author, Project
from knewkarma.meta.version import Version

project = Project.name
author = Author.name
copyright = f"{date.today().year}, {Author.name}"
release = Version.full_version
version = Version.release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
exclude_patterns = []
templates_path = ["_templates"]

html_theme = "alabaster"
html_show_sourcelink = False
html_show_sphinx = False
html_sidebars = {
    "**": ["sidebar.html", "searchbox.html"],
}
html_theme_options = {
    "show_powered_by": False,
    "show_related": False,
}
