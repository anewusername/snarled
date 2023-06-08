#!/usr/bin/env bash

cd $(dirname -- "$0")       # cd to this script's parent directory

snarled connectivity.oas connectivity.txt -l layermap.txt
