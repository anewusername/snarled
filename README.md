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
* python >= 3.9 (written and tested with 3.10)
* numpy
* pyclipper


Install with pip:
```bash
pip3 install snarled
```

Alternatively, install from git
```bash
pip3 install git+https://mpxd.net/code/jan/snarled.git@release
```

## Example
See `examples/check.py`. Note that the example uses `masque` to load data.

```python3
from pprint import pformat
from masque.file import gdsii, oasis
import snarled
import snarled.interfaces.masque

# Layer definitions
connectivity = {
    ((1, 0), (1, 2), (2, 0)),   #M1 to M2 (via V12)
    ((1, 0), (1, 3), (3, 0)),   #M1 to M3 (via V13)
    ((2, 0), (2, 3), (3, 0)),   #M2 to M3 (via V23)
    }


cells, props = oasis.readfile('connectivity.oas')
topcell = cells['top']

polys, labels = snarled.interfaces.masque.read_cell(topcell, connectivity)
nets_info = snarled.trace_connectivity(polys, labels, connectivity)

print('\nFinal nets:')
print([kk for kk in nets_info.nets if isinstance(kk.name, str)])

print('\nShorted net sets:')
for short in nets_info.get_shorted_nets():
    print('(' + ','.join([repr(nn) for nn in sorted(list(short))]) + ')')

print('\nOpen nets:')
print(pformat(dict(nets_info.get_open_nets())))
```

this prints the following:

```
Nets ['SignalD', 'SignalI'] are shorted on layer (1, 0) in poly:
 [[13000.0, -3000.0],
 [16000.0, -3000.0],
 [16000.0, -1000.0],
 [13000.0, -1000.0],
 [13000.0, 2000.0],
 [12000.0, 2000.0],
 [12000.0, -1000.0],
 [11000.0, -1000.0],
 [11000.0, -3000.0],
 [12000.0, -3000.0],
 [12000.0, -8000.0],
 [13000.0, -8000.0]]
Nets ['SignalK', 'SignalK'] are shorted on layer (1, 0) in poly:
 [[18500.0, -8500.0], [28200.0, -8500.0], [28200.0, 1000.0], [18500.0, 1000.0]]
Nets ['SignalC', 'SignalC'] are shorted on layer (1, 0) in poly:
 [[10200.0, 0.0], [-1100.0, 0.0], [-1100.0, -1000.0], [10200.0, -1000.0]]
Nets ['SignalG', 'SignalH'] are shorted on layer (1, 0) in poly:
 [[10100.0, -2000.0], [5100.0, -2000.0], [5100.0, -3000.0], [10100.0, -3000.0]]

Final nets:
[SignalA, SignalC__0, SignalE, SignalG, SignalK__0, SignalK__2, SignalL]

Shorted net sets:
(SignalC__0,SignalC__1,SignalD,SignalI)
(SignalK__0,SignalK__1)
(SignalG,SignalH)
(SignalA,SignalB)
(SignalE,SignalF)

Open nets:
{'SignalK': [SignalK__0, SignalK__2]}
```

## Code organization

- The main functionality is in `trace_connectivity`.
- Useful classes, namely `NetsInfo` and `NetName`, are in `snarled.tracker`.
- `snarled.interfaces` contains helper code for interfacing with other packages.

## Caveats

This package is slow, dumb, and the code is ugly. There's only a basic test case.

If you know what you're doing, you could probably do a much better job of it.

...but you *have* heard of it :)

