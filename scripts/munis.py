import logging
import os
import sys
import xml.sax
import json
import unicodedata

# contains Nodes organized by osm_id
Nodes={}
# contains Ways organized by osm_id
Ways={}
# contains Relations organized by osm_id
Relations={}


class Node(object):
    def __init__(self,osm_id,lat,lon):
        self.lat = lat
        self.lon = lon
        self.osm_id = osm_id

class Way(object):
    def __init__(self,osm_id):
        self.nodes=[]
        self.osm_id = osm_id
        self.level = -1
        self.name = ""

    def add_node(self, node_id):
        self.nodes.append(node_id)


class Relation(object):
    def __init__(self,osm_id):
        self.osm_id = osm_id
        self.ways=[]
        # levels are:
        # 1 for country
        #
        self.level = -1
        self.name = ""

    def add_way(self, way_id):
        self.ways.append(way_id)

class OSMXMLFileParser(xml.sax.ContentHandler):
    def __init__(self):
        self.node = None
        self.way = None
        self.relation = None

    def startElement(self, name, attrs):
        if name == 'node':
            self.node = Node(attrs['osm_id'],float(attrs['lat']),float(attrs['lon']))
        elif name == 'way':
            self.way = Way(attrs['osm_id'])
        elif name == 'tag':
            if self.relation:
                if 'boundary' in attrs:
                    if attrs['k'] == 'name':
                        self.relation.name(attrs['v'])
                    if attrs['k'] == admin_level:
                        self.relation.level(int(attrs['v']))
                else:
                    # we are only interested in boundary relations
                    self.relation = None
            if self.way:
                if 'boundary' in attrs:
                    if attrs['k'] == 'name':
                        self.way.name(attrs['v'])
                    if attrs['k'] == admin_level:
                        self.way.level(int(attrs['v']))
        elif name == "nd":
            if self.way:
                self.way.add_node(int(attrs['ref']))
        # not important for us
        elif name == "osm":
            pass
        elif name == "relation":
            self.relation = Relation(attrs['osm_id'])
        elif name == "member":
            if self.relation:
                if attrs['k'] == 'role' and attrs['v'] != 'inner':
                    if attrs['type'] == 'way':
                        self.relation.add_way(int(attrs['ref']))
        elif name == "bound":
            pass
        else:
            logging.error ("Don't know element %s" % (name))


    def endElement(self, name):
        if name == "node":
            if self.node:
                nodes[self.node.osm_id] = self.node
                self.node = None
        elif name == "way":
            if self.way:
                ways[self.way.osm_id] = self.way
                self.way = None
        elif name == "relation":
            if self.relation:
                relations[self.relation.osm_id] = relation.way
                self.relation = None
        elif name == "osm":
            pass
        else:
            pass



def main(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if len(args) < 3:
        print "Usage:"
        print args[0]+" <osm boundary xml file>"
        print " input file contains relations and ways tagged as boundary=administrative"
    osmfile = args[1]
    try:
        fp = open(osmfile)
    except IOError:
        logging.Critical("Can't open file: "+osmfile)
        sys.exit(1)
    # parse osm file
    handler = OSMXMLFileParser()
    xml.sax.parse(osmfile, handler)
    # resolve dependencies and form polygons for every relation



if __name__ == "__main__":
    main(sys.argv)

