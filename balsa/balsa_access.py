"""Functions for user authentication

    Stefan Wehner (2011)
"""

import os
import logging
import settings
import calendar
from google.appengine.ext import db
from google.appengine.api import users


def get_current_user_template_values(request, template_values=None):
    """Put together a set of template values regarding the logged in user.

    Needed for rendering the web page with some basic information about the user.
    """
    if not template_values:
        template_values = {}

    login_user = users.get_current_user()
    if not login_user:
        template_values['signed_in'] = False
        template_values['loginout_url'] = '/login'
        template_values['loginout_text'] = 'login'
        template_values['login_user_place'] = ""
        template_values['login_user_lat'] = 40.69
        template_values['login_user_lon'] = -73.97
        return template_values

    if users.is_current_user_admin():
        template_values['body_background_class'] = "balsa-admin-background"

    template_values['host'] = request.host
    template_values['signed_in'] = True
    template_values['login_user_key'] = login_user.email()
    template_values['loginout_url'] = users.create_logout_url('/')
    try:
        template_values['loginout_text'] = 'logout %s' % (login_user.email())
    except db.ReferencePropertyResolveError:
        template_values['loginout_text'] = 'logout'

    return template_values

def AdminRequired(target):
    """Decorator for RequestHandler methods get and put.

    Has the currently logged in user (google account) admin rights?

    Also prepares the google user object and some
    template_values and calls the target function with those as parameters.
    """
    def redirectToLoginPage(self):
        self.redirect('/login')
        return

    def wrapper (self):
        # find my own Person object
        login_user = users.get_current_user()
        if not login_user:
            return redirectToLoginPage
        else:
            # Add extra parameters
            kwargs = {'login_user': login_user,
                      'template_values': get_current_user_template_values(self.request)}
            return target(self, **kwargs)

    return wrapper

