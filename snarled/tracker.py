from typing import List, Set, ClassVar, Optional, Dict
from collections import defaultdict
from dataclasses import dataclass

from .types import layer_t, contour_t


class NetName:
    """
    Basically just a uniquely-sortable `Optional[str]`.

    A `name` of `None` indicates that the net is anonymous.
    The `subname` is used to track multiple same-named nets, to allow testing for opens.
    """
    name: Optional[str]
    subname: int

    count: ClassVar[defaultdict[Optional[str], int]] = defaultdict(int)
    """ Counter for how many classes have been instantiated with each name """

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name
        self.subname = self.count[name]
        NetName.count[name] += 1

    def __lt__(self, other: 'NetName') -> bool:
        if self.name == other.name:
            return self.subname < other.subname
        elif self.name is None:
            return False
        elif other.name is None:
            return True
        else:
            return self.name < other.name

    def __repr__(self) -> str:
        if self.name is not None:
            name = self.name
        else:
            name = '(None)'

        if NetName.count[self.name] == 1:
            return name
        else:
            return f'{name}__{self.subname}'


class NetsInfo:
    """
    Container for describing all nets and keeping track of the "canonical" name for each
    net. Nets which are known to be shorted together should be `merge`d together,
    combining their geometry under the "canonical" name and adding the other name as an alias.
    """
    nets: defaultdict[NetName, defaultdict[layer_t, List]]
    """
    Contains all polygons for all nets, in the format
    `{net_name: {layer: [poly0, poly1, ...]}}`

    Polygons are usually stored in pyclipper-friendly coordinates, but may be either `PyPolyNode`s
     or simple lists of coordinates (oriented boundaries).
    """

    net_aliases: Dict[NetName, NetName]
    """
    A mapping from alias to underlying name.
    Note that the underlying name may itself be an alias.
    `resolve_name` can be used to simplify lookup
    """

    def __init__(self) -> None:
        self.nets = defaultdict(lambda: defaultdict(list))
        self.net_aliases = {}

    def resolve_name(self, net_name: NetName) -> NetName:
        """
        Find the canonical name (as used in `self.nets`) for any NetName.

        Args:
            net_name: The name of the net to look up. May be an alias.

        Returns:
            The canonical name for the net.
        """
        while net_name in self.net_aliases:
            net_name = self.net_aliases[net_name]
        return net_name

    def merge(self, net_a: NetName, net_b: NetName) -> None:
        """
        Combine two nets into one.
        Usually used when it is discovered that two nets are shorted.

        The name that is preserved is based on the sort order of `NetName`s,
        which favors non-anonymous, lexicograpically small names.

        Args:
            net_a: A net to merge
            net_b: The other net to merge
        """
        net_a = self.resolve_name(net_a)
        net_b = self.resolve_name(net_b)
        if net_a is net_b:
            return

        # Always keep named nets if the other is anonymous
        keep_net, old_net = sorted((net_a, net_b))

        #logger.info(f'merging {old_net} into {keep_net}')
        self.net_aliases[old_net] = keep_net
        if old_net in self.nets:
            for layer in self.nets[old_net]:
                self.nets[keep_net][layer] += self.nets[old_net][layer]
            del self.nets[old_net]

    def prune(self, layer: layer_t) -> None:
        """
        Delete all geometry for the given layer.

        Args:
            layer: The layer to "forget"
        """
        for net in self.nets.values():
            if layer in net:
                del net[layer]

    def get_shorted_nets(self) -> List[Set[NetName]]:
        """
        List groups of non-anonymous nets which were merged.

        Returns:
            A list of sets of shorted nets.
        """
        shorts = defaultdict(list)
        for kk in self.net_aliases:
            if kk.name is None:
                continue

            base_name = self.resolve_name(kk)
            assert(base_name.name is not None)
            shorts[base_name].append(kk)

        shorted_sets = [set([kk] + others)
                        for kk, others in shorts.items()]
        return shorted_sets

    def get_open_nets(self) -> defaultdict[str, List[NetName]]:
        """
        List groups of same-named nets which were *not* merged.

        Returns:
            A list of sets of same-named, non-shorted nets.
        """
        opens = defaultdict(list)
        seen_names = {}
        for kk in self.nets:
            if kk.name is None:
                continue

            if kk.name in seen_names:
                if kk.name not in opens:
                    opens[kk.name].append(seen_names[kk.name])
                opens[kk.name].append(kk)
            else:
                seen_names[kk.name] = kk
        return opens
