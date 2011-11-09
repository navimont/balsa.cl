"""Balsa.cl Handle import and update of stops.
   Module is used by balsa_import and balsa_update

    Stefan Wehner (2011)
"""

import settings
import logging
import os
import re
import difflib
import zipfile
import osmparse
import unicodedata
import datetime
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.db import Key
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from balsa_dbm import Stop, StopMeta, Country, Region, Comuna
from balsa_access import AdminRequired


class Normalize(object):
    """Normalize names with national characters to plain ascii"""

    ignore = ['calle','avenida','avda','plaza','parada','de','del','la','lo','el','los']
    word_pattern = re.compile(r"(\w+)", re.UNICODE)

    @classmethod
    def normalize(cls,string):
        """Removes all accents and special characters form string and converts
        string to lower case. If the string is made up of several words a list
        of these words is returned.

        Returns an array of plainified strings (splitted at space)
        """
        res = []
        for s1 in re.findall(cls.word_pattern, string):
            s1 = unicode(s1)
            s1 = unicodedata.normalize('NFD',s1.lower())
            s1 = s1.replace("`", "")
            s1 = s1.encode('ascii','ignore')
            s1 = s1.replace("~", "")
            s1 = s1.strip()
            if len(s1) > 1 and not s1 in cls.ignore:
                res.append(s1)
        return res

class BalsaStopFactory(object):
    """Acts as a factory for Stop datasets

    Has to be a static class because it is used from a static callback function
    """

    @classmethod
    def create_stop(cls, node, kind):
        """Returns stop in production table created with parent to be in the correct entity group"""
        stop = Stop(key_id=node.osm_id, location=db.GeoPt(lat=node.lat, lon=node.lon))
        # uses the update function to fill all fields
        return cls.fill_stop(stop, node, kind)

    @classmethod
    def create_update_stop(cls, node, kind):
        """Returns stop in update table created with parent to be in the correct entity group"""
        stop = StopUpdate(key_id=node.osm_id, location=db.GeoPt(lat=node.lat, lon=node.lon))
        # uses the update function to fill all fields
        return cls.fill_stop(stop, node, kind)

    @classmethod
    def create_new_stop(cls, node, kind):
        """Returns stop in update table created with parent to be in the correct entity group"""
        stop = StopNew(key_id=node.osm_id, location=db.GeoPt(lat=node.lat, lon=node.lon))
        # uses the update function to fill all fields
        return cls.fill_stop(stop, node, kind)

    @classmethod
    def fill_stop(self, stop, node, kind):
        """Returns stop in the correct entity group"""
        stop.stop_type = kind
        stop.location = db.GeoPt(lat=node.lat, lon=node.lon)
        stop.update_location()
        stop.names = [node.name]
        gov = []
        for k,v in node.attr.items():
            if k in ['alt_name', 'nat_name', 'old_name', 'reg_name', 'loc_name', 'official_name']:
                stop.names.append(v)
            if k.startswith('name:'):
                # language specific
                stop.names.append(v)
            # adminstrative regions
            if k.startswith('is_in:country'):
                country = Country.get_or_insert(key_name=v, name=v)
                stop.country = country
            if k.startswith('is_in:region') or k.startswith('is_in:state'):
                region = Region.get_by_key_name(v)
                if not region:
                    # find the region with the best match (but must have some similarity to tag)
                    region_match = (0.6, "<no match>", "-")
                    for short_name,long_name in settings.REGIONS:
                        ndiff = difflib.SequenceMatcher(None,long_name,v)
                        if ndiff.ratio() > region_match[0]:
                            region_match = (ndiff.ratio(), unicode(long_name), unicode(short_name))
                    if region_match[1] != "<no match>":
                        logging.debug("Match %f for %s and %s" % region_match)
                        region = Region.get_or_insert(key_name=long_name, name=long_name, short_name=short_name)
                        region.put()
                if not region:
                    logging.warning("Unknown region, state or Bundesland: %s" % v)
                else:
                    stop.region = region
            if k.startswith('is_in:city') or k.startswith('is_in:municipality'):
                comuna = Comuna.get_or_insert(key_name=v, name=v)
                stop.comuna = comuna
        stop.ascii_names = []
        for name in stop.names:
            if name != "<no name>":
                stop.ascii_names.extend(Normalize.normalize(name))
        return stop


