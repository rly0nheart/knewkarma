Knew Karma
==========

**Knew Karma** (*/nuː ‘kɑːrmə/*) is a no-auth data analysis toolkit designed to provide an extensive range of
functionalities for exploring and analysing Reddit data.

.. raw:: html

   <p>
     <a href="https://github.com/rly0nheart/knewkarma"><img alt="Code Style" src="https://img.shields.io/badge/code%20style-black-000000?logo=github&link=https%3A%2F%2Fgithub.com%2Frly0nheart%2Fknewkarma"></a>
     <a href="https://pepy.tech/project/knewkarma"><img alt="Downloads" src="https://img.shields.io/pepy/dt/knewkarma?logo=pypi"></a>
     <a href="https://pypi.org/project/knewkarma"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/knewkarma?logo=pypi&link=https%3A%2F%2Fpypi.org%2Fproject%2Fknewkarma"></a>
   </p>

Quick Start
-----------

.. code-block:: python
   
   from pprint import pprint
   from knewkarma import Reddit

   with Reddit() as client:
     user_profile = client.user(username="spez").about()
     pprint(user_profile)   

.. code-block:: bash

   knewkarma user spez

.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   cli
   api
