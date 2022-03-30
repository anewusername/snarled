from typing import Union, Tuple, List, Sequence, Optional

layer_t = Tuple[int, int]
contour_t = List[Tuple[int, int]]
connectivity_t = Sequence[Tuple[layer_t, Optional[layer_t], layer_t]]
