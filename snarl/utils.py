from typing import Set, Tuple

from .types import connectivity_t, layer_t


def connectivity2layers(
        connectivity: connectivity_t,
        ) -> Tuple[Set[layer_t], Set[layer_t]]:
    metal_layers = set()
    via_layers = set()
    for top, via, bot in connectivity:
        metal_layers.add(top)
        metal_layers.add(bot)
        if via is not None:
            via_layers.add(via)

    # TODO verify no overlap between metal and via layer specifications

    return metal_layers, via_layers
