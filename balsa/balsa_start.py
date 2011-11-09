"""Finds fits in STOP for user's start and destination entered

   Stefan Wehner (2011)

"""

import settings
import logging
import os
from django.utils import simplejson as json
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.db import Key
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache
from balsa_dbm import Stop
from balsa_stops import Normalize

class LookupStop(webapp.RequestHandler):
    """Lookup function for search term.

    Splits term if more than one word and looks for contacts which have _all_
    search terms in their relevant(indexed) fields.
    """

    def get(self):
        queries = Normalize.normalize(self.request.get("term", None))
        if not queries:
            self.response.headers['Content-Type'] = "text/plain"
            self.response.out.write("{}")
            return

        logging.debug("lookup stops for %s" % " ".join(queries))

        all_stops = []
        for query in queries:
            stops = []
            query0 = query
            query1 = query0+u"\ufffd"
            # look up plain query string in list of plain keys
            q_pk = db.Query(Stop, keys_only=True)
            q_pk.filter("ascii_names >=", query0)
            q_pk.filter("ascii_names <", query1)
            for key in q_pk:
                # insert stop key
                stops.append(key)
            # convert from list to set
            all_stops.append(set(stops))

        # At this point we have the result sets (stop keys) for the words in the query.
        # Now we need to find the Stop entities (hopefully very few) which are in _all_
        # of the sets
        stops = all_stops[0]
        for stop in all_stops[1:]:
            stops = stops.intersection(stop)

        # retrieve entries from database
        stop_entries = db.get(list(stops))
        grouped = {'STOP': [], 'PLACE': [], 'STATION': []}
        for stop in stop_entries:
            grouped[stop.stop_type].append(" ".join(stop.names))
        # return in the order: PLACE, STATION, STOP
        res = grouped['PLACE']
        res.extend(grouped['STATION'])
        res.extend(grouped['STOP'])

        self.response.headers['Content-Type'] = "text/plain"
        self.response.out.write(json.dumps(res))


application = webapp.WSGIApplication([('/lookup', LookupStop)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

