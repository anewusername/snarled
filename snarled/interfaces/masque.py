"""
Functionality for extracting geometry and label info from `masque` patterns.
"""
from typing import Sequence, Dict, List, Any, Tuple, Optional, Mapping
from collections import defaultdict

import numpy
from numpy.typing import NDArray
from masque import Pattern
from masque.file import oasis, gdsii
from masque.shapes import Polygon

from ..types import layer_t
from ..utils import connectivity2layers


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

    if label_mapping is None:
        label_mapping = {layer: layer for layer in metal_layers}
    label_layers = {label_layer for label_layer in label_mapping.keys()}

    cell = cell.deepcopy().subset(
        shapes_func=lambda ss: ss.layer in poly_layers,
        labels_func=lambda ll: ll.layer in label_layers,
        subpatterns_func=lambda ss: True,
        )

    # load polygons
    polys = defaultdict(list)
    for layer in poly_layers:
        shapes_hier = cell.subset(
            shapes_func=lambda ss: ss.layer == layer,
            subpatterns_func=lambda ss: True,
            )
        shapes = shapes_hier.flatten().shapes

        for ss in shapes:
            assert(isinstance(ss, Polygon))

            if ss.repetition is None:
                displacements = [(0, 0)]
            else:
                displacements = ss.repetition.displacements

            for displacement in displacements:
                polys[ss.layer].append(
                    ss.vertices + ss.offset + displacement
                    )

    # load metal labels
    metal_labels = defaultdict(list)
    for label_layer, metal_layer in label_mapping.items():
        labels_hier = cell.subset(
            labels_func=lambda ll: ll.layer == label_layer,
            subpatterns_func=lambda ss: True,
            )
        labels = labels_hier.flatten().labels

        for ll in labels:
            if ll.repetition is None:
                displacements = [(0, 0)]
            else:
                displacements = ll.repetition.displacements

            for displacement in displacements:
                offset = ll.offset + displacement
                metal_labels[metal_layer].append(
                    (*offset, ll.string)
                    )

    return polys, metal_labels
