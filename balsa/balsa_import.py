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
from balsa_dbm import Stop, GovName, StopMeta, GovMeta
from balsa_tools import plainify
from balsa_access import get_current_user_template_values
from balsa_stops import BalsaStopUploadHandler, BalsaStopStoreTask

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
        counter_fields = StopMeta(counter_stop_no_confirm = 0,
                                  counter_stop_new_confirm = 0,
                                  counter_stop_update_confirm = 0,
                                  counter_station_no_confirm = 0,
                                  counter_station_new_confirm = 0,
                                  counter_station_update_confirm = 0,
                                  counter_place_no_confirm = 0,
                                  counter_place_new_confirm = 0,
                                  counter_place_update_confirm = 0)
        counter_fields.put()
        counter_gov = GovMeta(counter = 0)
        counter_gov.put()

        template_values['upload_url'] = blobstore.create_upload_url('/import/upload')

        path = os.path.join(os.path.dirname(__file__), "pages/import_select.html")
        self.response.out.write(template.render(path, template_values))
        return


application = webapp.WSGIApplication([('/import', BalsaImportSelect),
                                      ('/import/upload', BalsaStopUploadHandler),
                                      ('/import/store', BalsaStopStoreTask)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

