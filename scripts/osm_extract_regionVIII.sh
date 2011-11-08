#!/bin/bash
#
# Extract administrative boundaries
# Parameters:
#  <OSM dump input file (pbf format)>
#  <filtered osm dump output file>
#

osmosis --read-pbf file=$1 \
  --bounding-box bottom=-37.01 top=-36.24 left=-73.24 right=-70.97 \
  --write-pbf file=$2
