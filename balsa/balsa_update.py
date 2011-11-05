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

class BalsaUpdate(webapp.RequestHandler):
    """Display the update page with statistics abput the current data"""

    def get(self):
        login_user = users.get_current_user()
        template_values = get_current_user_template_values (login_user)

        if not users.is_current_user_admin():
            logging.warning("Access to %s failed. User is not admin: %s" % (self.__class__,login_user))
            self.error(500)
            return

        # Check for existing data.
        template_values['production_num_stops'] = StopMeta.all().filter("confirm =", "NO").filter("stop_type =", "STOP").get().counter
        template_values['production_num_stations'] = StopMeta.all().filter("confirm =", "NO").filter("stop_type =", "STATION").get().counter
        template_values['production_num_places'] = StopMeta.all().filter("confirm =", "NO").filter("stop_type =", "PLACE").get().counter
        # confirmation outstanding
        template_values['update_num_stops'] = StopMeta.all().filter("confirm =", "UPDATE").filter("stop_type =", "STOP").get().counter
        template_values['update_num_stations'] = StopMeta.all().filter("confirm =", "UPDATE").filter("stop_type =", "STATION").get().counter
        template_values['update_num_places'] = StopMeta.all().filter("confirm =", "UPDATE").filter("stop_type =", "PLACE").get().counter
        template_values['new_num_stops'] = StopMeta.all().filter("confirm =", "NEW").filter("stop_type =", "STOP").get().counter
        template_values['new_num_stations'] = StopMeta.all().filter("confirm =", "NEW").filter("stop_type =", "STATION").get().counter
        template_values['new_num_places'] = StopMeta.all().filter("confirm =", "NEW").filter("stop_type =", "PLACE").get().counter

        template_values['upload_url'] = blobstore.create_upload_url('/import/upload')

        path = os.path.join(os.path.dirname(__file__), "pages/update.html")
        self.response.out.write(template.render(path, template_values))
        return

class BalsaConfirmUpdate(webapp.RequestHandler):
    """Confirm data for update"""

    def get(self):
        self.redirect('/update')

class BalsaConfirmNew(webapp.RequestHandler):
    """Confirm new data (or replaced data)"""

    def get(self):
        self.redirect('/update')


application = webapp.WSGIApplication([('/update', BalsaUpdate),
                                      ('/update/confirm/update', BalsaConfirmUpdate),
                                      ('/update/confirm/new', BalsaConfirmNew)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

