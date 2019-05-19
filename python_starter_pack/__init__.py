# coding: utf8

"""This file is necesary if you want to import your module as a library, as in:

>>> import python_starter_pack
>>> python_starter_pack.some_func()
True

This documentation contains doctests that should be automatically run
when you execute `pipenv run pytest`.
"""

# This is how you "export" inner-module functionality to the top-level module
# Also, this is to test that local imports work inside your package
from .funcs import some_func
from .funcs import say_hello
