# Python Starter Pack

<img alt="PyPI - License" src="https://img.shields.io/pypi/l/python-starter-pack.svg"> <img alt="PyPI" src="https://img.shields.io/pypi/v/python-starter-pack.svg"> <img alt="Travis (.org)" src="https://img.shields.io/travis/apiad/python-starter-pack/master.svg"> <img alt="Codecov" src="https://img.shields.io/codecov/c/github/apiad/python-starter-pack.svg"> <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/python-starter-pack.svg">

> Quickly setup a Python 3 library complete with continuous integration, code coverage and automatic deployment to PyPi in 5 minutes.

## What's this about?

Have you ever wanted to make a Python library available on PyPi, but struggled with all the fuss about `setup.py`, continuous integration, unit testing, and such? Been there ;).

After reading a bunch of tutorials and trying a few different ways on my own, this is the most condensed and streamlined checklist I've come up with. Just by forking this project and following the next few steps you'll be up on your own with a brand new Python library project, together with unit testing, continuous integration, code coverage, and automatic deployment to PyPi. Tag along.

## A Python starter pack

Starting a new Python library project? Follow these steps:

### Step 1: Setting up the environment

First, it should go without saying, get a [Github account](https://github.com/signup) if you haven't.

Next, [fork this project](https://github.com/apiad/python-starter-pack), and then clone your own version, or directly clone the project:

```bash
$ git clone git@github.com:apiad/python-starter-pack <my-project>
```

Now you can head over to your project's folder and see what's inside:

```bash
$ cd <my-project>
$ ls

total 48K
-rw-r--r-- 1 user user 1,1K may 19 18:44 LICENSE
-rw-r--r-- 1 user user  321 may 22 15:29 makefile
-rw-r--r-- 1 user user   16 may 19 19:34 MANIFEST.in
-rw-r--r-- 1 user user  206 may 19 19:36 Pipfile
-rw-r--r-- 1 user user  13K may 19 19:36 Pipfile.lock
drwxr-xr-x 2 user user 4,0K may 22 15:31 python_starter_pack
-rw-r--r-- 1 user user 2,2K may 22 15:40 Readme.md
-rw-r--r-- 1 user user 2,1K may 22 15:31 setup.py
drwxr-xr-x 2 user user 4,0K may 22 15:31 tests
```

We'll go in depth on the contents of each file later on. The most important things now is to notice that we have a `Pipfile`, hence, we will be using `pipenv` for dependency management.

So, if you haven't already, [install pipenv](https://github.com/pypa/pipenv). The easiest way, in Linux, is simply to run:

```bash
$ make install

pip install pipenv
...
pipenv install --dev --skip-lock
Installing dependencies from Pipfile…
  🐍   ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉ 5/5 — 00:00:01
...
```

This will use our `makefile` definition for `install` which basically installs `pipenv` and updates the dependencies.

### Step 2: Adding your code

Now that you have the dependencies and development environment in place, you can start adding your code.
We have sample code in the `python_starter_pack` folder. Check the folder and files' content if you need a little guidance, or simply replace with your own code.

For starters, the `python_starter_pack` folder is what we call a _Python module_, because it contains a `__init__.py` file which allows it to be imported from Python code.

There are also some basic functions in there just to illustrate the basic functionality for importing code and, as we'll see next, for testing.

### Step 3: Running tests

The `tests` folder will contain all your unit tests. We'll be using the awesome `pytest` module, and also `pylint` for ensuring our code is Pythonic and beautiful.

If you have been changing code, you will need to make some changes to `makefile` to ensure everything is consistent. Open it and update the value of the `PROJECT` variable to point to your project's folder. In Linux you can just hack your way with the following (where `<my-project>` is your project's folder):

```bash
$ sed -i -E "/^PROJECT/s/(.*)/PROJECT=<my-project>/" makefile
```

In any case, now you can test your code with:

```bash
$ make test
```

This will run `pylint` and then `pytest`, testing doc-strings and unit tests in the `tests` folder. Check the file `tests/test_module.py` for head-start on unit testing in Python.
This will also create and print `codecov` coverage reports, telling you how much of your code is tested.
Make sure to re-test every time you change something.

### Step 4: Publishing on Github

If you forked your project then your git remote is set. Otherwise, you will need [to create a new project](https://github.com/new) on Github and set up your remote. In any case, when ready, you can just push your code:

```bash
$ git push origin master
```

### Step 5: Setup Travis-CI

Now that your project is on Github, the next step is to setup continuous integration with [Travis-CI](https://travis-ci.org). If you don't still have an account on Travis-CI, register there and [activate your repository](https://travis-ci.org/account/repositories).
