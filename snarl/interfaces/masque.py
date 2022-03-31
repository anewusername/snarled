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

    This function extracts the data needed by `snarl.trace_connectivity`.

    Args:
        cell: A `masque` `Pattern` object. Usually your topcell.
        connectivity: A sequence of 3-tuples specifying the layer connectivity.
            Same as what is provided to `snarl.trace_connectivity`.
        label_mapping: A mapping of `{label_layer: metal_layer}`. This allows labels
            to refer to nets on metal layers without the labels themselves being on
            that layer.

    Returns:
        `polys` and `labels` data structures, to be passed to `snarl.trace_connectivity`.
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
    cell = cell.flatten()

    polys = load_polys(cell, list(poly_layers))

    metal_labels = defaultdict(list)
    for label_layer, metal_layer in label_mapping.items():
        labels = []
        for ll in cell.labels:
            if ll.layer != label_layer:
                continue

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


def load_polys(
        cell: Pattern,
        layers: Sequence[layer_t],
        ) -> defaultdict[layer_t, List[NDArray[numpy.float64]]]:
    """
    Given a *flat* `masque.Pattern`, extract the polygon info into the format used by `snarl`.

    Args:
        cell: The `Pattern` object to extract from.
        layers: The layers to extract.

    Returns:
        `{layer0: [poly0, [(x0, y0), (x1, y1), ...], poly2, ...]}`
        `polys` structure usable by `snarl.trace_connectivity`.
    """
    polys = defaultdict(list)
    for ss in cell.shapes:
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
