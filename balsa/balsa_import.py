"""Balsa.cl import REST Api

    Stefan Wehner (2011)
"""

import settings
import logging
import os
import yaml
import zipfile
import osmparse
from django.utils import simplejson as json
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
from balsa_dbm import Stop, GovName, StopMeta
from balsa_tools import plainify
from balsa_access import get_current_user_template_values

class BalsaImportSelect(webapp.RequestHandler):
    """Bring up page to select file for import into database"""

    def get(self):
        login_user = users.get_current_user()
        template_values = get_current_user_template_values (login_user)

        if not users.is_current_user_admin():
            logging.warning("Access to BalsaImportSelect failed. User is not admin: %s" % (login_user))
            self.error(500)
            return

        # Check for existing data. Import is only done with an empty database
        # Note: If an area is imported which has no intersection with the existing
        #       data it is a differrent matter. This will be handled in proper
        #       time. For the moment we concentrate on Chile.
        if Stop.all().get():
            self.redirect('/update')

        # set counter fields to zero
        counter_fields=[]
        for stop in settings.STOP_TYPES:
            for con in settings.CONFIRM_TYPES:
                counter_fields.append(StopMeta(stop_type=stop, confirm=con, counter=0))
        db.put(counter_fields)

        template_values['upload_url'] = blobstore.create_upload_url('/import/upload')

        path = os.path.join(os.path.dirname(__file__), "pages/import_select.html")
        self.response.out.write(template.render(path, template_values))
        return


class StopData(object):
    """Helper class to deal with Stop data sets and their associated counter field"""

    def __init__(self, kind):
        self.counter = StopMeta.all().filter("confirm =", "NO").filter("stop_type =", kind).get()
        self.kind = kind
        self.data = []

    def new_stop(self,osm_id,location):
        """Returns stop in the correct entity group"""
        return Stop(parent=self.counter, osm_id=osm_id, location=location, stop_type=self.kind)

    def add(self, dataset):
        self.counter.counter += 1
        self.data.append(dataset)
        # write a batch if a certain quantity has accumulated
        if len(self.data) % settings.BATCH_SIZE == 0:
            # store fields and counters together in transaction
            db.run_in_transaction(self.store)

    def store(self):
        """Store data in transaction"""
        db.put(self.data)
        db.put(self.counter)
        self.data = []

    def __str__(self):
        stops = ""
        for stop in self.data:
            stops += ", "+str(stop.osm_id)
        return "<StopData> %s %s" % (self.counter, stops)

class BalsaImportStoreTask(webapp.RequestHandler):
    """Background tasks parses osm data and stores stops, stations and places
    in the datastore.
    """
    _stop_data = {}

    @staticmethod
    def node_cb(node, kind):
        """Callback function processes nodes from osm data"""
        logging.info("Found relevant node in OSM data: %s %s" % (kind,node))

        stop = BalsaImportStoreTask._stop_data[kind].new_stop(osm_id=node.osm_id, location=db.GeoPt(lat=node.lat, lon=node.lon))
        names = [node.name]
        gov = []
        for k,v in node.attr.items():
            if k in ['alt_name', 'nat_name', 'old_name', 'reg_name', 'loc_name', 'official_name']:
                names.append(v)
            if k.startswith('name:'):
                # language specific
                names.append(v)
            # adminstrative regions
            if k.startswith('is_in:'):
                gov.append(v)
        stop.names = names
        ascii_names = []
        for name in names:
            ascii_names.extend(plainify(name))
        for name in gov:
            ascii_names.extend(plainify(name))
        stop.asciii_names = ascii_names

        # look for gov entity and store new one if none was found
        gov_entity = None
        if gov:
            gov_entity = GovName.get_by_key_name(":".join(gov))
            if not gov_entity:
                gov_entity = GovName(key_name=":".join(gov))
                gov_entity.put()
        stop.gov = gov_entity

        stop.update_location()
        BalsaImportStoreTask._stop_data[kind].add(stop)



    def post(self):
        blob_info = blobstore.BlobInfo.get(self.request.get('osmdata'))
        logging.info("Retrieved %d bytes for processing." % (blob_info.size))
        memcache.set('import_status', "Parsing import data.", time=100)

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

        # store the counter entities in a class variable
        for stop_type in settings.STOP_TYPES:
            BalsaImportStoreTask._stop_data[stop_type] = StopData(stop_type)

        # parse blob and call node_cb on discovery of a Place, Stop or Station
        try:
            osmparse.OSMContentHandler(file_reader, (osmparse.StopAttr, BalsaImportStoreTask.node_cb))

            # store fields and counters together in transaction
            for stop_type in settings.STOP_TYPES:
                logging.debug(BalsaImportStoreTask._stop_data[stop_type])
                db.run_in_transaction(BalsaImportStoreTask._stop_data[stop_type].store)

        except SyntaxError:
            logging.error("Could not parse import file.")

        # free space in blobstore
        blob_info.delete()

class BalsaImportUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    """Is called when an osm data file has been uploaded to the blobstore"""

    def post(self):
        login_user = users.get_current_user()
        if not users.is_current_user_admin():
            logging.warning("Access to BalsaImportUploadHandler failed. User is not admin: %s" % (login_user))
            self.error(500)
            return

        memcache.set('import_status', "Queued import task", time=30)

        upload_files = self.get_uploads('osmdata')
        blob_info = upload_files[0]

        # start background process
        taskqueue.add(url='/import/store', queue_name="import", params={'compressed': self.request.get('compressed', ""), 'osmdata': blob_info.key()})

        # redirect to update page which will show the current state of the data storage
        self.redirect('/update')


application = webapp.WSGIApplication([('/import', BalsaImportSelect),
                                      ('/import/upload', BalsaImportUploadHandler),
                                      ('/import/store', BalsaImportStoreTask)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

