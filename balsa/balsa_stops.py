"""Balsa.cl Handle import and update of stops.
   Module is used by balsa_import and balsa_update

    Stefan Wehner (2011)
"""

import settings
import logging
import os
import yaml
import zipfile
import osmparse
import unicodedata
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
from balsa_dbm import Stop, GovName, StopMeta, GovMeta
from balsa_tools import plainify
from balsa_access import get_current_user_template_values



class BalsaStopStoreTask(webapp.RequestHandler):
    """Background tasks parses osm data and stores stops, stations and places
    in the datastore.
    """

    # store the list stop entities to be written to the datastore
    # in a batch operation
    _stop_data = None
    # Hold the stop counter dataset instance
    _stop_meta = None
    # Hold the giv data counter dataset instance
    _gov_meta = None

    @classmethod
    def new_stop(cls, node, kind):
        """Returns stop in the correct entity group"""
        stop = Stop(parent=cls._stop_meta, osm_id=node.osm_id, location=db.GeoPt(lat=node.lat, lon=node.lon))
        # uses the update function to fill all fields
        return cls.update_stop(stop, node, kind)

    @classmethod
    def update_stop(cls, stop, node, kind):
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
            if k.startswith('is_in:'):
                gov.append(v)
        stop.ascii_names = []
        for name in stop.names:
            stop.ascii_names.extend(plainify(name))
        for name in gov:
            stop.ascii_names.extend(plainify(name))
        # get gov entity data for the adminstrative hierarchy we found
        stop.gov = BalsaStopStoreTask.gov_entity(gov)
        return stop

    @classmethod
    def add(cls, stop, confirm='NO'):
        if stop.stop_type == 'STOP' and confirm == 'NO':
            cls._stop_meta.counter_stop_no_confirm += 1
        elif stop.stop_type == 'STOP' and confirm == 'UPDATE':
            cls._stop_meta.counter_stop_update_confirm += 1
        elif stop.stop_type == 'STOP' and confirm == 'NEW':
            cls._stop_meta.counter_stop_new_confirm += 1
        elif stop.stop_type == 'PLACE' and confirm == 'NO':
            cls._stop_meta.counter_place_no_confirm += 1
        elif stop.stop_type == 'PLACE' and confirm == 'UPDATE':
            cls._stop_meta.counter_place_update_confirm += 1
        elif stop.stop_type == 'PLACE' and confirm == 'NEW':
            cls._stop_meta.counter_place_new_confirm += 1
        elif stop.stop_type == 'STATION' and confirm == 'NO':
            cls._stop_meta.counter_station_no_confirm += 1
        elif stop.stop_type == 'STATION' and confirm == 'UPDATE':
            cls._stop_meta.counter_station_update_confirm += 1
        elif stop.stop_type == 'STATION' and confirm == 'NEW':
            cls._stop_meta.counter_station_new_confirm += 1
        else:
            assert False, "Invalid stop type or confirm %s/%s" % (stop.stop_type, confirm)

        stop.confirm = confirm
        cls._stop_data.append(stop)
        # write a batch if a certain quantity has accumulated
        if len(cls._stop_data) % settings.BATCH_SIZE == 0:
            # store fields and counters together in transaction
            db.run_in_transaction(cls.store)

    @classmethod
    def store(cls):
        """Store data in transaction"""
        db.put(cls._stop_data)
        db.put(cls._stop_meta)
        cls._stop_data = []

    @classmethod
    def gov_entity(cls,gov):
        """Store new government entity or return existing one"""
        if not gov:
            gov_key_name = '<no gov>'
        else:
            gov_key_name = ":".join(gov)
        gov_entity = GovName.get_by_key_name(gov_key_name, parent=cls._gov_meta)
        if not gov_entity:
            logging.debug("No gov entry found for %s" % (gov_key_name))
            # update Counter
            cls._gov_meta.counter += 1
            gov_entity = GovName(parent=cls._gov_meta, key_name=gov_key_name)
            gov_entity.gov_names = gov
            def gov_store():
                gov_entity.put()
                cls._gov_meta.put()
            db.run_in_transaction(gov_store)

        return gov_entity

    @staticmethod
    def import_node_cb(node, kind):
        """Callback function processes nodes from osm data"""
        stop = BalsaStopStoreTask.new_stop(node, kind)

        # accumulate some greater number in _stop_data for efficient batch write to datastore
        BalsaStopStoreTask.add(stop, confirm='NO')

    @staticmethod
    def update_node_cb(node, kind):
        """Callback function. Process nodes from osm data

        Different to import_node_cb (above) look for existing nodes with the
        same data and discard identical ones. Queue changed nodes and new nodes
        for confirmation.
        """
        # look for existing node with the same osm_id
        old_stop = Stop.all().filter("osm_id =", node.osm_id).get()
        if old_stop and old_stop.confirm != 'NO':
            # There is already an unconfirmed stop with the osm_id
            # queued for confirmation. Overwrite it.
            stop = BalsaStopStoreTask.update_stop(old_stop, node, kind)
            stop.put()
            logging.debug("REPLACE")
            return
        else:
            # create stop entity from node data
            stop = BalsaStopStoreTask.new_stop(node, kind)
            if old_stop:
                logging.debug("compare %s <==> %s" % (old_stop,stop))
                if old_stop == stop:
                    # no change
                    logging.debug("no change")
                    return
                else:
                    logging.debug("UPDATE")
                    # accumulate some greater number in _stop_data for efficient batch write to datastore
                    BalsaStopStoreTask.add(stop, confirm='UPDATE')
            else:
                logging.debug("NEW")
                BalsaStopStoreTask.add(stop, confirm='NEW')

            return

    def post(self):
        blob_info = blobstore.BlobInfo.get(self.request.get('osmdata'))
        logging.info("Retrieved %d bytes for processing." % (blob_info.size))

        # import or upload?
        action = self.request.get('action')
        assert action, "Import or upload? No action specified."

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

        BalsaStopStoreTask._stop_data = []
        BalsaStopStoreTask._stop_meta = StopMeta.all().get()
        BalsaStopStoreTask._gov_meta = GovMeta.all().get()

        # parse blob and call node_cb on discovery of a Place, Stop or Station
        try:
            if action == 'import':
                osmparse.OSMContentHandler(file_reader, (osmparse.StopAttr, BalsaStopStoreTask.import_node_cb))
            else:
                osmparse.OSMContentHandler(file_reader, (osmparse.StopAttr, BalsaStopStoreTask.update_node_cb))

            # store fields and counters together in transaction
            db.run_in_transaction(BalsaStopStoreTask.store)
            memcache.set('%s_status' % action, "%s finished successfully." % action.title(), time=30)

        except SyntaxError:
            logging.error("Could not parse uploaded file.")
            memcache.set('%s_status' % action, "%s failed. Could not parse data." % action.title(), time=30)

        # free space in blobstore
        blob_info.delete()

class BalsaStopUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    """Is called when an osm data file has been uploaded to the blobstore"""

    def post(self):
        login_user = users.get_current_user()
        if not users.is_current_user_admin():
            logging.warning("User is not admin: %s" % (login_user))
            self.error(500)
            return

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

