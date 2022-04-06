"""
Functionality for extracting geometry and label info from `masque` patterns.
"""
from typing import Sequence, Dict, List, Any, Tuple, Optional, Mapping, Callable
from collections import defaultdict

import numpy
from numpy.typing import NDArray
from masque import Pattern
from masque.file import oasis, gdsii
from masque.shapes import Polygon

from ..types import layer_t
from ..utils import connectivity2layers


def prepare_cell(
        cell: Pattern,
        label_mapping: Optional[Mapping[layer_t, layer_t]] = None,
        ) -> Callable[[layer_t], Tuple[
            List[NDArray[numpy.float64]],
            List[Tuple[float, float, str]]
            ]]:
    """
    Generate a function for extracting `polys` and `labels` from a `masque.Pattern`.
    The returned function can be passed to `snarled.trace_connectivity`.

    Args:
        cell: A `masque` `Pattern` object. Usually your topcell.
        label_mapping: A mapping of `{label_layer: metal_layer}`. This allows labels
            to refer to nets on metal layers without the labels themselves being on
            that layer.
            Default `None` reads labels from the same layer as the geometry.

    Returns:
        `get_layer` function, to be passed to `snarled.trace_connectivity`.
    """

    def get_layer(
            layer: layer_t,
            ) -> Tuple[
                List[NDArray[numpy.float64]],
                List[Tuple[float, float, str]]
                ]:

        if label_mapping is None:
            label_layers = {layer: layer}
        else:
            label_layers = {label_layer for label_layer, metal_layer in label_mapping.items()
                            if metal_layer == layer}

        subset = cell.deepcopy().subset(          # TODO add single-op subset-and-copy, to avoid copying unwanted stuff
            shapes_func=lambda ss: ss.layer == layer,
            labels_func=lambda ll: ll.layer in label_layers,
            subpatterns_func=lambda ss: True,
            recursive=True,
            )

        polygonized = subset.polygonize()       # Polygonize Path shapes
        flat = polygonized.flatten()

        # load polygons
        polys = []
        for ss in flat.shapes:
            assert(isinstance(ss, Polygon))

            if ss.repetition is None:
                displacements = [(0, 0)]
            else:
                displacements = ss.repetition.displacements

            for displacement in displacements:
                polys.append(
                    ss.vertices + ss.offset + displacement
                    )

        # load metal labels
        labels = []
        for ll in flat.labels:
            if ll.repetition is None:
                displacements = [(0, 0)]
            else:
                displacements = ll.repetition.displacements

            for displacement in displacements:
                offset = ll.offset + displacement
                labels.append((*offset, ll.string))

        return polys, labels
    return get_layer


def read_cell(
        cell: Pattern,
        connectivity: Sequence[Tuple[layer_t, Optional[layer_t], layer_t]],
        label_mapping: Optional[Mapping[layer_t, layer_t]] = None,
        ) -> Tuple[
                defaultdict[layer_t, List[NDArray[numpy.float64]]],
                defaultdict[layer_t, List[Tuple[float, float, str]]]]:
    """
    Extract `polys` and `labels` from a `masque.Pattern`.

    This function extracts the data needed by `snarled.trace_connectivity`.

    Args:
        cell: A `masque` `Pattern` object. Usually your topcell.
        connectivity: A sequence of 3-tuples specifying the layer connectivity.
            Same as what is provided to `snarled.trace_connectivity`.
        label_mapping: A mapping of `{label_layer: metal_layer}`. This allows labels
            to refer to nets on metal layers without the labels themselves being on
            that layer.

    Returns:
        `polys` and `labels` data structures, to be passed to `snarled.trace_connectivity`.
    """

    metal_layers, via_layers = connectivity2layers(connectivity)
    poly_layers = metal_layers | via_layers

    get_layer = prepare_cell(cell, label_mapping)

    polys = defaultdict(list)
    labels = defaultdict(list)
    for layer in poly_layers:
        polys[layer], labels[layer] = get_layer(layer)

    return polys, labels
