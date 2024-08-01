from typing import Sequence, Iterable
import logging
from collections import Counter
from itertools import chain

from klayout import db
from .types import lnum_t, layer_t
from .utils import SnarledError


logger = logging.getLogger(__name__)


class TraceAnalysis:
    """
    Short/Open analysis for a list of nets
    """

    nets: list[set[str]]
    """ List of nets (connected sets of labels) """

    opens: dict[str, int]
    """ Labels which appear on 2+ disconnected nets, and the number of nets they touch """

    shorts: list[set[str]]
    """ Nets containing more than one unique label """

    def __init__(
            self,
            nets: Sequence[Iterable[str]],
            ) -> None:
        """
        Args:
            nets: Sequence of nets. Each net is a sequence of labels
                which were found to be electrically connected.
        """

        setnets = [set(net) for net in nets]

        # Shorts contain more than one label
        shorts = [net for net in setnets if len(net) > 1]

        # Check number of times each label appears
        net_occurences = Counter(chain.from_iterable(setnets))

        # Opens are where the same label appears on more than one net
        opens = {
            nn: count
            for nn, count in net_occurences.items()
            if count > 1
            }

        self.nets = setnets
        self.shorts = shorts
        self.opens = opens

    def __repr__(self) -> str:
        def format_net(net: Iterable[str]) -> str:
            names = [f"'{name}'" if any(cc in name for cc in ' \t\n') else name for name in sorted(net)]
            return ','.join(names)

        def sort_nets(nets: Sequence[Iterable[str]]) -> list[Iterable[str]]:
            return sorted(nets, key=lambda net: ','.join(sorted(net)))

        ss = 'Trace analysis'
        ss += '\n============='

        ss += '\nNets'
        ss += '\n(groups of electrically connected labels)\n'
        for net in sort_nets(self.nets):
            ss += '\t' + format_net(net) + '\n'
        if not self.nets:
            ss += '\t<NO NETS FOUND>'

        ss += '\nOpens'
        ss += '\n(2+ nets containing the same name)\n'
        for label, count in sorted(self.opens.items()):
            ss += f'\t{label} : {count} nets\n'
        if not self.opens:
            ss += '\t<No opens found>'

        ss += '\nShorts'
        ss += '\n(2+ unique names for the same net)\n'
        for net in sort_nets(self.shorts):
            ss += '\t' + format_net(net) + '\n'
        if not self.shorts:
            ss += '\t<No shorts found>'

        ss += '=============\n'
        return ss


