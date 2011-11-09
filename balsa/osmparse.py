"""Balsa parser for openstreetmap data

   Stefan Wehner (2011)
"""
import os
import sys
import xml.sax
import logging
import datetime

try:
    from settings import LOG_LEVEL
except ImportError:
    LOG_LEVEL = logging.DEBUG


# Tags which we use to define a STOP, STATION or PLACE
StopAttr = {'place': [('city','PLACE'),
                      ('town','PLACE'),
                      ('village','PLACE'),
                      ('hamlet','PLACE'),
                      ('isolated_dwelling','PLACE'),
                      ('locality','PLACE')],
            'amenity': [('bus_station','STATION')],
            'public_transport': [('stop','STOP'),
                                ('stop_position','STOP'),
                                ('stop_area','STOP'),
                                ('station','STATION')],
            'highway': [('bus_stop','STOP')],
            'railway': [('halt','STOP'),
                        ('station','STATION')]
            }

class Node(object):
    def __init__(self,osm_id,name,lat,lon,timestamp):
        self.osm_id = osm_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.attr = {}
        self.timestamp = datetime.datetime(int(timestamp[0:4]),int(timestamp[5:7]),int(timestamp[8:10]),int(timestamp[11:13]),int(timestamp[14:16]),int(timestamp[17:19]),0,None)

    def __str__(self):
        return "NODE %s (%3.3f, %3.3f)" % (self.name.encode("UTF-8") ,self.lat,self.lon)


class OSMContentHandler(xml.sax.ContentHandler):
    def __init__(self, filedata, node_attr_cb):
        """
        Use this class to load and parse OSM files.

        node_attr_cb defines a tuple of structure with attributes and a callback.
        If a node is parsed whose attributes coincide at least at one position
        with those in the given attribute structure, then the node is returned.
        """
        self._counter = 0
        self._current_node = None
        self._find_node_attr, self._find_node_cb = node_attr_cb
        # call parent initializer and start parsing
        # Can't use super() because Content handler is old style class
        xml.sax.handler.ContentHandler.__init__(self)
        try:
            if isinstance(filedata,str):
                xml.sax.parseString(filedata, self)
            else:
                xml.sax.parse(filedata, self)
        except xml.sax.SAXParseException:
            raise SyntaxError


    def startElement(self, name, attrs):
        if name == 'node':
            # Always store data in new entity while parsing.
            # In the end, decide whether it is written to storage
            self._current_node = Node(long(attrs['id']), "<no name>",
                            float(attrs['lat']),
                            float(attrs['lon']),
                            attrs['timestamp'])

        elif name == 'way':
            pass

        elif name == 'tag':
            if self._current_node:
                if attrs['k'] == 'name':
                    self._current_node.name = attrs['v']
                self._current_node.attr[attrs['k']] = attrs['v']

        elif name == "nd":
            pass

        # not important for us
        elif name == "osm":
            pass
        elif name == "relation":
            pass
        elif name == "member":
            pass
        elif name == "bound":
            pass
        elif name == "bounds":
            pass
        else:
            logging.error ("Don't know element %s" % (name))


    def endElement(self, name):
        if name == "node":
            # Check if the current node has attributes with the key/value
            # combination we are looking for
            for key,val_list in self._find_node_attr.items():
                if key in self._current_node.attr:
                    for tag,kind in val_list:
                        if tag == self._current_node.attr[key]:
                            # found a matching node, callback
                            self._find_node_cb(self._current_node,kind)
            self._current_node = None

        elif name == "way":
            pass
        elif name == "relation":
            pass
        elif name == "osm":
            pass
        else:
            pass


def test_cb(node, kind):
    """callback function for testing"""
    print "Found ",kind,": ",node

def main(args):
    logging.getLogger().setLevel(LOG_LEVEL)
    try:
        fp = open(args[1],'r')
    except IOError:
        logging.critical ("Can't open file: "+args[1])
        sys.exit(1)
    except IndexError:
        logging.critical ("Usage: Call with filename parameter")
        sys.exit(1)

    OSMContentHandler(fp, (StopAttr, test_cb))
    fp.close()



if __name__ == "__main__":
    main(sys.argv)

