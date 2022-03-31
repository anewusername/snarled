from typing import List, Set, ClassVar, Optional, Dict
from collections import defaultdict
from dataclasses import dataclass

from .types import layer_t, contour_t


class NetName:
    name: Optional[str]
    subname: int
    count: ClassVar[defaultdict[Optional[str], int]] = defaultdict(int)

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
    nets: defaultdict[NetName, defaultdict[layer_t, List]]
    net_aliases: Dict[NetName, NetName]

    def __init__(self) -> None:
        self.nets = defaultdict(lambda: defaultdict(list))
        self.net_aliases = {}

    def resolve_name(self, net_name: NetName) -> NetName:
        while net_name in self.net_aliases:
            net_name = self.net_aliases[net_name]
        return net_name

    def merge(self, net_a: NetName, net_b: NetName) -> None:
        net_a = self.resolve_name(net_a)
        net_b = self.resolve_name(net_b)

        # Always keep named nets if the other is anonymous
        keep_net, old_net = sorted((net_a, net_b))

        #logger.info(f'merging {old_net} into {keep_net}')
        self.net_aliases[old_net] = keep_net
        if old_net in self.nets:
            for layer in self.nets[old_net]:
                self.nets[keep_net][layer] += self.nets[old_net][layer]
            del self.nets[old_net]


    def get_shorted_nets(self) -> List[Set[NetName]]:
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
