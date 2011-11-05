#!/bin/bash
#
# Extract relevant public_transport stops and place data from Openstreetmap dump
# Parameters:
#  <OSM dump input file (pbf format)>
#  <filtered osm dump output file>
#

osmosis --read-pbf file=$1 \
  --node-key keyList="place,public_transport" \
  outPipe.0=NODES \
  \
  --read-pbf file=$1 \
  --node-key-value keyValueList="highway.bus_stop,amenity.bus_station,public_transport.station,railway.station,railway.halt" \
  outPipe.0=MORE_STOPS \
  \
  --merge inPipe.0=NODES inPipe.1=MORE_STOPS  \
  --write-xml file=$2
