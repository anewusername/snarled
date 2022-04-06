"""
Main connectivity-checking functionality for `snarled`
"""
from typing import Tuple, List, Dict, Set, Optional, Union, Sequence, Mapping, Callable
from collections import defaultdict
from pprint import pformat
import logging

import numpy
from numpy.typing import NDArray, ArrayLike
from pyclipper import scale_to_clipper, scale_from_clipper, PyPolyNode

from .types import connectivity_t, layer_t, contour_t
from .poly import poly_contains_points
from .clipper import union_nonzero, union_evenodd, intersection_evenodd, difference_evenodd, hier2oriented
from .tracker import NetsInfo, NetName
from .utils import connectivity2layers


logger = logging.getLogger(__name__)


def trace_connectivity_preloaded(
        polys: Mapping[layer_t, Sequence[ArrayLike]],
        labels: Mapping[layer_t, Sequence[Tuple[float, float, str]]],
        connectivity: Sequence[Tuple[layer_t, Optional[layer_t], layer_t]],
        clipper_scale_factor: int = int(2 ** 24),
        ) -> NetsInfo:
    """
    Analyze the electrical connectivity of the provided layout.

    The resulting `NetsInfo` will contain only disjoint `nets`, and its `net_aliases` can be used to
    understand which nets are shorted (and therefore known by more than one name).

    Args:
        polys: A full description of all conducting paths in the layout. Consists of lists of polygons
            (Nx2 arrays of vertices), indexed by layer. The structure looks roughly like
            `{layer0: [poly0, poly1, ..., [(x0, y0), (x1, y1), ...]], ...}`
        labels: A list of "named points" which are used to assign names to the nets they touch.
            A collection of lists of (x, y, name) tuples, indexed *by the layer they target*.
            `{layer0: [(x0, y0, name0), (x1, y1, name1), ...], ...}`
        connectivity: A sequence of 3-tuples specifying the electrical connectivity between layers.
            Each 3-tuple looks like `(top_layer, via_layer, bottom_layer)` and indicates that
            `top_layer` and `bottom_layer` are electrically connected at any location where
            shapes are present on all three (top, via, and bottom) layers.
            `via_layer` may be `None`, in which case any overlap between shapes on `top_layer`
            and `bottom_layer` is automatically considered a short (with no third shape necessary).
        clipper_scale_factor: `pyclipper` uses 64-bit integer math, while we accept either floats or ints.
            The coordinates from `polys` are scaled by this factor to put them roughly in the middle of
            the range `pyclipper` wants; you may need to adjust this if you are already using coordinates
            with large integer values.

    Returns:
        `NetsInfo` object describing the various nets and their connectivities.
    """
    def get_layer(layer: layer_t) -> Tuple[Sequence[ArrayLike], Sequence[Tuple[float, float, str]]]:
        return polys[layer], labels[layer]

    return trace_connectivity(get_layer, connectivity, clipper_scale_factor)


