"""
snarled
=====

Layout connectivity checker.

`snarled` is a python package for checking electrical connectivity in multi-layer layouts.

It is intended to be "poor-man's LVS" (layout-versus-schematic), for when poverty
has deprived the man of a schematic and a better connectivity tool.

The main functionality is in `trace`.
`__main__.py` details the command-line interface.
"""
from .trace import trace_layout, TraceAnalysis

__author__ = 'Jan Petykiewicz'
__version__ = '1.0'
