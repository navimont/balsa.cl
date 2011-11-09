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

class Box(object):
    """A geographic bounding box"""

    def __init__(self,north=90,west=-180,south=-90,east=180):
        """Create box and initialize
        north[lat], west[lon], south[lat], east[lon]
        """
        self.north = north
        self.south = south
        self.east = east
        self.west = west

    def include_node(self,node):
        """make the bounding box boundaries so that it includes the node

        and all others which have been used to call this function earlier
        """
        lat,lon = node
        if self.south == -90 or lat < self.south:
            self.south = lat
        if self.north == 90 or lat > self.north:
            self.north = lat
        if self.west == -180 or lon < self.west:
            self.west = lon
        if self.east == 180 or lon > self.east:
            self.east = lon

    def is_in(self,node):
        """Is coordinate point in bounding box"""
        lat,lon = node
        if lat < self.north and lat > self.south and lon > self.west and lon < self.east:
            return True
        else:
            return False

    def __str__(self):
        return "(N %f, W %f),(S %f, E %f)" % (self.north,self.west,self.south,self.east)


class Boundary(object):
    """A polygon which represents an administrative boundary"""
    def __init__(self,level,name):
        self.level = level
        self.name = name
        # smallest bounding box which contains the whole polygon
        self.bbox = Box()
        # (lat,lon) tuples which make up the polygon
        self.nodes = []
        # set to True if not all relation elements were found for resolving
        self.incomplete = False

    def add_node(self,node):
        """receive (lat,lon) tuple"""
        self.nodes.append(node)
        # update bounding box
        self.bbox.include_node(node)

    def __str__(self):
        return "Level %d Boundary %s (%d nodes) %s %s" % (self.level, self.name, len(self.nodes), "INCOMPLETE" if self.incomplete else "", str(self.bbox))

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
        self.name = None

    def add_node(self, node_id):
        self.nodes.append(node_id)


class Relation(object):
    def __init__(self,osm_id):
        self.osm_id = osm_id
        self.ways=[]
        # levels are:
        # 1 for country
        # 4 for region (state)
        # 8 for comuna (municipality)
        self.level = -1
        self.name = ""

    def add_way(self, way_id):
        self.ways.append(way_id)

class OSMXMLNodeParser(xml.sax.ContentHandler):
    """Parses the file, enriches it with location information and writes it to stdout immediately"""

    def __init__(self):
        self.node = None
        self.writer = xml.sax.saxutils.XMLGenerator(sys.stdout, "UTF-8")
        self.writer.startDocument()
        attr_vals = {
            u'version': "0.6",
            u'generator': u"Balsa.cl AdminBoundary enrichment"
            }
        attrs = xml.sax.xmlreader.AttributesImpl(attr_vals)
        self.writer.startElement(u'osm', attrs)

    def cleanup():
        """Write everything and close the ports"""
        self.writer.endDocument()

    def startElement(self, name, attrs):
        if name == 'node':
            self.node = Node(int(attrs['id']),float(attrs['lat']),float(attrs['lon']))
        elif name == 'tag':
            # elements with name will get a geolocation in their adminstrative boundaries here
            if self.node:
                if attrs['k'] == 'name':
                    region = get_region(self.node.lat, self.node.lon)
                    if region:
                        attrs['is_in:region'] = region

        elif name = 'osm':
            return
        else:
            pass
        self.writer.startElement(name, attrs)


    def endElement(self, name):
        if name == "node":
            self.node = None
        else:
            pass
        self.writer.endElement(name)