def trace_connectivity(
        get_layer: Callable[[layer_t], Tuple[Sequence[ArrayLike], Sequence[Tuple[float, float, str]]]],
        connectivity: Sequence[Tuple[layer_t, Optional[layer_t], layer_t]],
        clipper_scale_factor: int = int(2 ** 24),
        ) -> NetsInfo:
    """
    Analyze the electrical connectivity of a layout.

    The resulting `NetsInfo` will contain only disjoint `nets`, and its `net_aliases` can be used to
    understand which nets are shorted (and therefore known by more than one name).

    This function attempts to reduce memory usage by lazy-loading layout data (layer-by-layer) and
    pruning away layers for which all interactions have already been computed.
    TODO: In the future, this will be extended to cover partial loading of spatial extents in
          addition to layers.

    Args:
        get_layer: When called, `polys, labels = get_layer(layer)` should return the geometry and labels
            on that layer. Returns

            polys, A list of polygons (Nx2 arrays of vertices) on the layer. The structure looks like
                `[poly0, poly1, ..., [(x0, y0), (x1, y1), ...]]`

            labels, A list of "named points" which are used to assign names to the nets they touch.
                A list of (x, y, name) tuples targetting this layer.
                `[(x0, y0, name0), (x1, y1, name1), ...]`

        connectivity: A sequence of 3-tuples specifying the electrical connectivity between layers.

            Each 3-tuple looks like `(top_layer, via_layer, bottom_layer)` and indicates that
            `top_layer` and `bottom_layer` are electrically connected at any location where
            shapes are present on all three (top, via, and bottom) layers.

            `via_layer` may be `None`, in which case any overlap between shapes on `top_layer`
            and `bottom_layer` is automatically considered a short (with no third shape necessary).

            NOTE that the order in which connectivity is specified (i.e. top-level ordering of the
            tuples) directly sets the order in which the layers are loaded and merged, and thus
            has a significant impact on memory usage by determining when layers can be pruned away.
            Try to group entries by the layers they affect!

        clipper_scale_factor: `pyclipper` uses 64-bit integer math, while we accept either floats or ints.
            The coordinates from `polys` are scaled by this factor to put them roughly in the middle of
            the range `pyclipper` wants; you may need to adjust this if you are already using coordinates
            with large integer values.

    Returns:
        `NetsInfo` object describing the various nets and their connectivities.
    """
    loaded_layers = set()
    nets_info = NetsInfo()

    for ii, (top_layer, via_layer, bot_layer) in enumerate(connectivity):
        for metal_layer in (top_layer, bot_layer):
            if metal_layer in loaded_layers:
                continue
            # Load and run initial union on each layer
            raw_polys, labels = get_layer(metal_layer)
            polys = union_input_polys(scale_to_clipper(raw_polys, clipper_scale_factor))

            # Check each polygon for labels, and assign it to a net (possibly anonymous).
            nets_on_layer, merge_groups = label_polys(polys, labels, clipper_scale_factor)
            for name, net_polys in nets_on_layer.items():
                nets_info.nets[name][metal_layer] += hier2oriented(net_polys)

            # Merge any nets that were shorted by having their labels on the same polygon
            for group in merge_groups:
                net_names = set(nn.name for nn in group)
                if len(net_names) > 1:
                    logger.warning(f'Nets {net_names} are shorted on layer {metal_layer}')
                first_net, *defunct_nets = group
                for defunct_net in defunct_nets:
                    nets_info.merge(first_net, defunct_net)

            loaded_layers.add(metal_layer)

        # Load and union vias
        via_raw_polys, _labels = get_layer(via_layer)
        via_polys = hier2oriented(union_input_polys(
            scale_to_clipper(via_raw_polys, clipper_scale_factor)
            ))

        # Figure out which nets are shorted by vias, then merge them
        merge_pairs = find_merge_pairs(nets_info.nets, top_layer, bot_layer, via_polys)
        for net_a, net_b in merge_pairs:
            nets_info.merge(net_a, net_b)


        remaining_layers = set()
        for layer_a, _, layer_b in connectivity[ii + 1:]:
            remaining_layers.add(layer_a)
            remaining_layers.add(layer_b)

        finished_layers = loaded_layers - remaining_layers
        for layer in finished_layers:
            nets_info.prune(layer)

    return nets_info


def union_input_polys(polys: Sequence[ArrayLike]) -> List[PyPolyNode]:
    """
    Perform a union operation on the provided sequence of polygons, and return
    a list of `PyPolyNode`s corresponding to all of the outer (i.e. non-hole)
    contours.

    Note that while islands are "outer" contours and returned in the list, they
    also are still available through the `.Childs` property of the "hole" they
    appear in. Meanwhile, "hole" contours are only accessible through the `.Childs`
    property of their parent "outer" contour, and are not returned in the list.

    Args:
        polys: A sequence of polygons, `[[(x0, y0), (x1, y1), ...], poly1, poly2, ...]`
            Polygons may be implicitly closed.

    Returns:
        List of PyPolyNodes, representing all "outer" contours (including islands) in
        the union of `polys`.
    """
    for poly in polys:
        if (numpy.abs(poly) % 1).any():
            logger.warning('Warning: union_polys got non-integer coordinates; all values will be truncated.')
            break

    #TODO: check if we need to reverse the order of points in some polygons
    #       via sum((x2-x1)(y2+y1)) (-ve means ccw)

    poly_tree = union_nonzero(polys)
    if poly_tree is None:
        return []

    # Partially flatten the tree, reclassifying all the "outer" (non-hole) nodes as new root nodes
    unvisited_nodes = [poly_tree]
    outer_nodes = []
    while unvisited_nodes:
        node = unvisited_nodes.pop()    # node will be the tree parent node (a container), or a hole
        for poly in node.Childs:
            outer_nodes.append(poly)
            for hole in poly.Childs:            # type: ignore
                unvisited_nodes.append(hole)

    return outer_nodes

