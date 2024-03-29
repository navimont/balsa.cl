import logging
import os
import sys
import xml.sax
import json
import unicodedata
import inspect
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
        self.members = []
        # set to True if not all relation elements were found for resolving
        self.incomplete = False
        # outline segments from node to node as vectors
        self.segments = []

    def add_member(self,member):
        """receive a list of Node objects"""
        self.members.append(member)
        # update bounding box
        for node in member:
            self.bbox.include_node((node.lat,node.lon))

    def calculate_segments(self):
        """Calculates outline segments from pairs of its members nodes"""
        if not self.members:
            return

        def connecting_segment(node_id, start, ways, left=True):
            """return the way element's index which starts or ends with node_id

            Start search at index start.
            If the element ends with node_id, it is reversed before returning
            """
            for wi in range(start,len(ways)):
                if ways[wi][0 if left else -1].osm_id == node_id:
                    return wi
                if ways[wi][-1 if left else 0].osm_id == node_id:
                    ways[wi].reverse()
                    return wi
            return None

        # first build continuous outline from the members
        def merge_segments(self, ways):
            """ ways is a list of ways which make the polygon. Their order is unspecified
                find the member which connects to the last node in the first member.
                and unite the two. Their node's osm_id is identical
            """
            for wi in range(0,len(ways)):
                if wi > len(ways)-1:
                    break
                ia = connecting_segment(ways[wi][-1].osm_id, wi+1, ways, left=True)
                while ia:
                    # extend current element wi with successor
                    ways[wi].extend(ways[ia][1:])
                    ways[ia] = ways[wi+1]
                    del ways[wi+1]
                    ia = connecting_segment(ways[wi][-1].osm_id, wi+1, ways, left=True)
                # try the other end
                ia = connecting_segment(ways[wi][0].osm_id, wi+1, ways, left=False)
                while ia:
                    # extend found element in place
                    ways[ia].extend(ways[wi][1:])
                    ways[wi] = ways[ia]
                    del ways[ia]
                    ia = connecting_segment(ways[wi][0].osm_id, wi+1, ways, left=False)

        # function starts here
        merge_segments(self, self.members)
        if len(self.members) == 1 and self.members[0][0].osm_id == self.members[0][-1].osm_id:
            # a perfect polygon. As first and last node are the same, delete one
            del self.members[0][-1]
        else:
            self.incomplete = True

        # make LineSegments from the point-to-point connections
        for member in self.members:
            self.segments=[]
            nn = len(member)
            for i in range(nn):
                p0 = lib.euclid.Point2(member[i].lat,member[i].lon)
                p1 = lib.euclid.Point2(member[(i+1)%nn].lat,member[(i+1)%nn].lon)
                try:
                    self.segments.append(lib.euclid.LineSegment2(p0,p1))
                except AttributeError:
                    # line from identical points
                    print "Caught AttributeError in calculate_segments(). Osm_id: %d and %d" % (member[i].osm_id,member[(i+1)%nn].osm_id)


    def coordinates_in_boundary(self, coord):
        """Return True if point is in boundary polygon, False otherwise"""
        # construct a ray starting from the point
        ray = lib.euclid.Ray2(lib.euclid.Point2(coord[0],coord[1]),lib.euclid.Vector2(1,1))
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
        return "Level-%d Boundary %s (%d members) %s %s" % (self.level, self.name, len(self.members), "INCOMPLETE" if self.incomplete else "", str(self.bbox))


