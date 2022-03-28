from typing import List, Set
from collections import defaultdict

from .types import layer_t, net_name_t, contour_t


class NetsInfo:
    nets: defaultdict[net_name_t, defaultdict[layer_t, List]]
    net_aliases: defaultdict[net_name_t, net_name_t]

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
                base_name = self.resolve_name(kk)
                assert(isinstance(base_name, str))
                shorts[base_name].append(kk)

        shorted_sets = [set([kk] + others)
                        for kk, others in shorts.items()]
        return shorted_sets
