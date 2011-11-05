"""Balsa.cl Database scheme


  Stefan Wehner (2011)
"""

from google.appengine.ext import db
from google.appengine.ext.db import polymodel
from google.appengine.ext.db import BadValueError
from geo.geomodel import GeoModel
import settings


class GovName(db.Model):
    """Hold a list of adminstrative entities. Example: Region Metropolitana, Chile"""

    # in unicode
    gov_names = db.StringListProperty()


class StopMeta(db.Model):
    """Keep track of number of datasets stored

    Should contain 9 datasets, the permutations of stops
    STOP, STATION, PLACE with confirmation NO, UPDATE and NEW
    """

    # type of Stop
    stop_type = db.StringProperty(choices=settings.STOP_TYPES)
    #  confirmation status
    confirm = db.StringProperty(choices=settings.CONFIRM_TYPES)
    # counter
    counter = db.IntegerProperty()

    def __str__(self):
        return "<StopMeta> %s %s %d" % (self.stop_type, self.confirm, self.counter)

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
        return "<Stop> id=%d %s" % (self.osm_id, " ".join(self.names))
