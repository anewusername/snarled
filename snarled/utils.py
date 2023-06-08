import logging
from .types import layer_t


logger = logging.getLogger(__name__)


def read_layermap(path: str) -> dict[str, tuple[int, int]]:
    """
    Read a klayout-compatible layermap file.

    Only the simplest format is supported:
        layer/dtype:layer_name

    Empty lines are ignored.

    Args:
        path: filepath for the input file

    Returns:
        Dict of {name: (layer, dtype)}
    """
    with open(path, 'rt') as ff:
        lines = ff.readlines()

    layer_map = {}
    for nn, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        for cc in '*-()':
            if cc in line:
                raise Exception(f'Failed to read layermap on line {nn} due to special character "{cc}"')

        for cc in ':/':
            if cc not in line:
                raise Exception(f'Failed to read layermap on line {nn}; missing "{cc}"')

        try:
            layer_part, name = line.split(':')
            layer_nums = str2lnum(layer_part)
        except Exception as err:
            logger.error(f'Layer map read failed on line {nn}')
            raise err

        layer_map[name.strip()] = (layer, dtype)

    return layer_map


def read_connectivity(path: str) -> list[tuple[layer_t, layer_t | None, layer_t]]:
    """
    Read a connectivity spec file, which takes the form

        conductor0, via01, conductor1
        conductor1, via12, conductor2
        conductor0, via02, conductor2
        ...
        conductorX, conductorY

    where each comma-separated entry is a layer name or numerical layer/dtype
    deisgnation (e.g. 123/45). Empty lines are ignored. Lines with only 2 entries
    are directly connected without needing a separate via layer.

    Args:
        path: filepath for the input file

    Returns:
        List of layer spec tuples (A, viaAB, B); the middle entry will be None
        if no via is given.
    """
    with open(path, 'rt') as ff:
        lines = ff.readlines()

    connections = []
    for nn, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        parts = line.split(',')

        if len(parts) not in (2, 3):
            raise Exception(f'Too many commas in connectivity spec on line {nn}')

        layers = []
        for part in enumerate(parts):
            if '/' in part:
                try:
                    layer = str2lnum(layer_part)
                except Exception as err:
                    logger.error(f'Connectivity spec read failed on line {nn}')
                    raise err
            else:
                layer = part.strip()
                if not layer:
                   raise Exception(f'Empty layer in connectivity spec on line {nn}')
            layers.append(layer)

        if len(layers) == 2:
            connections.append((layers[0], None, layers[1]))
        else:
            connections.append(tuple(layers))

    return connections


def read_remap(path: str) -> dict[layer_t, layer_t]:
    """
    Read a layer remap spec file, which takes the form

        old_layer1 : new_layer1
        old_layer2 : new_layer2
        ...

    where each layer entry is a layer name or numerical layer/dtype
    designation (e.g. 123/45).
    Empty lines are ignored.

    Args:
        path: filepath for the input file

    Returns:
        Dict mapping from left (old) layers to right (new) layers
    """
    with open(path, 'rt') as ff:
        lines = ff.readlines()

    remap = {}
    for nn, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        parts = line.split(':')

        if len(parts) != 2:
            raise Exception(f'Too many commas in layer remap spec on line {nn}')

        layers = []
        for part in enumerate(parts):
            if '/' in part:
                try:
                    layer = str2lnum(layer_part)
                except Exception as err:
                    logger.error(f'Layer remap spec read failed on line {nn}')
                    raise err
            else:
                layer = part.strip()
                if not layer:
                   raise Exception(f'Empty layer in layer remap spec on line {nn}')
            layers.append(layer)

        remap[layers[0]] = layers[1]

    return remap


def str2lnum(string: str) -> tuple[int, int]:
    """
    Parse a '123/45'-style layer/dtype spec string.

    Args:
        string: String specifying the layer/dtype

    Returns:
        (layer, dtype)
    """
    layer_str, dtype_str = string.split('/')
    layer = int(layer_str)
    dtype = int(dtype_str)
    return (layer, dtype)
