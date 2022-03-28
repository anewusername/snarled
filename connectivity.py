from typing import Tuple, List, Dict, Set, Optional, Union, Sequence
from collections import defaultdict
from pprint import pformat
import logging

import numpy
from numpy.typing import NDArray, ArrayLike
import pyclipper
from pyclipper import (
    Pyclipper, PT_CLIP, PT_SUBJECT, CT_UNION, CT_INTERSECTION, PFT_NONZERO, PFT_EVENODD,
    scale_to_clipper, scale_from_clipper, PyPolyNode,
    )
from masque.file import oasis, gdsii

from masque import Pattern
from masque.shapes import Polygon
from .poly import poly_contains_points


logger = logging.getLogger(__name__)


layer_t = Tuple[int, int]
contour_t = List[Tuple[int, int]]
net_name_t = Union[str, object]


CLIPPER_SCALE_FACTOR = 2**24




def union_nonzero(shapes: Sequence[ArrayLike]) -> Optional[PyPolyNode]:
    if not shapes:
        return None
    pc = Pyclipper()
    pc.AddPaths(shapes, PT_CLIP, closed=True)
    result = pc.Execute2(CT_UNION, PFT_NONZERO, PFT_NONZERO)
    return result


def union_evenodd(shapes: Sequence[ArrayLike]) -> List[contour_t]:
    if not shapes:
        return []
    pc = Pyclipper()
    pc.AddPaths(shapes, PT_CLIP, closed=True)
    return pc.Execute(CT_UNION, PFT_EVENODD, PFT_EVENODD)


def intersection_evenodd(
        subject_shapes: Sequence[ArrayLike],
        clip_shapes: Sequence[ArrayLike],
        clip_closed: bool = True,
        ) -> List[contour_t]:
    if not subject_shapes or not clip_shapes:
        return []
    pc = Pyclipper()
    pc.AddPaths(subject_shapes, PT_SUBJECT, closed=True)
    pc.AddPaths(clip_shapes, PT_CLIP, closed=clip_closed)
    return pc.Execute(CT_INTERSECTION, PFT_EVENODD, PFT_EVENODD)


class NetsInfo:
    nets: defaultdict[str, defaultdict[layer_t, List]]
    net_aliases: defaultdict[str, List]

    def __init__(self) -> None:
        self.nets = defaultdict(lambda: defaultdict(list))
        self.net_aliases = defaultdict(list)

    def resolve_name(self, net_name: net_name_t) -> net_name_t:
        while net_name in self.net_aliases:
            net_name = self.net_aliases[net_name]
        return net_name

    def merge(self, net_a: net_name_t, net_b: net_name_t) -> None:
        net_a = self.resolve_name(net_a)
        net_b = self.resolve_name(net_b)

        # Always keep named nets if the other is anonymous
        if not isinstance(net_a, str) and isinstance(net_b, str):
            keep_net, old_net = net_b, net_a
        else:
            keep_net, old_net = net_a, net_b

        #logger.info(f'merging {old_net} into {keep_net}')
        self.net_aliases[old_net] = keep_net
        if old_net in self.nets:
            for layer in self.nets[old_net]:
                self.nets[keep_net][layer] += self.nets[old_net][layer]
            del self.nets[old_net]

    def get(self, net: net_name_t, layer: layer_t) -> List[contour_t]:
        return self.nets[self.resolve_name(net)][layer]

    def get_shorted_nets(self) -> List[Set[str]]:
        shorts = defaultdict(list)
        for kk in self.net_aliases:
            if isinstance(kk, str):
                shorts[self.resolve_name(kk)].append(kk)

        shorted_sets = [set([kk] + others)
                        for kk, others in shorts.items()]
        return shorted_sets


def load_polys(layers: Sequence[Tuple[int, int]]) -> Dict[layer_t, List[NDArray[numpy.float64]]]:
    polys = defaultdict(list)
    for ss in topcell.shapes:
        if ss.layer not in layers:
            continue

        if ss.repetition is None:
            displacements = [(0, 0)]
        else:
            displacements = ss.repetition.displacements

        for displacement in displacements:
            polys[ss.layer].append(
                ss.vertices + ss.offset + displacement
                )
    return dict(polys)


def union_polys(polys: list[ArrayLike]) -> List[PyPolyNode]:
    scaled_polys = scale_to_clipper(polys, CLIPPER_SCALE_FACTOR)
    for poly in scaled_polys:
        if (numpy.abs(poly) % 1).any():
            logger.warning('Warning: union_polys got non-integer coordinates; all values will be truncated.')
            break

    poly_tree = union_nonzero(scaled_polys)

    # Partially flatten the tree, reclassifying all the "outer" (non-hole) nodes as new root nodes
    unvisited_nodes = [poly_tree]
    outer_nodes = []
    while unvisited_nodes:
        node = unvisited_nodes.pop()    # node will be the tree parent node (a container), or a hole
        for poly in node.Childs:
            outer_nodes.append(poly)
            for hole in poly.Childs:
                unvisited_nodes.append(hole)

    return outer_nodes



cells, props = oasis.readfile('connectivity.oas')
#cells, props = gdsii.readfile('connectivity.gds')
topcell = cells['top']


layer_info = {
    ((1, 0), (1, 2), (2, 0)),   #M1 to M2
    ((1, 0), (1, 3), (3, 0)),   #M1 to M3
    ((2, 0), (2, 3), (3, 0)),   #M2 to M3
    }

metal_layers = set()
via_layers = set()
for top, via, bot in layer_info:
    metal_layers.add(top)
    metal_layers.add(bot)
    via_layers.add(via)