class BalsaStopWriter(object):
    """Holds Stops which are imported for the first time

    Takes care of batch wise write operations of stop data
    to the database.
    """
    @classmethod
    def init(cls):
        # store the list stop entities to be written to the datastore
        # in a batch operation
        cls._stop_data = []
        cls._timestamp = datetime.datetime(2001,1,1)

    @classmethod
    def add(cls, stop, timestamp):
        if timestamp > cls._timestamp:
            cls._timestamp = timestamp
        cls._stop_data.append(stop)
        # write a batch if a certain quantity has accumulated
        if len(cls._stop_data) % settings.BATCH_SIZE == 0:
            cls.store()

    @classmethod
    def store(cls):
        """Store datasets accumulated in internal list"""
        db.put(cls._stop_data)
        db.run_in_transaction(cls.update_counter)
        cls._stop_data = []

    @classmethod
    def update_counter(cls):
        """Update meta counter fields in transaction"""
        counter = StopMeta.get(Key.from_path('StopMeta', 1))
        for stop in cls._stop_data:
            if isinstance(stop, Stop):
                counter.counter_delta(1, stop.stop_type, "NO")
            elif isinstance(stop, StopUpdate):
                counter.counter_delta(1, stop.stop_type, "UPDATE")
            elif isinstance(stop, StopNew):
                counter.counter_delta(1, stop.stop_type, "NEW")
            else:
                assert False, "Unknown stop instance: %s" % (stop)
            if cls._timestamp > counter.last_update:
                counter.last_update = cls._timestamp
            counter.put()

class BalsaStopStoreTask(webapp.RequestHandler):
    """Background tasks parses osm data and stores stops, stations and places
    in the datastore.
    """
    @staticmethod
    def import_node_cb(node, kind):
        # we don't consider stops for the moment
        if kind == 'STOP':
            return

        """Callback function processes nodes from osm data"""
        stop = BalsaStopFactory.create_stop(node, kind)
        # accumulate some greater number in for efficient batch write to datastore
        BalsaStopWriter.add(stop, node.timestamp)

    @staticmethod
    def update_node_cb(node, kind):
        """Callback function. Process nodes from osm data

        Different to import_node_cb (above) look for existing nodes with the
        same data and discard identical ones. Queue changed nodes and new nodes
        for confirmation.
        """
        # look for existing node with the same osm_id
        old_stop = Stop.get_by_key_id(node.osm_id)
        if old_stop:
            # create stop entity from node data
            stop = BalsaStopStoreTask.create_update_stop(node, kind)
            logging.debug("compare %s <==> %s" % (old_stop,stop))
            if old_stop == stop:
                # no change
                return
            else:
                # accumulate some greater number for efficient batch write to datastore
                BalsaStopWriter.add(stop, node.timestamp)
        else:
            # create stop entity from node data
            stop = BalsaStopStoreTask.create_new_stop(node, kind)
            BalsaStopWriter.add(stop, node.timestamp)
        return

    def post(self):
        # import or upload?
        action = self.request.get('action')
        assert action, "Import or upload? No action specified."

        blob_info = blobstore.BlobInfo.get(self.request.get('osmdata'))
        if not blob_info:
            logging.error("Could open parse uploaded file.")
            memcache.set('%s_status' % action, "%s failed. Could not access data." % action.title(), time=30)
            return

        logging.info("Retrieved %d bytes for processing." % (blob_info.size))

        memcache.set('%s_status' % action, "Parsing %s data." % action, time=100)

        blob_reader = blobstore.BlobReader(blob_info)
        char2 = blob_reader.read(2)
        blob_reader.seek(0)
        if char2 == "PK":
            logging.info("Detected zip file.")
            zip_reader = zipfile.ZipFile(blob_reader, 'rU')
            # we expect exactly one zipfile for reading
            file_reader = zip_reader.read(zip_reader.namelist()[0])
        else:
            file_reader = blob_reader

        # initialize the writer class for stop objects
        BalsaStopWriter.init()

        # parse blob and call node_cb on discovery of a Place, Stop or Station
        try:
            if action == 'import':
                osmparse.OSMContentHandler(file_reader, (osmparse.StopAttr, BalsaStopStoreTask.import_node_cb))
            else:
                osmparse.OSMContentHandler(file_reader, (osmparse.StopAttr, BalsaStopStoreTask.update_node_cb))

            # store fields and counters together in transaction
            BalsaStopWriter.store
            memcache.set('%s_status' % action, "%s finished successfully." % action.title(), time=30)

        except SyntaxError:
            logging.error("Could not parse uploaded file.")
            memcache.set('%s_status' % action, "%s failed. Could not parse data." % action.title(), time=30)

        # free space in blobstore
        blob_info.delete()

class BalsaStopUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    """Is called when an osm data file has been uploaded to the blobstore"""

    @AdminRequired
    def post(self, login_user=None, template_values={}):

        memcache.set('import_status', "Queued import task", time=30)

        # import or upload?
        action = self.request.get('action')
        assert action, "Import or upload? No action specified."

        upload_files = self.get_uploads('osmdata')
        try:
            blob_info = upload_files[0]
        except IndexError:
            memcache.set('%s_status' % action, "%s failed. Nothing found in blobstore." % action.title(), time=30)
            logging.warning("Could not find uploaded data in blobstore.")
            self.redirect('/update')

        # delete memory for confirmation walkthrough (see balsa_update)
        memcache.delete('update')
        memcache.delete('new')

        # start background process
        taskqueue.add(url='/%s/store' % action, queue_name='import',
                      params={'compressed': self.request.get('compressed', ""),
                              'action': action,
                              'osmdata': blob_info.key()})

        # redirect to update page which will show the current state of the data storage
        self.redirect('/update')



def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)

if __name__ == "__main__":
    main()

