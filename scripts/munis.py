import logging
import os
import sys
import xml.sax
import json
import unicodedata

Munis={}

def plainify(string):
    """Removes all accents and special characters form string and converts
    string to lower case. If the string is made up of several words a list
    of these words is returned.

    Returns an array of plainified strings (splitted at space)
    """
    res = []
    for s1 in string.split(" "):
        s1 = s1.strip(",.;:\\?/!@#$%^&*()[]{}|\"'")
        s1 = unicodedata.normalize('NFD',s1.lower())
        s1 = s1.replace("`", "")
        s1 = s1.encode('ascii','ignore')
        s1 = s1.replace("~", "")
        s1 = s1.strip()
        if len(s1):
            res.append(s1)

    return res


class Place(object):
    def __init__(self,osm_id,name,lat,lon):
        self.osm_id = osm_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.kind = None


class OSMXMLFileParser(xml.sax.ContentHandler):
    def __init__(self):
        self.counter = 0
        self.place = None

    def startElement(self, name, attrs):
        if name == 'node':
            # Always store data in new entity while parsing.
            # In the end, decide whether it is written to storage
            self.place = Place(long(attrs['id']), "<no name>",
                            float(attrs['lat']),
                            float(attrs['lon']))

        elif name == 'way':
            pass

        elif name == 'tag':
            if self.place:
                if attrs['k'] == 'name':
                    self.place.name = attrs['v']
                if attrs['k'] == 'place':
                    self.place.kind = attrs['v']

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
        else:
            logging.error ("Don't know element %s" % (name))


    def endElement(self, name):
        if name == "node":
            placename = " ".join(plainify(self.place.name))
            if placename in Munis:
                # print self.place.name,self.place.lat,self.place.lon
                del Munis[placename]

        elif name == "way":
            pass
        elif name == "relation":
            pass
        elif name == "osm":
            pass
        else:
            pass

def parseOSMXMLFile(filename=None, content=None):
    """
    Use this class to load and parse OSM files.
    """
    handler = OSMXMLFileParser()
    if content:
        xml.sax.parseString(content, handler)
    else:
        xml.sax.parse(filename, handler)


def main(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if len(args) < 3:
        print "Usage:"
        print args[0]+" <munifile> <osmfile>"
        print " <munifile> contains a list of municialities, short names, province and region"
        print " <osmfile> contains places (town, city, village). Other tags are ignored."
    munifile = args[1]
    try:
        fp = open(munifile)
    except IOError:
        logging.Critical("Can't open file: "+munifile)
        sys.exit(1)
    for line in fp:
        line = line.decode("Latin-1")
        muni = line.split(",")
        Munis[" ".join(plainify(muni[0]))] = muni
    fp.close()
    parseOSMXMLFile (filename=args[2])
    for key in Munis.keys():
        print key.encode("UTF-8")

if __name__ == "__main__":
    main(sys.argv)

