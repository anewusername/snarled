from typing import Sequence, Dict, List, Any, Tuple, Optional, Mapping
from collections import defaultdict

import numpy
from numpy.typing import NDArray
from masque import Pattern
from masque.file import oasis, gdsii
from masque.shapes import Polygon

from ..types import layer_t
from ..utils import connectivity2layers


def read_topcell(
        topcell: Pattern,
        connectivity: Sequence[Tuple[layer_t, Optional[layer_t], layer_t]],
        label_mapping: Optional[Mapping[layer_t, layer_t]] = None,
        ) -> Tuple[
                defaultdict[layer_t, List[NDArray[numpy.float64]]],
                defaultdict[layer_t, List[Tuple[float, float, str]]]]:

    metal_layers, via_layers = connectivity2layers(connectivity)
    poly_layers = metal_layers | via_layers

    if label_mapping is None:
        label_mapping = {layer: layer for layer in metal_layers}
    label_layers = {label_layer for label_layer in label_mapping.keys()}

    topcell = topcell.deepcopy().subset(
        shapes_func=lambda ss: ss.layer in poly_layers,
        labels_func=lambda ll: ll.layer in label_layers,
        subpatterns_func=lambda ss: True,
        )
    topcell = topcell.flatten()

    polys = load_polys(topcell, list(poly_layers))

    metal_labels = defaultdict(list)
    for label_layer, metal_layer in label_mapping.items():
        labels = [ll for ll in topcell.labels if ll.layer == label_layer]
        metal_labels[metal_layer] += [(*ll.offset, ll.string) for ll in labels]

    return polys, metal_labels


def load_polys(
        topcell: Pattern,
        layers: Sequence[layer_t],
        ) -> defaultdict[layer_t, List[NDArray[numpy.float64]]]:
    polys = defaultdict(list)
    for ss in topcell.shapes:
        if ss.layer not in layers:
            continue

        assert(isinstance(ss, Polygon))

        if ss.repetition is None:
            displacements = [(0, 0)]
        else:
            displacements = ss.repetition.displacements

        for displacement in displacements:
            polys[ss.layer].append(
                ss.vertices + ss.offset + displacement
                )
    return polys
