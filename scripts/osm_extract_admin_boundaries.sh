#!/bin/bash
#
# Extract administrative boundaries
# Parameters:
#  <OSM dump input file (pbf format)>
#  <filtered osm dump output file>
#

osmosis --read-pbf file=$1 \
  --tf accept-relations boundary=administrative \
  --tf reject-ways highway=* \
  --tf reject-ways landuse=* \
  --used-node \
  --used-way \
  --write-xml file=$2
