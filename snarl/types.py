from typing import Union, Tuple, List, Sequence, Optional, Hashable

layer_t = Hashable
contour_t = List[Tuple[int, int]]
connectivity_t = Sequence[Tuple[layer_t, Optional[layer_t], layer_t]]
