"""Balsa.cl Handle import and update of stops.
   Module is used by balsa_import and balsa_update

    Stefan Wehner (2011)
"""

import settings
import logging
import os
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from balsa_access import get_current_user_template_values, AdminRequired

class BalsaMain(webapp.RequestHandler):
    """Front page; search for connections"""

    def get(self):
        template_values = get_current_user_template_values(self.request)

        path = os.path.join(os.path.dirname(__file__), "pages/main.html")
        self.response.out.write(template.render(path, template_values))
        return



application = webapp.WSGIApplication([('/', BalsaMain)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

