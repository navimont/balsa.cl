"""Balsa.cl import REST Api

    Stefan Wehner (2011)
"""

import settings
import logging
import os
import datetime
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
from balsa_dbm import Stop, StopMeta, Country, Region, Comuna
from balsa_access import AdminRequired
from balsa_stops import BalsaStopUploadHandler, BalsaStopStoreTask


class BalsaPurgeTask(webapp.RequestHandler):
    """Delete all data in the stop table"""

    def post(self):
        counter = StopMeta().all().get()
        def delete():
            db.delete(Stop.all().ancestor(counter))
            counter.zero_all()
            counter.put()
        db.run_in_transaction(delete)
        memcache.set('import_status', "Deletion finished.", time=30)


class BalsaPurge(webapp.RequestHandler):
    """Start a background job to delete all data in the stop table"""

    @AdminRequired
    def get(self, login_user=None, template_values={}):
        # start background process
        taskqueue.add(url='/purge/delete', queue_name='import')

        memcache.set('import_status', "Deleting all data", time=30)
        self.redirect('/update')


class BalsaImportSelect(webapp.RequestHandler):
    """Bring up page to select file for import into database"""

    @AdminRequired
    def get(self, login_user=None, template_values={}):

        # Check for existing data. Import is only done with an empty database
        # Note: If an area is imported which has no intersection with the existing
        #       data it is a differrent matter. This will be handled in proper
        #       time. For the moment we concentrate on Chile.
        if Stop.all().get():
            self.redirect('/update')

        # set counter fields to zero
        counter_fields = StopMeta()
        counter_fields.zero_all()
        counter_fields.last_update = datetime.datetime(2011,1,1)
        counter_fields.put()

        template_values['upload_url'] = blobstore.create_upload_url('/import/upload')

        path = os.path.join(os.path.dirname(__file__), "pages/import_select.html")
        self.response.out.write(template.render(path, template_values))
        return


application = webapp.WSGIApplication([('/import', BalsaImportSelect),
                                      ('/purge', BalsaPurge),
                                      ('/purge/delete', BalsaPurgeTask),
                                      ('/import/upload', BalsaStopUploadHandler),
                                      ('/import/store', BalsaStopStoreTask)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