def label_polys(
        polys: Sequence[PyPolyNode],
        labels: Sequence[Tuple[float, float, str]],
        clipper_scale_factor: int,
        ) -> Tuple[
            defaultdict[NetName, List[PyPolyNode]],
            List[List[NetName]]
            ]:
    merge_groups = []
    point_xys = []
    point_names = []
    nets = defaultdict(list)
    for x, y, point_name in labels:
        point_xys.append((x, y))
        point_names.append(point_name)

    for poly in polys:
        found_nets = label_poly(poly, point_xys, point_names, clipper_scale_factor)

        if found_nets:
            name = NetName(found_nets[0])
        else:
            name = NetName()     # Anonymous net

        nets[name].append(poly)

        if len(found_nets) > 1:
            # Found a short
            poly = pformat(scale_from_clipper(poly.Contour, clipper_scale_factor))
            merge_groups.append([name] + [NetName(nn) for nn in found_nets[1:]])
    return nets, merge_groups


def label_poly(
        poly: PyPolyNode,
        point_xys: ArrayLike,
        point_names: Sequence[str],
        clipper_scale_factor: int,
        ) -> List[str]:
    """
    Given a `PyPolyNode` (a polygon, possibly with holes) and a sequence of named points,
    return the list of point names contained inside the polygon.

    Args:
        poly: A polygon, possibly with holes. "Islands" inside the holes (and deeper-nested
            structures) are not considered (i.e. only one non-hole contour is considered).
        point_xys: A sequence of point coordinates (Nx2, `[(x0, y0), (x1, y1), ...]`).
        point_names: A sequence of point names (same length N as point_xys)
        clipper_scale_factor: The PyPolyNode structure is from `pyclipper` and likely has
            a scale factor applied in order to use integer arithmetic. Due to precision
            limitations in `poly_contains_points`, it's prefereable to undo this scaling
            rather than asking for similarly-scaled `point_xys` coordinates.
            NOTE: This could be fixed by using `numpy.longdouble` in
            `poly_contains_points`, but the exact length of long-doubles is platform-
            dependent and so probably best avoided.

    Result:
        All the `point_names` which correspond to points inside the polygon (but not in
        its holes).
    """
    poly_contour = scale_from_clipper(poly.Contour, clipper_scale_factor)
    inside = poly_contains_points(poly_contour, point_xys)
    for hole in poly.Childs:
        hole_contour = scale_from_clipper(hole.Contour, clipper_scale_factor)
        inside &= ~poly_contains_points(hole_contour, point_xys)

    inside_nets = sorted([net_name for net_name, ii in zip(point_names, inside) if ii])

    if inside.any():
        return inside_nets
    else:
        return []


def find_merge_pairs(
        nets: Mapping[NetName, Mapping[layer_t, Sequence[contour_t]]],
        top_layer: layer_t,
        bot_layer: layer_t,
        via_polys: Optional[Sequence[contour_t]],
        ) -> Set[Tuple[NetName, NetName]]:
    """
    Given a collection of (possibly anonymous) nets, figure out which pairs of
    nets are shorted through a via (and thus should be merged).

    Args:
        nets: A collection of all nets (seqences of polygons in mappings indexed by `NetName`
            and layer). See `NetsInfo.nets`.
        top_layer: Layer name of first layer
        bot_layer: Layer name of second layer
        via_polys: Sequence of via contours. `None` denotes to vias necessary (overlap is sufficent).

    Returns:
        A set containing pairs of `NetName`s for each pair of nets which are shorted.
    """
    merge_pairs = set()
    if via_polys is not None and not via_polys:
        logger.warning(f'No vias between layers {top_layer}, {bot_layer}')
        return merge_pairs

    for top_name in nets.keys():
        top_polys = nets[top_name][top_layer]
        if not top_polys:
            continue

        for bot_name in nets.keys():
            if bot_name == top_name:
                continue

            name_pair: Tuple[NetName, NetName] = tuple(sorted((top_name, bot_name)))  #type: ignore
            if name_pair in merge_pairs:
                continue

            bot_polys = nets[bot_name][bot_layer]
            if not bot_polys:
                continue

            if via_polys is not None:
                top_bot = intersection_evenodd(top_polys, bot_polys)
                overlap = intersection_evenodd(top_bot, via_polys)
                via_polys = difference_evenodd(via_polys, overlap)      # reduce set of via polys for future nets
            else:
                overlap = intersection_evenodd(top_polys, bot_polys)  # TODO verify there aren't any suspicious corner cases for this

            if overlap:
                merge_pairs.add(name_pair)

    return merge_pairs
