"""
This module contains mathematical routines for my osm Scripts

Stefan wehner (2009)
"""

import math

# radius of the earth
earthradius = 6378000.0
deg2rad = math.pi/180.0
deg2meter = math.pi*earthradius/180

def NodeDistance(n1,n2):
    """Returns distance in meters between nodes"""

    # convert all to radians
    a1 = n1.lat * (math.pi/180.0)
    b1 = n1.lon * (math.pi/180.0)
    a2 = n2.lat * (math.pi/180.0)
    b2 = n2.lon * (math.pi/180.0)

    a = math.cos(a1)*math.cos(b1)*math.cos(a2)*math.cos(b2) \
            + math.cos(a1)*math.sin(b1)*math.cos(a2)*math.sin(b2) \
            + math.sin(a1)*math.sin(a2)
    # due to rounding errors this may exceed the legal argument range for acos
    if a < -1.0:
        a = -1.0
    if a > 1.0:
        a = 1.0
    return math.acos(a) * earthradius;


class Merkator:
    """Helps with Merkator projection"""

    def __init__ (self,ll):
        """Initialize with a base coordinate to which the
        transformations will return the difference"""

        self.lat, self.lon = ll

    def getXY(self,ll):
        """return xy coordinates of a point in lat,lon coordinates with reference
        to the base point of the class"""

        x = (ll[1] - self.lon) * deg2meter
        y = (ll[0] - self.lat) * deg2meter * math.log(math.tan(0.25*math.pi + 0.5*self.lat*deg2rad))

        return (x,y)

    def getLatLon(self,xy):
        """return lat,lon coordinates of a point in the local merkator
        tangential plane"""

        lon = self.lon + xy[0] / deg2meter
        lat = self.lat + xy[1] / deg2meter / math.log(math.tan(0.25*math.pi + 0.5*self.lat*deg2rad))

        return (lat,lon)

