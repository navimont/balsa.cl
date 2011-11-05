"""Balsa login pages

   Stefan Wehner (2011)
"""

import settings
import logging
import os
import calendar
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.db import Key
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


class OpenIdLogin(webapp.RequestHandler):
    """creates the openid login url and redirects the browser"""

    def get(self):
        openid_url = self.request.GET.get('openid_identifier')
        if not openid_url:
            self.redirect('/_ah/login_required')
        else:
            self.redirect(users.create_login_url(dest_url='/', federated_identity=openid_url))


class BalsaLogin(webapp.RequestHandler):
    """Login page

    Anonymous: Present login page
    Logged in users who use weschnitz for the first time: they need to enter their data
    Logged in users who are known users: go to main page
    """

    def get(self):
        login_user = users.get_current_user()

        # not logged in. display login options
        if not login_user:
            path = os.path.join(os.path.dirname(__file__), 'pages/balsa_login.html')
            self.response.out.write(template.render(path, {}))
            return

        self.redirect('/')
        return

# PAGE FLOW:
# /_ah/login_required or
# /login              presents the openId logos to choose from
# /openid_login       takes the chosen provider (parameter ) and forwards there for the login

application = webapp.WSGIApplication([('/openid_login', OpenIdLogin),
                                      ('/login', BalsaLogin),
                                      ('/_ah/login_required', BalsaLogin),
                                      ],debug=settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