topcell = topcell.subset(
    shapes_func=lambda ss: ss.layer in metal_layers | via_layers,
    labels_func=lambda ll: ll.layer in metal_layers,
    subpatterns_func=lambda ss: True,
    )
topcell = topcell.flatten()


base_metal_polys = load_polys(metal_layers)
metal_polys = {layer: union_polys(base_metal_polys[layer])
               for layer in metal_layers}

base_via_polys = load_polys(via_layers)
via_polys = {layer: union_polys(base_via_polys[layer])
             for layer in via_layers}

## write out polys to gds
#pat = Pattern('metal_polys')
#for layer in metal_polys:
#    for poly in metal_polys[layer]:
#        pat.shapes.append(Polygon(layer=layer, vertices=scale_from_clipper(poly.Contour, CLIPPER_SCALE_FACTOR)))
#        for hole in poly.Childs:
#            pat.shapes.append(Polygon(layer=(layer[0], layer[1] + 10), vertices=scale_from_clipper(hole.Contour, CLIPPER_SCALE_FACTOR)))
#for layer in via_polys:
#    for poly in via_polys[layer]:
#        pat.shapes.append(Polygon(layer=layer, vertices=scale_from_clipper(poly.Contour, CLIPPER_SCALE_FACTOR)))
#        for hole in poly.Childs:
#            pat.shapes.append(Polygon(layer=(layer[0], layer[1] + 10), vertices=scale_from_clipper(hole.Contour, CLIPPER_SCALE_FACTOR)))
#gdsii.writefile(pat, '_polys.gds', 1e-9, 1e-6)


net_info = NetsInfo()



def label_nets(
        net_info: NetsInfo,
        polys: Sequence[PyPolyNode],
        point_xys: ArrayLike,
        point_names: Sequence[str],
        ):
    for poly in polys:
        poly_contour = scale_from_clipper(poly.Contour, CLIPPER_SCALE_FACTOR)
        inside = poly_contains_points(poly_contour, point_xys)
        for hole in poly.Childs:
            hole_contour = scale_from_clipper(hole.Contour, CLIPPER_SCALE_FACTOR)
            inside &= ~poly_contains_points(hole_contour, point_xys)

        inside_nets = sorted([net_name for net_name, ii in zip(point_names, inside) if ii])

        if not inside.any():
            # No labels in this net, so it's anonymous
            name = object()
            net_info.nets[name][layer].append(poly)
            continue

        net_info.get(inside_nets[0], layer).append(poly)

        if inside.sum() == 1:
            # No short on this layer, continue
            continue

        logger.warning(f'Nets {inside_nets} are shorted on layer {layer} in poly:\n {pformat(poly)}')
        first_net, *defunct_nets = inside_nets
        for defunct_net in defunct_nets:
            net_info.merge(first_net, defunct_net)

    contours = []


def tree2oriented(polys: Sequence[PyPolyNode]) -> List[ArrayLike]:
    contours = []
    for poly in polys:
        contours.append(poly.Contour)
        contours += [hole.Contour for hole in poly.Childs]

    return union_evenodd(contours)


for layer in metal_layers:
    labels = sorted([ll for ll in topcell.labels if ll.layer == layer], key=lambda ll: ll.string)
    point_xys = [ll.offset for ll in labels]
    point_names = [ll.string for ll in labels]
    label_nets(net_info, metal_polys[layer], point_xys, point_names)

#
#   Take EVENODD union within each net
#   & stay in EVENODD-friendly representation
#
for net in net_info.nets.values():
    for layer in net:
        net[layer] = tree2oriented(net[layer])

for layer in via_polys:
    via_polys[layer] = tree2oriented(via_polys[layer])

## write out nets to gds
#pat = Pattern('nets')
#for name, net in net_info.nets.items():
#    sub = Pattern(str(name))
#    for layer in net:
#        print('aaaaaa', layer)
#        for poly in net[layer]:
#            sub.shapes.append(Polygon(layer=layer, vertices=scale_from_clipper(poly, CLIPPER_SCALE_FACTOR)))
#    pat.addsp(sub)
#gdsii.writefile(pat, '_nets.gds', 1e-9, 1e-6)


#
#   Merge nets based on via connectivity
#
merge_pairs = set()
for top_layer, via_layer, bot_layer in layer_info:
    vias = via_polys[via_layer]
    if not vias:
        continue

    #TODO deal with polygons that have holes (loops?)

    for top_name in net_info.nets.keys():
        top_polys = net_info.nets[top_name][top_layer]
        if not top_polys:
            continue

        for bot_name in net_info.nets.keys():
            if bot_name == top_name:
                continue
            name_pair = tuple(sorted((top_name, bot_name), key=lambda s: id(s)))
            if name_pair in merge_pairs:
                continue

            bot_polys = net_info.nets[bot_name][bot_layer]
            if not bot_polys:
                continue

            via_top = intersection_evenodd(top_polys, vias)
            overlap = intersection_evenodd(via_top, bot_polys)

            if not overlap:
                continue

            if isinstance(bot_name, str) and isinstance(top_name, str):
                logger.warning(f'Nets {top_name} and {bot_name} are shorted with via layer {via_layer} at:\n {pformat(scale_from_clipper(overlap[0], CLIPPER_SCALE_FACTOR))}')
            merge_pairs.add(name_pair)

for net_a, net_b in merge_pairs:
    net_info.merge(net_a, net_b)


print('merged pairs')
print(pformat(merge_pairs))


print('\nFinal nets:')
print([kk for kk in net_info.nets if isinstance(kk, str)])


print('\nNet sets:')
for short in net_info.get_shorted_nets():
    print('(' + ','.join(sorted(list(short))) + ')')
