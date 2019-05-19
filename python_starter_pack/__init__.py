# coding: utf8

"""This file is necesary if you want to import your module as a library, as in:

>>> import python_starter
>>> python_starter.VERSION
'0.1.0'
"""

VERSION = '0.1.0'

# This is how you "export" inner-module functionality to the top-level module
# Also, this is to test that local imports work inside your package
from .funcs import some_func