class OSMXMLFileParser(xml.sax.ContentHandler):
    """Parse OSM XML file and extract the nodes, ways and relation which make boundaries"""
    def __init__(self):
        self.node = None
        self.way = None
        self.relation = None

    def startElement(self, name, attrs):
        if name == 'node':
            self.node = Node(int(attrs['id']),float(attrs['lat']),float(attrs['lon']))
        elif name == 'way':
            self.way = Way(int(attrs['id']))
        elif name == 'tag':
            if self.relation:
                if attrs['k'] == 'name':
                    self.relation.name = (attrs['v'])
                if attrs['k'] == 'admin_level':
                    self.relation.level = (int(attrs['v']))
            if self.way:
                if attrs['k'] == 'name':
                    self.way.name = (attrs['v'])
                if attrs['k'] == 'admin_level':
                    self.way.level = (int(attrs['v']))
        elif name == "nd":
            if self.way:
                self.way.add_node(int(attrs['ref']))
        # not important for us
        elif name == "osm":
            pass
        elif name == "relation":
            self.relation = Relation(int(attrs['id']))
        elif name == "member":
            if self.relation:
                if attrs['role'] != 'inner':
                    if attrs['type'] == 'way':
                        self.relation.add_way(int(attrs['ref']))
        elif name == "bound":
            pass
        else:
            logging.error ("Don't know element %s" % (name))


    def endElement(self, name):
        if name == "node":
            if self.node:
                Nodes[self.node.osm_id] = self.node
                self.node = None
        elif name == "way":
            if self.way:
                Ways[self.way.osm_id] = self.way
                self.way = None
        elif name == "relation":
            if self.relation:
                Relations[self.relation.osm_id] = self.relation
                self.relation = None
        elif name == "osm":
            pass
        else:
            pass


def print_usage():
    print >> sys.stderr,  "Usage:"
    print >> sys.stderr,  args[0]+" <osm boundary xml file>  <osm node xml file>"
    print >> sys.stderr,  " boundary input file contains relations and ways tagged as boundary=administrative"
    print >> sys.stderr,  " all nodes in node xml input file which have a name will be located in the"
    print >> sys.stderr,  " boundary polygons defined by the first imput file and extra tags will be "
    print >> sys.stderr,  " written for them: is_in:country (admin level 2), is_in:region (admin_level 4)"
    print >> sys.stderr,  " is_in:municipality (admin_level 8)"
    print >> sys.stderr,  " The enriched file will be written to stdout."

def main(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if len(args) < 3:
        print_usage()
        sys.exit(1)

    osmfile = args[1]
    try:
        fp = open(osmfile)
    except IOError:
        logging.Critical("Can't open file: "+osmfile)
        sys.exit(1)
    # parse osm file
    handler = OSMXMLFileParser()
    xml.sax.parse(fp, handler)
    fp.close()
    print >> sys.stderr,  "Nodes: %d" % (len(Nodes))
    print >> sys.stderr,  "Ways: %d" % (len(Ways))
    print >> sys.stderr,  "Relations: %d" % (len(Relations))
    # resolve dependencies and form polygons for every relation
    bounds = Boundaries()
    for rel in Relations.values():
        bdy = Boundary(rel.level, rel.name)
        for way in rel.ways:
            # resolve way
            try:
                rway = Ways[way]
                for node in rway.nodes:
                    # resolve node
                    try:
                        rnode = Nodes[node]
                        bdy.add_node((rnode.lat,rnode.lon))
                    except KeyError:
                        bdy.incomplete = True
            except KeyError:
                # way is not in data file; set flag
                bdy.incomplete = True
        bounds.append(bdy)
    # before reolations: ways can maark an area, too
    for way in Ways.values():
        if way.level > 0 and way.name:
            bdy = Boundary(way.level, way.name)
            for node in way.nodes:
                # resolve node
                try:
                    rnode = Nodes[node]
                    bdy.add_node((rnode.lat,rnode.lon))
                except KeyError:
                    bdy.incomplete = True
            bounds.append(bdy)

    # parse target file and write enriched to stdout
    nodefile = args[2]
    try:
        fp = open(nodefile)
    except IOError:
        logging.Critical("Can't open file: "+nodefile)
        sys.exit(1)
    # parse osm file
    handler = OSMXMLNodeParser()
    xml.sax.parse(fp, handler)
    handler.cleanup()
    fp.close()


if __name__ == "__main__":
    main(sys.argv)

