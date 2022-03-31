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

    metal_layers, via_layers = connectivity2layers(connectivity)

    metal_polys = {layer: union_input_polys(scale_to_clipper(polys[layer], clipper_scale_factor))
                   for layer in metal_layers}
    via_polys = {layer: union_input_polys(scale_to_clipper(polys[layer], clipper_scale_factor))
                 for layer in via_layers}

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

            name: Optional[str]
            if found_nets:
                name = NetName(found_nets[0])
            else:
                name = NetName()     # Anonymous net

            nets_info.nets[name][layer].append(poly)

            if len(found_nets) > 1:
                # Found a short
                logger.warning(f'Nets {found_nets} are shorted on layer {layer} in poly:\n {pformat(poly)}')
                merge_groups.append([name] + [NetName(nn) for nn in found_nets[1:]])

    for group in merge_groups:
        first_net, *defunct_nets = group
        for defunct_net in defunct_nets:
            nets_info.merge(first_net, defunct_net)

    #
    #   Take EVENODD union within each net
    #   & stay in EVENODD-friendly representation
    #
    for net in nets_info.nets.values():
        for layer in net:
            #net[layer] = union_evenodd(hier2oriented(net[layer]))
            net[layer] = hier2oriented(net[layer])

    for layer in via_polys:
        via_polys[layer] = hier2oriented(via_polys[layer])


    merge_pairs = find_merge_pairs(connectivity, nets_info.nets, via_polys)
    for net_a, net_b in merge_pairs:
        nets_info.merge(net_a, net_b)

    return nets_info


def union_input_polys(polys: List[ArrayLike]) -> List[PyPolyNode]:
    for poly in polys:
        if (numpy.abs(poly) % 1).any():
            logger.warning('Warning: union_polys got non-integer coordinates; all values will be truncated.')
            break

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
    #
    #   Merge nets based on via connectivity
    #
    merge_pairs = set()
    for top_layer, via_layer, bot_layer in connectivity:
        if via_layer is not None:
            vias = via_polys[via_layer]
            if not vias:
                continue

        for top_name in nets.keys():
            top_polys = nets[top_name][top_layer]
            if not top_polys:
                continue

            for bot_name in nets.keys():
                if bot_name == top_name:
                    continue
                name_pair = tuple(sorted((top_name, bot_name)))
                if name_pair in merge_pairs:
                    continue

                bot_polys = nets[bot_name][bot_layer]
                if not bot_polys:
                    continue

                if via_layer is not None:
                    via_top = intersection_evenodd(top_polys, vias)
                    overlap = intersection_evenodd(via_top, bot_polys)
                else:
                    overlap = intersection_evenodd(top_polys, bot_polys)        # TODO verify there aren't any suspicious corner cases for this

                if not overlap:
                    continue

                merge_pairs.add(name_pair)
    return merge_pairs
