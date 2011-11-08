#!/bin/bash
#
# Extract administrative boundaries
# Parameters:
#  <OSM dump input file (pbf format)>
#  <filtered osm dump output file>
#

osmosis --read-pbf file=$1 \
  --tf accept-ways boundary=administrative \
  --tf accept-relations boundary=administrative \
  --used-node \
  --write-xml file=$2