class BoundaryContainer():
    """Hold the parsed boundaries separated by level and provide methods to work with them"""

    def __init__(self):
        # holds lists of Boundary objects mapped by their level
        self.bnds = {}
        self.statistics = {}
        for i in range(10):
            self.statistics[i] = {'box_match': 0, 'poly_match': 0, 'no_match': 0, 'multiple_match': 0}
            self.bnds[i] = []

    def print_boundary_objects(self):
        """For debugging"""
        for bdys in self.bnds.values():
            for bdy in bdys:
                print "%s" % bdy

    def print_statistics(self):
        """Print some data on admin tagging"""
        for i in range(10):
            counter = 0
            counter += self.statistics[i]['box_match']
            counter += self.statistics[i]['poly_match']
            counter += self.statistics[i]['no_match']
            counter += self.statistics[i]['multiple_match']
            if counter:
                print "Level-%d location tagging: " % (i)
                print "%6d box (quick) match" % (self.statistics[i]['box_match'])
                print "%6d poly match" % (self.statistics[i]['poly_match'])
                print "%6d no match" % (self.statistics[i]['no_match'])
                print "%6d multiple matches" % (self.statistics[i]['multiple_match'])

    def add(self, bdy):
        """Add boundary object to container"""
        self.bnds[bdy.level].append(bdy)

    def get_entity_by_level(self,level,lat,lon):
        """Return name of administrative entity of given level in which the coordinates are located"""
        # Quick approach: Look for a unique match in bounding boxes
        box_match = []
        for bdy in self.bnds[level]:
            if bdy.bbox.coordinates_in_box((lat,lon)):
                box_match.append(bdy)
        # zero, one or multiple matches?
        if not box_match:
            self.statistics[level]['no_match'] += 1
            return None
        elif len(box_match) == 1:
            self.statistics[level]['box_match'] += 1
            return box_match[0].name
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
                self.statistics[level]['poly_match'] += 1
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
        return self.get_entity_by_level(1,lat,lon)


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

    def __init__(self,bdy_container,out):
        self.node = None
        self.writer = xml.sax.saxutils.XMLGenerator(out, "UTF-8")
        self.writer.startDocument()
        self._bdy_container = bdy_container
        attr_vals = {
            u'version': "0.6",
            u'generator': u"Balsa.cl AdminBoundary enrichment"
            }
        attrs = xml.sax.xmlreader.AttributesImpl(attr_vals)
        self.writer.startElement(u'osm', attrs)

    def cleanup(self):
        """Finish up writing"""
        self.writer.endDocument()

    def startElement(self, name, attrs):
        if name == 'node':
            self.node = Node(int(attrs['id']),float(attrs['lat']),float(attrs['lon']))
        elif name == 'tag':
            # elements with name will get a geolocation in their adminstrative boundaries here
            if self.node:
                if attrs['k'] == 'name':
                    country = self._bdy_container.get_country(self.node.lat, self.node.lon)
                    if country:
                        self.writer.startElement(name, {'k': 'is_in:country', 'v': country})
                        self.writer.endElement(name)
                    muni = self._bdy_container.get_muni(self.node.lat, self.node.lon)
                    if muni:
                        self.writer.startElement(name, {'k': 'is_in:municipality', 'v': muni})
                        self.writer.endElement(name)
                    region = self._bdy_container.get_region(self.node.lat, self.node.lon)
                    if region:
                        self.writer.startElement(name, {'k': 'is_in:region', 'v': region})
                        self.writer.endElement(name)
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
    print """Usage:
python munis.py <osm boundary xml file>  <osm node xml file> <out file>

<boundary input file>  contains relations and ways tagged as boundary=administrative
<osm node xml file>    all nodes in this second input file which have a name will be
                       located in the"boundary polygons defined by the first imput file.
                       The nodes will be enriched with extra tags which describe their
                       location. E.g.: is_in:country (admin level 2), is_in:region (admin_level 4)
                       is_in:municipality (admin_level 8)
<out file>             The enriched file will be written to the given filename.

All diagnostic information is written to stdout.
"""

def main(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if len(args) < 4:
        print_usage()
        sys.exit(1)

    osmfile = args[1]
    try:
        fp = open(osmfile)
    except IOError:
        logging.Critical("Can't open file: "+osmfile)
        sys.exit(1)

    print "Parse boundary file..."
    handler = OSMXMLFileParser()
    xml.sax.parse(fp, handler)
    fp.close()
    print "%8d Nodes" % (len(Nodes))
    print "%8d Ways" % (len(Ways))
    print "%8d Relations" % (len(Relations))

    # resolve dependencies and form polygons for every relation
    print "Build boundary polygons..."
    bounds = BoundaryContainer()
    for rel in Relations.values():
        if rel.level < 0:
            continue
        bdy = Boundary(rel.level, rel.name)
        for way in rel.ways:
            # resolve way
            try:
                rway = Ways[way]
                member = []
                for node in rway.nodes:
                    # resolve node
                    try:
                        rnode = Nodes[node]
                        member.append(rnode)
                    except KeyError:
                        pass
                bdy.add_member(member)
            except KeyError:
                # way is not in data file; set flag
                pass
        # calculate segments of boundary object
        bdy.calculate_segments()
        bounds.add(bdy)
    # before relations: ways can mark an area, too
    for way in Ways.values():
        if way.level > 0 and way.name:
            bdy = Boundary(way.level, way.name)
            member = []
            for node in way.nodes:
                # resolve node
                try:
                    rnode = Nodes[node]
                    member.append(rnode)
                except KeyError:
                    pass
            bdy.add_member(member)
            # calculate segments of boundary object
            bdy.calculate_segments()
            bounds.add(bdy)

    print "Parse target file and update nodes..."
    nodefile = args[2]
    try:
        fp = open(nodefile)
    except IOError:
        logging.critical("Can't open file: "+nodefile)
        sys.exit(1)

    # open output file
    outfile = args[3]
    try:
        out = open(outfile, 'w')
    except IOError:
        logging.critical("Can't open file: "+outfile)
        sys.exit(1)

    # parse osm file
    handler = OSMXMLNodeParser(bounds, out)
    xml.sax.parse(fp, handler)
    handler.cleanup()
    fp.close()
    out.close()

    # bounds.print_boundary_objects()
    bounds.print_statistics()


if __name__ == "__main__":
    main(sys.argv)

