"""Balsa.cl Database scheme


  Stefan Wehner (2011)
"""

from google.appengine.ext import db
from google.appengine.ext.db import polymodel
from google.appengine.ext.db import BadValueError
from geo.geomodel import GeoModel
import settings


class StopMeta(db.Model):
    """Keep track of number of datasets stored

    Should contain 9 datasets, the permutations of stops
    STOP, STATION, PLACE with confirmation NO, UPDATE and NEW
    """
    last_update = db.DateTimeProperty()
    counter_stop_no_confirm = db.IntegerProperty()
    counter_stop_new_confirm = db.IntegerProperty()
    counter_stop_update_confirm = db.IntegerProperty()
    counter_station_no_confirm = db.IntegerProperty()
    counter_station_new_confirm = db.IntegerProperty()
    counter_station_update_confirm = db.IntegerProperty()
    counter_place_no_confirm = db.IntegerProperty()
    counter_place_new_confirm = db.IntegerProperty()
    counter_place_update_confirm = db.IntegerProperty()

    def zero_all(self):
        self.counter_stop_no_confirm = 0
        self.counter_stop_new_confirm = 0
        self.counter_stop_update_confirm = 0
        self.counter_station_no_confirm = 0
        self.counter_station_new_confirm = 0
        self.counter_station_update_confirm = 0
        self.counter_place_no_confirm = 0
        self.counter_place_new_confirm = 0
        self.counter_place_update_confirm =0

    def counter_delta(delta, stop_type, confirm="NO"):
        if stop_type == 'STOP' and confirm == 'NO':
            self.counter_stop_no_confirm += delta
        elif stop_type == 'STOP' and confirm == 'UPDATE':
            self.counter_stop_update_confirm += delta
        elif stop_type == 'STOP' and confirm == 'NEW':
            self.counter_stop_new_confirm += delta
        elif stop_type == 'PLACE' and confirm == 'NO':
            self.counter_place_no_confirm += delta
        elif stop_type == 'PLACE' and confirm == 'UPDATE':
            self.counter_place_update_confirm += delta
        elif stop_type == 'PLACE' and confirm == 'NEW':
            self.counter_place_new_confirm += delta
        elif stop_type == 'STATION' and confirm == 'NO':
            self.counter_station_no_confirm += delta
        elif stop_type == 'STATION' and confirm == 'UPDATE':
            self.counter_station_update_confirm += delta
        elif stop_type == 'STATION' and confirm == 'NEW':
            self.counter_station_new_confirm += delta
        else:
            assert False, "Invalid stop type or confirm %s/%s" % (stop_type, confirm)


class Comuna(db.Model):
    """Comunas (Staedte, towns, municipalities)

    from tag is_in:city or is_in:municipality
    """
    name = db.StringProperty()

class Region(db.Model):
    """Regions (States, Bundeslaender)

    from tag is_in:region or is_in:state
    """
    # Short name is the roman number (Chile), the state signature (USA)
    # or some funny Abkuerzung (Germany))
    short_name = db.StringProperty()
    name = db.StringProperty()

class Country(db.Model):
    """Countries of the world

    from tag is_in:country
    """
    name = db.StringProperty()


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
    # alt name (same as above but in pure ascii)
    ascii_names = db.StringListProperty()
    # type of Stop
    stop_type = db.StringProperty(choices=settings.STOP_TYPES)
    # administrative hierarchy
    comuna = db.ReferenceProperty(Comuna)
    region = db.ReferenceProperty(Region)
    pais = db.ReferenceProperty(Country)

    def __str__(self):
        return "<Stop> id=%d %s (lat=%3.3f,lon=%3.3f)" % ("; ".join(self.names),self.location.lat,self.location.lon)

    def __eq__(self,other):
        if not other or not isinstance(other, self.__class__):
            return False
        # test for equal fields
        if self.osm_id == other.osm_id and self.names == other.names and self.stop_type == other.stop_type and self.location == other.location:
            return True
        return False

class StopUpdate(Stop):
    """Holds changed Stops which need to be confirmed by adminstrator before being moved into the Stop datastore
    """
    def __str__(self):
        return "<StopUpdate> id=%d %s (lat=%3.3f,lon=%3.3f)" % ("; ".join(self.names),self.location.lat,self.location.lon)


class StopNew(Stop):
    """Holds new Stops which need to be confirmed by adminstrator before being moved into the Stop datastore
    """
    def __str__(self):
        return "<StopUpdate> id=%d %s (lat=%3.3f,lon=%3.3f)" % ("; ".join(self.names),self.location.lat,self.location.lon)

