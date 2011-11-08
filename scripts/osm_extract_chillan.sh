#!/bin/bash
#
# Extract administrative boundaries
# Parameters:
#  <OSM dump input file (pbf format)>
#  <filtered osm dump output file>
#

osmosis --read-pbf file=$1 \
  --bounding-box bottom=-36.67 top=-36.54 left=-72.19 right=-72.02 \
  --write-xml file=$2
