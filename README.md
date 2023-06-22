snarled README
============

Layout connectivity checker.

`snarled` is a python package for checking electrical connectivity in multi-layer layouts.

It is intended to be "poor-man's LVS" (layout-versus-schematic), for when poverty
has deprived the man of both a schematic and a better connectivity tool.

- [Source repository](https://mpxd.net/code/jan/snarled)
- [PyPI](https://pypi.org/project/snarled)

## Installation

Requirements:
* python >= 3.10 (written and tested with 3.11)
* numpy
* klayout (python package only)


Install with pip:
```bash
pip install snarled
```

Alternatively, install from git
```bash
pip install git+https://mpxd.net/code/jan/snarled.git@release
```

## Example
See `examples/check.py` (python interface) or `examples/run.sh` (command-line interface).

Command line:
```bash
snarled connectivity.oas connectivity.txt -m layermap.txt
```

Python interface:
```python3
from pprint import pformat
import logging

import snarled
from snarled.types import layer_t


logging.basicConfig()
logging.getLogger('snarled').setLevel(logging.INFO)


connectivity = [
    ((1, 0), (1, 2), (2, 0)),   # M1 to M2 (via V12)
    ((1, 0), (1, 3), (3, 0)),   # M1 to M3 (via V13)
    ((2, 0), (2, 3), (3, 0)),   # M2 to M3 (via V23)
    ]

labels_map: dict[layer_t, layer_t] = {
    (1, 0): (1, 0),
    (2, 0): (2, 0),
    (3, 0): (3, 0),
    }

filename = 'connectivity.oas'

nets = snarled.trace_layout(filename, connectivity, topcell='top', labels_map=labels_map)
result = snarled.TraceAnalysis(nets)

print('\n')
print(result)
```

this prints the following:

```
INFO:snarled.trace:Adding layer (3, 0)
INFO:snarled.trace:Adding layer (2, 3)
INFO:snarled.trace:Adding layer (1, 3)
INFO:snarled.trace:Adding layer (1, 2)
INFO:snarled.trace:Adding layer (1, 0)
INFO:snarled.trace:Adding layer (2, 0)


Trace analysis
=============
Nets
(groups of electrically connected labels)
        SignalA,SignalB
        SignalC,SignalD,SignalI
        SignalE,SignalF
        SignalG,SignalH
        SignalK
        SignalK
        SignalL

Opens
(2+ nets containing the same name)
        SignalK : 2 nets

Shorts
(2+ unique names for the same net)
        SignalA,SignalB
        SignalC,SignalD,SignalI
        SignalE,SignalF
        SignalG,SignalH
=============
```

## Code organization

- The primary functionality is in `trace`; specifically `trace.trace_layout()`.
- `main` provides a command-line interface, supported by the functions in `utils`.
