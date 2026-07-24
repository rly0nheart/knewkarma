**Knew Karma** (*/nuː ‘kɑːrmə/*) is a data analysis toolkit designed to provide an extensive range of functionalities
for exploring and analysing Reddit data.
<p align="center">
  <a href="https://github.com/rly0nheart/knewkarma"><img alt="Code Style" src="https://img.shields.io/badge/code%20style-black-000000?logo=github&link=https%3A%2F%2Fgithub.com%2Frly0nheart%2Fknewkarma"></a>
  <a href="https://pepy.tech/project/knewkarma"><img alt="Downloads" src="https://img.shields.io/pepy/dt/knewkarma?logo=pypi"></a>
  <a href="https://pypi.org/project/knewkarma"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/knewkarma?logo=pypi&link=https%3A%2F%2Fpypi.org%2Fproject%2Fknewkarma"></a>
  <a href="https://snapcraft.io/knewkarma"><img alt="Snap Version" src="https://img.shields.io/snapcraft/v/knewkarma/latest/stable?logo=snapcraft&color=%23BB431A"></a>
  <!--<a href="https://opencollective.com/knewkarma"><img alt="Open Collective backers and sponsors" src="https://img.shields.io/opencollective/all/knewkarma?logo=open-collective"></a>-->
</p>

```commandline
knewkarma user spez
```

```python
from pprint import pprint
from knewkarma import Reddit

reddit = Reddit(user_agent="MyKnewKarmaApp/1.0")
user = reddit.user(username="spez").about()
pprint(user)
```

## Read the Docs

Refer to the [docs](https://knewkarma.readthedocs.io) for installation instructions, CLI, and API usage.

## License

GPL-3.0+ License © [Ritchie Mwewa](https://rly0nheart.com)
