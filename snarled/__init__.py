"""
snarled
=====

Layout connectivity checker.

`snarled` is a python package for checking electrical connectivity in multi-layer layouts.

It is intended to be "poor-man's LVS" (layout-versus-schematic), for when poverty
has deprived the man of both a schematic and a better connectivity tool.

The main functionality is in `trace_connectivity`.
Useful classes, namely `NetsInfo` and `NetName`, are in `snarled.tracker`.
`snarled.interfaces` contains helper code for interfacing with other packages.
"""
from .main import trace_connectivity, trace_connectivity_preloaded
from .tracker import NetsInfo, NetName
from  . import interfaces


__author__ = 'Jan Petykiewicz'

from .VERSION import __version__
