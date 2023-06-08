from typing import Sequence, Callable
import logging
from collections import Counter
from dataclasses import dataclass
from itertools import chain

from klayout import db
from .types import lnum_t, layer_t


logger = logging.getLogger(__name__)


def get_topcell(
        layout: db.Layout,
        name: str | None = None,
        ) -> db.Cell:
    if name is None:
        return layout.top_cell()
    else:
        ind = layout.cell_by_name(name)
        return layout.cell(ind)


def write_net_layout(
        l2n: db.LayoutToNetlist,
        filepath: str,
        layers: Sequence[lnum_t],
        ) -> None:
    layout = db.Layout()
    top = layout.create_cell('top')
    lmap = {layout.layer(*layer) for layer in layers}
    l2n.build_all_nets(l2n.cell_mapping_into(ly, top), ly, lmap, 'net_', 'prop_', l2n.BNH_Flatten, 'circuit_')
    layout.write(filepath)


def merge_labels_from(
        filepath: str,
        into_layout: db.Layout,
        lnum_map: dict[lnum_t, lnum_t],
        topcell: str | None = None,
        ) -> None:
    layout = db.Layout()
    lm = layout.read(filepath)

    topcell_obj = get_topcell(layout, topcell)

    for labels_layer, conductor_layer in lnum_map:
        layer_ind_src = layout.layer(*labels_layer)
        layer_ind_dst = into_layout.layer(*conductor_layer)

        shapes_dst = topcell_obj.shapes(layer_ind_dst)
        shapes_src = topcell_obj.shapes(layer_ind_src)
        for shape in shapes_dst.each():
            new_shape = shapes_dst.insert(shape)
            shapes_dst.replace_prop_id(new_shape, 0)        # clear shape properties


@dataclass
class TraceResult:
    shorts: list[str]
    opens: list[str]
    nets: list[set[str]]


def trace_layout(
        filepath: str,
        connectivity: list[layer_t, layer_t | None, layer_t],
        layer_map: dict[str, lnum_t] | None = None,
        topcell: str | None = None,
        *,
        labels_map: dict[layer_t, layer_t] = {},
        lfile_path: str | None = None,
        lfile_map: dict[layer_t, layer_t] | None = None,
        lfile_layer_map: dict[str, lnum_t] | None = None,
        lfile_topcell: str | None = None,
        output_path: str | None = None,
        parse_label: Callable[[str], str] | None = None,
        ) -> TraceResult:
    if layer_map is None:
        layer_map = {}

    if parse_label is None:
        def parse_label(label: str) -> str:
            return label

    layout = db.Layout()
    lm = layout.read(filepath)

    topcell_obj = get_topcell(layout, topcell)

    # Merge labels from a separate layout if asked
    if lfile_path:
        if not lfile_map:
            raise Exception('Asked to load labels from a separate file, but no '
                            'label layers were specified in lfile_map')

        if lfile_layer_map is None:
            lfile_layer_map = layer_map

        lnum_map = {}
        for ltext, lshape in lfile_map.items():
            if isinstance(ltext, str):
                ltext = lfile_layer_map[ltext]
            if isinstance(lshape, str):
                lshape = layer_map[lshape]
            lnum_map[ltext] = lshape

        merge_labels_from(lfile_path, layout, lnum_map, lfile_topcell)

    #
    # Build a netlist from the layout
    #
    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, topcell_obj, []))
    #l2n.include_floating_subcircuits = True

    # Create l2n polygon layers
    layer2polys = {}
    for layer in set(chain(*connectivity)):
        if isinstance(layer, str):
            layer = layer_map[layer]
        klayer = layout.layer(*layer)
        layer2polys[layer] = l2n.make_polygon_layer(klayer)

    # Create l2n text layers
    layer2texts = {}
    for layer in labels_map.keys():
        if isinstance(layer, str):
            layer = layer_map[layer]
        klayer = layout.layer(*layer)
        texts = l2n.make_text_layer(klayer)
        texts.flatten()
        layer2texts[layer] = texts

    # Connect each layer to itself
    for name, polys in layer2polys.items():
        logger.info(f'Adding layer {name}')
        l2n.connect(polys)

    # Connect layers, optionally with vias
    for top, via, bot in connectivity:
        if isinstance(top, str):
            top = layer_map[top]
        if isinstance(via, str):
            via = layer_map[via]
        if isinstance(top, str):
            bot = layer_map[bot]

        if via is None:
            l2n.connect(layer2polys[top], layer2polys[bot])
        else:
            l2n.connect(layer2polys[top], layer2polys[via])
            l2n.connect(layer2polys[bot], layer2polys[via])

    # Label nets
    for label_layer, metal_layer in labels_map.items():
        if isinstance(label_layer, str):
            label_layer = layer_map[label_layer]
        if isinstance(metal_layer, str):
            metal_layer = layer_map[metal_layer]

        l2n.connect(layer2polys[metal_layer], layer2texts[label_layer])

    # Get netlist
    nle = l2n.extract_netlist()
    nl = l2n.netlist()
    nl.make_top_level_pins()

    if output_path:
        write_net_layout(l2n, output_path, layer2polys.keys())

    #
    # Analyze traced nets
    #
    top_circuits = [cc for cc, _ in zip(nl.each_circuit_top_down(), range(nl.top_circuit_count()))]

    # Nets with more than one label get their labels joined with a comma
    nets = [
        {parse_label(ll) for ll in nn.name.split(',')}
        for cc in top_circuits
        for nn in cc.each_net()
        if nn.name
        ]
    nets2 = [
        nn.name
        for cc in top_circuits
        for nn in cc.each_net()
        ]
    print(nets2)

    # Shorts contain more than one label
    shorts = [net for net in nets if len(net) > 1]

    # Check number of times each label appears
    net_occurences = Counter(chain.from_iterable(nets))

    # If the same label appears on more than one net, warn about an open
    opens = [
        (nn, count)
        for nn, count in net_occurences.items()
        if count > 1
        ]

    return TraceResult(shorts=shorts, opens=opens, nets=nets)
