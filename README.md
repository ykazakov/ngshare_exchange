# ngshare_exchange
[![Build Status](https://travis-ci.org/LibreTexts/ngshare_exchange.svg?branch=master)](https://travis-ci.org/LibreTexts/ngshare_exchange)
[![codecov](https://codecov.io/gh/LibreTexts/ngshare_exchange/branch/master/graph/badge.svg)](https://codecov.io/gh/LibreTexts/ngshare_exchange)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://readthedocs.org/projects/ngshare-exchange/badge/?version=latest)](https://ngshare-exchange.readthedocs.io/en/latest/?badge=latest)

Custom [nbgrader](https://github.com/jupyter/nbgrader) exchange to be used with [ngshare](https://github.com/LibreTexts/ngshare). This should be installed in the singleuser image of [Z2JH](https://github.com/jupyterhub/zero-to-jupyterhub-k8s) to allow the users to use ngshare.

# Installation instructions

To install this and `ngshare`, see the instructions on [Read the Docs](https://ngshare.readthedocs.io/en/latest/user_guide/install.html).

# ngshare Course Management

To manage students in your course, please don't use formgrader's web interface since it doesn't use ngshare. Instead, use the `ngshare-course-management` command that gets installed with this package. Please [read the documentation](https://ngshare.readthedocs.io/en/latest/user_guide/course_management.html) for instructions on how to use this tool.
