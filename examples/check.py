"""
Example code for checking connectivity in a layout by using
`snarled` and `masque`.
"""
from pprint import pformat
import logging

import snarled


logging.basicConfig()
logging.getLogger('snarled').setLevel(logging.INFO)


connectivity = [
    ((1, 0), (1, 2), (2, 0)),   #M1 to M2 (via V12)
    ((1, 0), (1, 3), (3, 0)),   #M1 to M3 (via V13)
    ((2, 0), (2, 3), (3, 0)),   #M2 to M3 (via V23)
    ]

labels_map = {
    (1, 0): (1, 0),
    (2, 0): (2, 0),
    (3, 0): (3, 0),
    }

filename = 'connectivity.oas'

result = snarled.trace_layout(filename, connectivity, topcell='top', labels_map=labels_map)

print('Result:\n', pformat(result))
