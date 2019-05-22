# Python Starter Pack

<img alt="PyPI - License" src="https://img.shields.io/pypi/l/python-starter-pack.svg"> <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/python-starter-pack.svg"> <img alt="PyPI" src="https://img.shields.io/pypi/v/python-starter-pack.svg"> <img alt="Travis (.org)" src="https://img.shields.io/travis/apiad/python-starter-pack/master.svg"> <img alt="Codecov" src="https://img.shields.io/codecov/c/github/apiad/python-starter-pack.svg">

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

### Step 5: Setup continuous integration

Now that your project is on Github, the next step is to setup continuous integration with [Travis-CI](https://travis-ci.org). If you don't still have an account on Travis-CI, register there and [activate your repository](https://travis-ci.org/account/repositories).

Travis-CI will ask you to link with your Github account, and install the `travis` app in your Github profile. Once that is done, every push will automatically trigger Travis-CI to run the tests online.

Plus, Travis-CI will automatically push coverage reports to [Codecov](https://codecov.io). Make sure to register there as well, and you will see coverage statistics automatically (there is no need to "activate" a repository there, it happens automatically when Travis pushes coverage stats).

This all just works because of the file `.travis.yml` which you are free to open and modify according to your preferences (e.g., change the preferred Python version).

Once Travis-CI and Codecov are setup, make sure to modify the top of this `Readme.md` file and update these links:

```html
<img alt="Travis (.org)" src="https://img.shields.io/travis/apiad/python-starter-pack/master.svg">
<img alt="Codecov" src="https://img.shields.io/codecov/c/github/apiad/python-starter-pack.svg">
```

Change the `apiad/python-starter-pack` part to match your Github user/repository and you will immediately get these nice badges on your Readme file.

### Step 6: Automatic deploy on PyPi

The next step is to setup automatic deployment on the Python Package Index. We will start with deploying to the test channel before moving on deploying to the real channel.

First, to keep things tidy up, let me explain the how the workflow will be. We will create a `develop` branch:

```bash
$ git branch -C develop
$ git checkout develop
```

Now, on this branch, we will test that deployment to PyPi works. Head over to [test.pypi.org](https://test.pypi.org) and register there. Remember your **username** and **password**.

Now it's time to setup up your package configuration. Open the file `setup.py` and modify the necessary lines. They all say `TODO` on top. You should define there your project's name and modules, copyright info, entry-points (if any) and other metadata (known as classifiers).

Once that is ready, **make sure to change** the `VERSION` variable on top. This `VERSION` variable is what PyPi will use to determine the current version, and if you push twice with the same version you'll get an error because you cannot override something published to PyPi.

Now head over to [Travis-CI](https://travis-ci.org) and navigate to your project's settings. There you will need to set two **environment variables**: `TEST_PYPI_USER` and `TEST_PYPI_PASSWORD` with the values of your username and password for [test.pypi.org](https://test.pypi.org).

Once that is done, you can now push to Github from the `develop` branch and your project will be automatically published on [test.pypi.org](https://test.pypi.org). You can check it there.

By now you should have a workflow cycle that looks something like this:
- Work on the `develop` branch (or a `feature-*` and them merge to `develop`).
- Commit as much as you like.
- Run `make test` often to make sure everything works.
- When you are confident the next feature is working, go over to `setup.py` and bump the `VERSION` variable to your new version.
- Push the `develop` branch to Github.
- Check [Travis-CI](https://travis-ci.org) and [test.pypi.org](https://test.pypi.org) to make sure everything is Ok.

### Step 7: Deploy on PyPi for real

Now you are going to setup deployment on the **real** PyPi index. Head over to [pypi.org](https://test.pypi.org) and register there.

Now go over to Travis-CI settings for your project and set the **environment variables** `PYPI_USERNAME` and `PYPI_PASSWORD`. Once this is ready, Travis will be able to push to PyPi when you commit and push to `master`.

However, for safety reasons, we **do not** deploy on PyPI on every commit to `master`, but **only on tags**. Hence, the workflow is the following:

- Develop on the `develop` branch and commit, bump version, push, rinse, repeat.
- Once you are confident everything is Ok on `develop`, navigate to [Github](https://github.com), and in your project's page, create a **pull request** from `develop` to `master`.
- When the pull request has been created, you will notice that automatically Travis and Codecov start working and basically block your commit until all tests pass.
- Once everything is green, you will be able to **merge** to `master`.
- Finally, **create a release** on Github, with a proper version number (please, the same as in `setup.py`) and then, and only then, will Travis deploy to PyPi.

Enjoy!

## Collaboration

License is MIT, so you know the drill.

> MIT License
>
> Copyright (c) 2019 Alejandro Piad
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.


