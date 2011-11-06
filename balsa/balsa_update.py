"""Balsa.cl import REST Api

    Stefan Wehner (2011)
"""

import settings
import logging
import os
import yaml
import zipfile
import osmparse
import geo.geomath
import geo.geomodel
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
from balsa_stops import BalsaStopStoreTask, BalsaStopUploadHandler

class BalsaUpdate(webapp.RequestHandler):
    """Display the update page with statistics abput the current data"""

    def get(self):
        login_user = users.get_current_user()
        template_values = get_current_user_template_values (login_user)

        if not users.is_current_user_admin():
            logging.warning("Access to %s failed. User is not admin: %s" % (self.__class__,login_user))
            self.error(500)
            return

        # is import or update going on?
        template_values['update_status'] = memcache.get('update_status')
        template_values['import_status'] = memcache.get('import_status')

        # Check for existing data.
        try:
            counter = StopMeta.all().get()
            template_values['production_num_stops'] = counter.counter_stop_no_confirm
            template_values['production_num_stations'] = counter.counter_station_no_confirm
            template_values['production_num_places'] = counter.counter_place_no_confirm
            # confirmation outstanding
            template_values['update_num_stops'] = counter.counter_stop_update_confirm
            template_values['update_num_stations'] = counter.counter_station_update_confirm
            template_values['update_num_places'] = counter.counter_place_update_confirm
            template_values['new_num_stops'] = counter.counter_stop_new_confirm
            template_values['new_num_stations'] = counter.counter_station_new_confirm
            template_values['new_num_places'] = counter.counter_place_new_confirm
            # Administrative hierarchy
            template_values['gov_num'] = GovMeta.all().get().counter
        except AttributeError:
            # no data in database. Redirect to import page
            self.redirect('/import')

        for x in GovName.all():
            logging.debug(x)

        template_values['upload_url'] = blobstore.create_upload_url('/update/upload')
        path = os.path.join(os.path.dirname(__file__), "pages/update.html")
        self.response.out.write(template.render(path, template_values))
        return



class BalsaConfirmUpdate(webapp.RequestHandler):
    """Confirm data for update"""

    def get(self):
        login_user = users.get_current_user()
        template_values = get_current_user_template_values (login_user)

        if not users.is_current_user_admin():
            logging.warning("Access to %s failed. User is not admin: %s" % (self.__class__,login_user))
            self.error(500)
            return

        # hold update query in memcache
        q_update = memcache.get('update')
        if not q_update:
            q_update = Stop.all().filter('confirm =', 'UPDATE')
            memcache.set('update', q_update)

        update = q_update.get()
        if not update:
            # nothing to do
            self.redirect('/update')
            return

        # get corresponding production data
        production = Stop.all().filter('osm_id =', update.osm_id).filter('confirm =', 'NO').get()
        assert production, "Failed to fetch prodcution data for update osm_id=%d" % (update.osm_id)

        compare={}
        compare['key'] = str(update.key)
        compare['data'] = []
        data = {}
        data['type'] = 'Stop type'
        data['production'] = production.stop_type
        data['update'] = update.stop_type
        compare['data'].append(data)
        data['type'] = 'Location (lat)'
        data['production'] = production.location.lat
        data['update'] = update.location.lat
        compare['data'].append(data)
        data['type'] = 'Location (lon)'
        data['production'] = production.location.lon
        data['update'] = update.location.lon
        compare['data'].append(data)
        data['type'] = 'Name(s)'
        data['production'] = ", ".join(production.names)
        data['update'] = ", ".join(update.names)
        compare['data'].append(data)
        data['type'] = 'Location zoom'
        data['production'] = ", ".join(production.gov.gov_names)
        data['update'] = ", ".join(update.gov.gov_names)
        compare['data'].append(data)
        template_values['compare'] = compare

        counter = StopMeta.all().get()
        template_values['update_num_stops'] = counter.counter_stop_update_confirm
        template_values['update_num_stations'] = counter.counter_station_update_confirm
        template_values['update_num_places'] = counter.counter_place_update_confirm

        path = os.path.join(os.path.dirname(__file__), "pages/confirm_update.html")
        self.response.out.write(template.render(path, template_values))
        return

class BalsaConfirmNew(webapp.RequestHandler):
    """Confirm new data (or replaced data)"""

    def get(self):
        login_user = users.get_current_user()
        template_values = get_current_user_template_values (login_user)

        if not users.is_current_user_admin():
            logging.warning("Access to %s failed. User is not admin: %s" % (self.__class__,login_user))
            self.error(500)
            return

        # hold update query in memcache
        q_new = memcache.get('new')
        if not q_new:
            q_new = Stop.all().filter('confirm =', 'NEW')
            memcache.set('new', q_new)

        offset = int(self.request.get("offset", "0"))
        new = q_new.fetch(limit=1, offset=offset)
        template_values['offset'] = offset+1
        if not new:
            # nothing to do
            self.redirect('/update')
            return
        new = new[0]

        # find datasets nearby
        query = Stop.all().filter('confirm =', 'NO')
        proximity = geo.geomodel.GeoModel.proximity_fetch(query, new.location, max_results=6, max_distance=500)

        compare=[]
        stop = {}
        stop['description'] = 'New:'
        stop['type'] = new.stop_type
        stop['name'] = ", ".join(new.names)
        stop['lat'] = new.location.lat
        stop['lon'] = new.location.lon
        stop['new'] = True
        compare.append(stop)
        for pstop in proximity:
            stop = {}
            # calculate distance to new point
            dist = geo.geomath.distance(new.location,pstop.location)
            stop['description'] = 'at %4.0f meters' % (dist)
            stop['type'] = pstop.stop_type
            stop['name'] = ", ".join(pstop.names)
            stop['lat'] = pstop.location.lat
            stop['lon'] = pstop.location.lon
            stop['new'] = False
            compare.append(stop)
        template_values['compare'] = compare

        counter = StopMeta.all().get()
        template_values['new_num_stops'] = counter.counter_stop_new_confirm
        template_values['new_num_stations'] = counter.counter_station_new_confirm
        template_values['new_num_places'] = counter.counter_place_new_confirm

        path = os.path.join(os.path.dirname(__file__), "pages/confirm_new.html")
        self.response.out.write(template.render(path, template_values))
        return


application = webapp.WSGIApplication([('/update', BalsaUpdate),
                                      ('/update/upload', BalsaStopUploadHandler),
                                      ('/update/store', BalsaStopStoreTask),
                                      ('/update/confirm/update', BalsaConfirmUpdate),
                                      ('/update/confirm/new', BalsaConfirmNew)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

