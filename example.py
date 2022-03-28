from masque.file import gdsii, oasis

import snarl
import snarl.interfaces.masque


connectivity = {
    ((1, 0), (1, 2), (2, 0)),   #M1 to M2 (via V12)
    ((1, 0), (1, 3), (3, 0)),   #M1 to M3 (via V13)
    ((2, 0), (2, 3), (3, 0)),   #M2 to M3 (via V23)
    }


#cells, props = gdsii.readfile('connectivity.gds')
cells, props = oasis.readfile('connectivity.oas')
topcell = cells['top']

polys, labels = snarl.interfaces.masque.read_topcell(topcell, connectivity)
nets_info = snarl.check_connectivity(polys, labels, connectivity)