def trace_layout(
        filepath: str,
        connectivity: Sequence[tuple[layer_t, layer_t | None, layer_t]],
        layer_map: dict[str, lnum_t] | None = None,
        topcell: str | None = None,
        *,
        labels_map: dict[layer_t, layer_t] | None = None,
        lfile_path: str | None = None,
        lfile_map: dict[layer_t, layer_t] | None = None,
        lfile_layer_map: dict[str, lnum_t] | None = None,
        lfile_topcell: str | None = None,
        output_path: str | None = None,
        ) -> list[set[str]]:
    """
    Trace a layout to identify labeled nets.

    To label a net, place a text label anywhere touching the net.
    Labels may be mapped from a different layer, or even a different
    layout file altogether.
    Note: Labels must not contain commas (,)!!

    Args:
        filepath: Path to the primary layout, containing the conductor geometry
            (and optionally also the labels)
        connectivity: List of (conductor1, via12, conductor2) tuples,
            which indicate that the specified layers are electrically connected
            (conductor1 to via12 and via12 to conductor2). The middle (via) layer
            may be `None`, in which case the outer layers are directly connected
            at any overlap (conductor1 to conductor2).
        layer_map: {layer_name: (layer_num, dtype_num)} translation table.
            Should contain any strings present in `connectivity` and `labels_map`.
            Default is an empty dict.
        topcell: Cell name of the topcell. If `None`, it is automatically chosen.
        labels_map: {label_layer: metal_layer} mapping, which allows labels to
            reside on a different layer from their corresponding metals.
            Only labels on the provided label layers are used, so
            {metal_layer: metal_layer} entries must be explicitly specified if
            they are desired.
            If `None`, labels on each layer in `connectivity` are used alongside
            that same layer's geometry ({layer: layer} for all participating
            geometry layers)
            Default `None`.
        lfile_path: Path to a separate file from which labels should be merged.
        lfile_map: {lfile_layer: primary_layer} mapping, used when merging the
            labels into the primary layout.
        lfile_layer_map: {layer_name: (layer_num, dtype_num)} mapping for the
            secondary (label) file. Should contain all string keys in
            `lfile_map`.
            `None` reuses `layer_map` (default).
        lfile_topcell: Cell name for the topcell in the secondary (label) file.
            `None` automatically chooses the topcell (default).
        output_path: If provided, outputs the final net geometry to a layout
            at the given path. Default `None`.

    Returns:
        List of labeled nets, where each entry is a set of label strings which
        were found on the given net.
    """
    if layer_map is None:
        layer_map = {}

    if labels_map is None:
        labels_map = {
            layer: layer
            for layer in chain(*connectivity)
            if layer is not None
            }

    layout = db.Layout()
    layout.read(filepath)

    topcell_obj = _get_topcell(layout, topcell)

    # Merge labels from a separate layout if asked
    if lfile_path:
        if not lfile_map:
            raise SnarledError('Asked to load labels from a separate file, but no '
                               + 'label layers were specified in lfile_map')

        if lfile_layer_map is None:
            lfile_layer_map = layer_map

        lnum_map = {}
        for ltext, lshape in lfile_map.items():
            if isinstance(ltext, str):
                ltext = lfile_layer_map[ltext]
            if isinstance(lshape, str):
                lshape = layer_map[lshape]
            lnum_map[ltext] = lshape

        _merge_labels_from(lfile_path, layout, topcell_obj, lnum_map, lfile_topcell)

    #
    # Build a netlist from the layout
    #
    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, topcell_obj, []))
    #l2n.include_floating_subcircuits = True

    # Create l2n polygon layers
    layer2polys = {}
    for layer in set(chain(*connectivity)):
        if layer is None:
            continue
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
        if isinstance(bot, str):
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
    l2n.extract_netlist()
    nl = l2n.netlist()
    nl.make_top_level_pins()

    if output_path:
        _write_net_layout(l2n, output_path, layer2polys)

    #
    # Return merged nets
    #
    top_circuits = [cc for cc, _ in zip(nl.each_circuit_top_down(), range(nl.top_circuit_count()))]

    # Nets with more than one label get their labels joined with a comma
    nets  = [
        set(nn.name.split(','))
        for cc in top_circuits
        for nn in cc.each_net()
        if nn.name
        ]
    return nets


def _get_topcell(
        layout: db.Layout,
        name: str | None = None,
        ) -> db.Cell:
    """
    Get the topcell by name or hierarchy.

    Args:
        layout: Layout to get the cell from
        name: If given, use the name to find the topcell; otherwise use hierarchy.

    Returns:
        Cell object
    """
    if name is None:
        return layout.top_cell()
    else:
        ind = layout.cell_by_name(name)
        return layout.cell(ind)


def _write_net_layout(
        l2n: db.LayoutToNetlist,
        filepath: str,
        layer2polys: dict[lnum_t, db.Region],
        ) -> None:
    layout = db.Layout()
    top = layout.create_cell('top')
    lmap = {layout.layer(*layer): polys for layer, polys in layer2polys.items()}
    l2n.build_all_nets(l2n.cell_mapping_into(layout, top), layout, lmap, 'net_', 'prop_', l2n.BNH_Flatten, 'circuit_')
    layout.write(filepath)


def _merge_labels_from(
        filepath: str,
        into_layout: db.Layout,
        into_cell: db.Cell,
        lnum_map: dict[lnum_t, lnum_t],
        topcell: str | None = None,
        ) -> None:
    layout = db.Layout()
    layout.read(filepath)

    topcell_obj = _get_topcell(layout, topcell)

    for labels_layer, conductor_layer in lnum_map.items():
        layer_ind_src = layout.layer(*labels_layer)
        layer_ind_dst = into_layout.layer(*conductor_layer)

        shapes_dst = topcell_obj.shapes(layer_ind_dst)
        shapes_src = into_cell.shapes(layer_ind_src)
        for shape in shapes_src.each():
            new_shape = shapes_dst.insert(shape)
            shapes_dst.replace_prop_id(new_shape, 0)        # clear shape properties
