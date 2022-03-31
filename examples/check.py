"""
Example code for checking connectivity in a layout by using
`snarled` and `masque`.
"""
from pprint import pformat

from masque.file import gdsii, oasis

import snarled
import snarled.interfaces.masque


connectivity = {
    ((1, 0), (1, 2), (2, 0)),   #M1 to M2 (via V12)
    ((1, 0), (1, 3), (3, 0)),   #M1 to M3 (via V13)
    ((2, 0), (2, 3), (3, 0)),   #M2 to M3 (via V23)
    }


#cells, props = gdsii.readfile('connectivity.gds')
cells, props = oasis.readfile('connectivity.oas')
topcell = cells['top']

polys, labels = snarled.interfaces.masque.read_cell(topcell, connectivity)
nets_info = snarled.trace_connectivity(polys, labels, connectivity)

print('\nFinal nets:')
print([kk for kk in sorted(nets_info.nets.keys()) if isinstance(kk.name, str)])

print('\nShorted net sets:')
for short in nets_info.get_shorted_nets():
    print('(' + ','.join([repr(nn) for nn in sorted(list(short))]) + ')')

print('\nOpen nets:')
print(pformat(dict(nets_info.get_open_nets())))
