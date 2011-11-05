"""Functions for user authentication

    Stefan Wehner (2011)
"""

import os
import logging
import settings
import calendar
from google.appengine.ext import db
from google.appengine.api import users


def get_current_user_template_values(login_user, template_values=None):
    """Put together a set of template values regarding the logged in user.

    Needed for rendering the web page with some basic information about the user.
    """
    if not template_values:
        template_values = {}

    if not login_user:
        template_values['signed_in'] = False
        template_values['loginout_url'] = '/login'
        template_values['loginout_text'] = 'login'
        template_values['login_user_place'] = ""
        template_values['login_user_lat'] = 40.69
        template_values['login_user_lon'] = -73.97
        return template_values


    template_values['signed_in'] = True
    template_values['login_user_key'] = login_user.email()
    template_values['loginout_url'] = users.create_logout_url('/')
    try:
        template_values['loginout_text'] = 'logout %s' % (login_user.email())
    except db.ReferencePropertyResolveError:
        template_values['loginout_text'] = 'logout'


    return template_values
