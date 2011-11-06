"""Balsa.cl Database scheme


  Stefan Wehner (2011)
"""

from google.appengine.ext import db
from google.appengine.ext.db import polymodel
from google.appengine.ext.db import BadValueError
from geo.geomodel import GeoModel
import settings



class GovMeta(db.Model):
    """Keep number of Gov entries"""
    counter = db.IntegerProperty()

class GovName(db.Model):
    """Hold a list of adminstrative entities. Example: Region Metropolitana, Chile"""

    # in unicode
    gov_names = db.StringListProperty()

    def __str__(self):
        return "<%s> %s" % (self.__class__,", ".join(self.gov_names))

class StopMeta(db.Model):
    """Keep track of number of datasets stored

    Should contain 9 datasets, the permutations of stops
    STOP, STATION, PLACE with confirmation NO, UPDATE and NEW
    """

    counter_stop_no_confirm = db.IntegerProperty()
    counter_stop_new_confirm = db.IntegerProperty()
    counter_stop_update_confirm = db.IntegerProperty()
    counter_station_no_confirm = db.IntegerProperty()
    counter_station_new_confirm = db.IntegerProperty()
    counter_station_update_confirm = db.IntegerProperty()
    counter_place_no_confirm = db.IntegerProperty()
    counter_place_new_confirm = db.IntegerProperty()
    counter_place_update_confirm = db.IntegerProperty()


class Stop(GeoModel):
    """Lists bus stops, train halts, terminals, stations on ordinary
    place names (where a bus may stop)
    """

    # location property is defined in parent class
    # location = db.GeoPtProperty(required=True)
    # location_geocells is defined in parent class and used for quick geo queries
    # location_geocells = db.StringListProperty()
    # needs to be updated before every put. Call update_location() on the class

    # List of names for this stop, in unicode
    names = db.StringListProperty()
    # alt name (same as above and more but in pure ascii)
    ascii_names = db.StringListProperty()
    # openstreetmap node id
    osm_id = db.IntegerProperty(required=True)
    # type of Stop
    stop_type = db.StringProperty(choices=settings.STOP_TYPES)
    # administrative hierarchy
    gov = db.ReferenceProperty(GovName, collection_name="stops")
    #  field marks data sets which need to be confirmed as updated or new
    confirm = db.StringProperty(choices=settings.CONFIRM_TYPES)

    def __str__(self):
        return "<Stop> id=%d %s (lat=%3.3f,lon=%3.3f)" % (self.osm_id, " ".join(self.names),self.location.lat,self.location.lon)

    def __eq__(self,other):
        if not other or not isinstance(other, self.__class__):
            return False
        # test for equal fields
        if self.osm_id == other.osm_id and self.names == other.names and self.stop_type == other.stop_type and self.location == other.location:
            return True
        return False

