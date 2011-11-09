import logging
import os
import sys
import xml.sax
import json
import unicodedata
import inspect
import lib.osmmath
import lib.euclid

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

    def coordinates_in_box(self,node):
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
        # outline segments from node to node as vectors
        self.segments = []
        # merkator transformation object, initialized with first node
        self.merkator = None

    def add_node(self,node):
        """receive (lat,lon) tuple"""
        self.nodes.append(node)
        # update bounding box
        self.bbox.include_node(node)
        # initialize projection with first node
        if not self.merkator:
            self.merkator = lib.osmmath.Merkator(node)

    def calculate_segments(self):
        """Calculates outline segments from pairs of nodes"""
        self.segments=[]
        nn = len(self.nodes)
        for i in range(nn):
            p0 = self.merkator.getXY(self.nodes[i])
            p1 = self.merkator.getXY(self.nodes[(i+1)%nn])
            if p0 == p1:
                # happens at the common points of two ways
                continue
            # and in euclid format
            p0 = lib.euclid.Point2(p0[0], p0[1])
            p1 = lib.euclid.Point2(p1[0], p1[1])
            self.segments.append(lib.euclid.LineSegment2(p0,p1))

    def coordinates_in_boundary(self, coord):
        """Return True if point is in boundary polygon, False otherwise"""
        # construct a ray starting from the point
        point = self.merkator.getXY(coord)
        ray = lib.euclid.Ray2(lib.euclid.Point2(point[0],point[1]),lib.euclid.Vector2(1,1))
        # count the ray's intersections with boundary segments
        count = 0
        for segment in self.segments:
            if ray.intersect(segment):
                count += 1
        if count & 1:
            # if the number of intersections is odd, then the point is inside
            return True
        return False

    def __str__(self):
        return "Level %d Boundary %s (%d nodes) %s %s" % (self.level, self.name, len(self.nodes), "INCOMPLETE" if self.incomplete else "", str(self.bbox))


class BoundaryContainer():
    """Hold the parsed boundaries separated by level and provide methods to work with them"""

    def __init__(self):
        # holds lists of Boundary objects mapped by their level
        self.bnds = {}
        self.statistics = {}
        for i in range(10):
            self.statistics[i] = {'match': 0, 'no_match': 0, 'multiple_match': 0}

    def print_statistics(self, stream):
        """Print some data on admin tagging"""
        for i in range(10):
            counter = 0
            counter += self.statistics[i]['match']
            counter += self.statistics[i]['no_match']
            counter += self.statistics[i]['multiple_match']
            if counter:
                print >> stream, "Level-%d location tagging: " % (i)
                print >> stream, "%4d ok" % (self.statistics[i]['match'])
                print >> stream, "%4d no match" % (self.statistics[i]['no_match'])
                print >> stream, "%4d multiple matches" % (self.statistics[i]['multiple_match'])


    def add(self, bdy):
        """Add boundary object to container"""
        # check if the boundary object looks valid (minimum three nodes!)
        if len(bdy.nodes) < 3:
            return

        # calculate segments of boundary object on the occasion
        bdy.calculate_segments()
        if bdy.level in self.bnds:
            self.bnds[bdy.level].append(bdy)
        else:
            self.bnds[bdy.level] = [bdy]

    def get_entity_by_level(self,level,lat,lon):
        """Return name of administrative entity of given level in which the coordinates are located"""
        # Quick approach: Look for a unique match in bounding boxes
        box_match = []
        for bdy in self.bnds[level]:
            if bdy.bbox.coordinates_in_box((lat,lon)):
                box_match.append(bdy)
        # zero, one or multiple matches?
        if not box_match:
            return None
            self.statistics[level]['no_match'] += 1
        elif len(box_match) == 1:
            return box_match[0].name
            self.statistics[level]['match'] += 1
        else:
            poly_match = []
            for match in box_match:
                # verify with more precise point in polygon check
                if match.coordinates_in_boundary((lat,lon)):
                    poly_match.append(match)
            # Again: zero, one or multiple matches?
            if not poly_match:
                self.statistics[level]['no_match'] += 1
                return None
            elif len(poly_match) == 1:
                self.statistics[level]['match'] += 1
                return poly_match[0].name
            else:
                self.statistics[level]['multiple_match'] += 1
        return None

    def get_muni(self,lat,lon):
        """Return municipality name where the position is located"""
        return self.get_entity_by_level(8,lat,lon)

    def get_region(self,lat,lon):
        """Return region name where the position is located"""
        return self.get_entity_by_level(4,lat,lon)

    def get_country(self,lat,lon):
        """Return country name where the position is located"""
        return self.get_entity_by_level(2,lat,lon)


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

    def __init__(self,bdy_container):
        self.node = None
        self.writer = xml.sax.saxutils.XMLGenerator(sys.stdout, "UTF-8")
        self.writer.startDocument()
        self._bdy_container = bdy_container
        attr_vals = {
            u'version': "0.6",
            u'generator': u"Balsa.cl AdminBoundary enrichment"
            }
        attrs = xml.sax.xmlreader.AttributesImpl(attr_vals)
        self.writer.startElement(u'osm', attrs)
        self.counter = 0

    def cleanup(self):
        """Finish up writing"""
        self.writer.endDocument()

    def print_statistics(self,stream):
        print >> stream, "%8d Nodes checked in target file" % (self.counter)

    def startElement(self, name, attrs):
        if name == 'node':
            self.node = Node(int(attrs['id']),float(attrs['lat']),float(attrs['lon']))
        elif name == 'tag':
            # elements with name will get a geolocation in their adminstrative boundaries here
            if self.node:
                if attrs['k'] == 'name':
                    self.counter += 1
                    my_attrs = {}
                    my_attrs.update(attrs)
                    muni = self._bdy_container.get_muni(self.node.lat, self.node.lon)
                    if muni:
                        my_attrs['is_in:municipality'] = muni
                    region = self._bdy_container.get_region(self.node.lat, self.node.lon)
                    if region:
                        my_attrs['is_in:region'] = region
                    country = self._bdy_container.get_country(self.node.lat, self.node.lon)
                    if country:
                        my_attrs['is_in:country'] = country
                    self.writer.startElement(name, my_attrs)
                    return
        elif name == 'osm':
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
                    try:
                        self.way.level = (int(attrs['v']))
                    except ValueError:
                        pass
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

    print >> sys.stderr, "Parse boundary file..."
    handler = OSMXMLFileParser()
    xml.sax.parse(fp, handler)
    fp.close()
    print >> sys.stderr,  "%8d Nodes" % (len(Nodes))
    print >> sys.stderr,  "%8d Ways" % (len(Ways))
    print >> sys.stderr,  "%8d Relations" % (len(Relations))

    # resolve dependencies and form polygons for every relation
    print >> sys.stderr, "Build boundary polygons..."
    bounds = BoundaryContainer()
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
        bounds.add(bdy)
    # before relations: ways can mark an area, too
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
            bounds.add(bdy)

    print >> sys.stderr, "Parse target file and update nodes..."
    nodefile = args[2]
    try:
        fp = open(nodefile)
    except IOError:
        logging.Critical("Can't open file: "+nodefile)
        sys.exit(1)
    # parse osm file
    handler = OSMXMLNodeParser(bounds)
    xml.sax.parse(fp, handler)
    handler.cleanup()
    fp.close()

    bounds.print_statistics(sys.stderr)
    handler.print_statistics(sys.stderr)


if __name__ == "__main__":
    main(sys.argv)

