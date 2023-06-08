from typing import Any
import argparse
import logging
from pprint import pformat


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(
    prog='snarled',
    description='layout connectivity checker',
    )

parser.add_argument('file_path')
parser.add_argument('connectivity_path')
parser.add_argument('-m', '--layermap')
parser.add_argument('-t', '--top')
parser.add_argument('-p', '--labels-remap')

parser.add_argument('-l', '--lfile-path')
parser.add_argument('-r', '--lremap')
parser.add_argument('-n', '--llayermap')
parser.add_argument('-s', '--ltop')

parser.add_argument('-o', '--output')
parser.add_argument('-u', '--raw-label-names', action='store_true')


args = parser.parse_args()

filepath = args.file_path
connectivity = utils.read_connectivity(args.connectivity_path)

kwargs: dict[str, Any] = {}

if args.layermap:
    kwargs['layer_map'] = utils.read_layermap(args.layermap)

if args.top:
    kwargs['topcell'] = args.top

if args.labels_remap:
    kwargs['labels_remap'] = utils.read_remap(args.labels_remap)

if args.lfile_path:
    kwargs['lfile_path'] = args.lfile_path
    kwargs['lfile_map'] = utils.read_remap(args.lremap)

if args.llayermap:
    kwargs['lfile_layermap'] = utils.read_layermap(args.llayermap)

if args.ltop:
    kwargs['lfile_topcell'] = args.ltop

if args.output:
    kwargs['output_path'] = args.output

if not args.raw_label_names:
    def parse_label(string: str) -> str:
        try:
            parts = string.split('_')
            _part_id = int(parts[-1])       # must succeed to return here
            return '_'.join(parts[:-1])
        except Exception:
            return string

    kwargs['parse_label'] = parse_label

result = trace_layout(
        filepath=filepath,
        connectivity=connectivity,
        **kwargs,
        )

print('Nets: ', pformat(result.nets))
print('Opens: ', pformat(result.opens))
print('Shorts: ', pformat(result.shorts))
