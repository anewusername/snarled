from typing import Union, Tuple, List, Sequence, Optional

layer_t = Tuple[int, int]
contour_t = List[Tuple[int, int]]
net_name_t = Union[str, object]
connectivity_t = Sequence[Tuple[layer_t, Optional[layer_t], layer_t]]
