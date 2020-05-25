# ngshare_exchange
[![Build Status](https://travis-ci.org/lxylxy123456/ngshare_exchange.svg?branch=master)](https://travis-ci.org/lxylxy123456/ngshare_exchange)
[![codecov](https://codecov.io/gh/lxylxy123456/ngshare_exchange/branch/master/graph/badge.svg)](https://codecov.io/gh/lxylxy123456/ngshare_exchange)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://readthedocs.org/projects/ngshare-exchange/badge/?version=latest)](https://ngshare-exchange.readthedocs.io/en/latest/?badge=latest)

```
.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

.. image:: https://travis-ci.org/lxylxy123456/ngshare_exchange.svg?branch=master
    :target: https://travis-ci.org/lxylxy123456/ngshare_exchange

.. image:: https://codecov.io/gh/lxylxy123456/ngshare_exchange/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/lxylxy123456/ngshare_exchange

.. image:: https://readthedocs.org/projects/ngshare-exchange/badge/?version=latest
    :target: https://ngshare-exchange.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status
```

(TODO: Add badges after finishing up Travis + Codecov)
Custom [nbgrader](https://github.com/jupyter/nbgrader) exchange to be used with [ngshare](https://github.com/lxylxy123456/ngshare). This should be installed in the singleuser image of [Z2JH](https://github.com/jupyterhub/zero-to-jupyterhub-k8s) to allow the users to use ngshare.

# Installation instructions

This assumes you have [installed ngshare](https://ngshare.readthedocs.io/en/latest/user_guide/install_ngshare.html).

### Z2JH
You should already be familiar with how to [customize user images](https://zero-to-jupyterhub.readthedocs.io/en/latest/customizing/user-environment.html#customize-an-existing-docker-image) on Z2JH. Add the following to your customized singleuser container:
1. Install the latest nbgrader in the pod. Unfortunately, ngshare_exchange relies on [pluggable exchange](https://github.com/jupyter/nbgrader/pull/1238), which is available in the not-yet-released nbgrader v0.7.0. Therefore, you have to install it from git for now: `python3 -m pip install git+https://github.com/jupyter/nbgrader.git`
2. Install ngshare_exchange. This can be easily done by running `python3 -m pip install git+https://github.com/lxylxy123456/ngshare_exchange`. We're also going to package this on PyPI soon.
3. Ask nbgrader to use ngshare_exchange as the default exchange. Simply create a global nbgrader configuration file at `/etc/jupyter/nbgrader_config.py`, with the following contents:
```python
from ngshare_exchange import configureExchange
configureExchange(get_config())
```
That should be all! Here's a sample Dockerfile that you can add to yours:
```Dockerfile
FROM jupyterhub/k8s-singleuser-sample:0.9.0

# Install latest nbgrader and enable the extensions
RUN python3 -m pip install git+https://github.com/jupyter/nbgrader.git && \
    jupyter nbextension install --symlink --sys-prefix --py nbgrader && \
    jupyter nbextension enable --sys-prefix --py nbgrader && \
    jupyter serverextension enable --sys-prefix --py nbgrader

# Install ngshare_exchange
RUN python3 -m pip install git+https://github.com/lxylxy123456/ngshare_exchange

# Configure nbgrader
USER 0
RUN echo -e "from ngshare_exchange import configureExchange\nconfigureExchange(get_config())" >> /etc/jupyter/nbgrader_config.py
USER $NB_UID
```

### Regular JupyterHub
If you aren't using Kubernetes, you may still run ngshare if you wish. If that's the case, you just need to install ngshare_exchange, but you also need to tell it where the ngshare service is. TODO: Finish writing this part once I finish writing ngshare installation documentation for regular JupyterHub.

# ngshare Course Management

To manage students in your course, please don't use formgrader's web interface since it doesn't use ngshare. Instead, use the `ngshare-course-management` command that gets installed with this package. Usage is as follows:

## Flags
- `-c`, `--course_id` : A unique name for the course.
- `-s`, `--student_id` : The ID given to a student.
- `-i`, `--instructor_id` : The ID given to an instructor
- `-f`, `--first_name` : First name of the user you are creating
- `-l`, `--last_name` : Last name of the user you are creating
- `-e`, `--email` : Email of the user you are creating
- `--students_csv` : csv file containing a list of students to add. See `students.csv` as an example. 
- `--instructors` : list of instructors
- `--gb` : add/update the student to the nbgrader gradebook
- `--force` : use to force an nbgrader gradebook command
---
### Create a course
User creating course must be *admin*.
You can specify the instructors for the course in a list.

```
$ ngshare_course_management create_course --course_id math101 
```
```
$ ngshare_course_management create_course -c math101 -i
```
```
$ ngshare_course_management create_course --course_id math101 --instructors math101_instructor1 math101_instructor2
```

Remember to add the `nbgrader_config.py` on the course root directory e.g. `/home/username/math101`
Example course configuration file:
```python
c = get_config()
c.CourseDirectory.course_id = 'math101'
```

Also, remember to add the `nbgrader_config.py` on the instructor's `/home/username/.jupyter` folder.
Example user configuration file:
```python
c = get_config()
c.CourseDirectory.root = '/home/username/math101'
```

### Add/update one student
```
$ ngshare_course_management add_student --course_id math101 --student_id 12345 --first_name jane --last_name doe --email jdoe@mail.com 
```
```
$ ngshare_course_management add_student -c math101 -s 12345 -f jane -l doe -e jdoe@mail.com
```

first name, last name, and email are optional parameters.

### Add/update multiple students
```
$ ngshare_course_management add_students --course_id math101 --students_csv math101Students.csv
```
```
$ ngshare_course_management add_students -c math101 --students_csv math101Students.csv
```

The csv file must have the following columns: **student_id**, **first_name**, **last_name**, **email**.

### Remove student from a course
```
$ ngshare_course_management remove_student --course_id math101 --student_id 12345
```
```
$ ngshare_course_management remove_student -c math101 -s 12345
```

### Add instructor to a course
```
$ ngshare_course_management add_instructor --course_id math101 --instructor_id 12345 --first_name jane --last_name doe --email jdoe@mail.com 
```
```
$ ngshare_course_management add_instructor -c math101 -i 12345 -f jane -l doe -e jdoe@mail.com
```
first name, last name, and email are optional parameters

### Remove instructor from a course
```
$ ngshare_course_management remove_instructor --course_id math101 --instructor_id 12345
```
```
$ ngshare_course_management remove_instructor -c math101 -i 12345
```
---
You can add the `--gb` flag at the end of `add_student`, `add_students`, or `remove_student` to add or remove the students from the nbgrader gradebook **and** ngshare

For example running:
```
 $ ngshare_course_management add_student -c math101 -s 12345 -f jane -l doe -e jdoe@mail.com --gb
 ```

Adding the --gb flag runs:
```
 $ nbgrader db student add --first-name jane --last-name doe --email jdoe@mail.com 12345
```
