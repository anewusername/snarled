"""
Main connectivity-checking functionality for `snarled`
"""
from typing import Tuple, List, Dict, Set, Optional, Union, Sequence, Mapping
from collections import defaultdict
from pprint import pformat
import logging

import numpy
from numpy.typing import NDArray, ArrayLike
from pyclipper import scale_to_clipper, scale_from_clipper, PyPolyNode

from .types import connectivity_t, layer_t, contour_t
from .poly import poly_contains_points
from .clipper import union_nonzero, union_evenodd, intersection_evenodd, hier2oriented
from .tracker import NetsInfo, NetName
from .utils import connectivity2layers


logger = logging.getLogger(__name__)


def trace_connectivity(
        polys: Mapping[layer_t, Sequence[ArrayLike]],
        labels: Mapping[layer_t, Sequence[Tuple[float, float, str]]],
        connectivity: Sequence[Tuple[layer_t, Optional[layer_t], layer_t]],
        clipper_scale_factor: int = int(2 ** 24),
        ) -> NetsInfo:
    """
    Analyze the electrical connectivity of the layout.

    This is the primary purpose of `snarled`.

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
    #
    # Figure out which layers are metals vs vias, and run initial union on each layer
    #
    metal_layers, via_layers = connectivity2layers(connectivity)

    metal_polys = {layer: union_input_polys(scale_to_clipper(polys[layer], clipper_scale_factor))
                   for layer in metal_layers}
    via_polys = {layer: union_input_polys(scale_to_clipper(polys[layer], clipper_scale_factor))
                 for layer in via_layers}

    #
    # Check each polygon for labels, and assign it to a net (possibly anonymous).
    #
    nets_info = NetsInfo()

    merge_groups: List[List[NetName]] = []
    for layer in metal_layers:
        point_xys = []
        point_names = []
        for x, y, point_name in labels[layer]:
            point_xys.append((x, y))
            point_names.append(point_name)

        for poly in metal_polys[layer]:
            found_nets = label_poly(poly, point_xys, point_names, clipper_scale_factor)

            if found_nets:
                name = NetName(found_nets[0])
            else:
                name = NetName()     # Anonymous net

            nets_info.nets[name][layer].append(poly)

            if len(found_nets) > 1:
                # Found a short
                poly = pformat(scale_from_clipper(poly.Contour, clipper_scale_factor))
                logger.warning(f'Nets {found_nets} are shorted on layer {layer} in poly:\n {poly}')
                merge_groups.append([name] + [NetName(nn) for nn in found_nets[1:]])

    #
    # Merge any nets that were shorted by having their labels on the same polygon
    #
    for group in merge_groups:
        first_net, *defunct_nets = group
        for defunct_net in defunct_nets:
            nets_info.merge(first_net, defunct_net)

    #
    # Convert to non-hierarchical polygon representation
    #
    for net in nets_info.nets.values():
        for layer in net:
            #net[layer] = union_evenodd(hier2oriented(net[layer]))
            net[layer] = hier2oriented(net[layer])

    for layer in via_polys:
        via_polys[layer] = hier2oriented(via_polys[layer])

    #
    # Figure out which nets are shorted by vias, then merge them
    #
    merge_pairs = find_merge_pairs(connectivity, nets_info.nets, via_polys)
    for net_a, net_b in merge_pairs:
        nets_info.merge(net_a, net_b)

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


def label_poly(
        poly: PyPolyNode,
        point_xys: ArrayLike,
        point_names: Sequence[str],
        clipper_scale_factor: int = int(2 ** 24),
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
        connectivity: connectivity_t,
        nets: Mapping[NetName, Mapping[layer_t, Sequence[contour_t]]],
        via_polys: Mapping[layer_t, Sequence[contour_t]],
        ) -> Set[Tuple[NetName, NetName]]:
    """
    Given a collection of (possibly anonymous) nets, figure out which pairs of
    nets are shorted through a via (and thus should be merged).

    Args:
        connectivity: A sequence of 3-tuples specifying the electrical connectivity between layers.
            Each 3-tuple looks like `(top_layer, via_layer, bottom_layer)` and indicates that
            `top_layer` and `bottom_layer` are electrically connected at any location where
            shapes are present on all three (top, via, and bottom) layers.
            `via_layer` may be `None`, in which case any overlap between shapes on `top_layer`
            and `bottom_layer` is automatically considered a short (with no third shape necessary).
        nets: A collection of all nets (seqences of polygons in mappings indexed by `NetName`
            and layer). See `NetsInfo.nets`.
        via_polys: A collection of all vias (in a mapping indexed by layer).

    Returns:
        A set containing pairs of `NetName`s for each pair of nets which are shorted.
    """
    merge_pairs = set()
    for top_layer, via_layer, bot_layer in connectivity:
        if via_layer is not None:
            vias = via_polys[via_layer]
            if not vias:
                logger.warning(f'No vias on layer {via_layer}')
                continue

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

                if via_layer is not None:
                    via_top = intersection_evenodd(top_polys, vias)
                    overlap = intersection_evenodd(via_top, bot_polys)
                else:
                    overlap = intersection_evenodd(top_polys, bot_polys)  # TODO verify there aren't any suspicious corner cases for this

                if not overlap:
                    continue

                merge_pairs.add(name_pair)
    return merge_pairs
