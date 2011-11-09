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
from balsa_dbm import Stop, Comuna, Country, Region
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

        # look for city first
        match_query = ""
        comunas = []
        for query in queries:
            query0 = query
            query1 = query0+u"\ufffd"
            q_com = db.Query(Comuna, keys_only=True)
            q_com.filter("ascii_names >=", query0)
            q_com.filter("ascii_names <", query1)
            com = q_com.fetch(4)
            # choose the result(s) with max. 3 matches
            if len(com) > 0 and len(com) < 4:
                # use the results if better then the results from a previous string part
                if not comunas or len(com) < len(comunas):
                    comunas = com
                    match_query = query
        if comunas:
            logging.debug("Found cities: %s" % ",".join([ckey.name() for ckey in comunas]))
            # if one city was matched, remove the match query
            # saves us time in the stop lookup
            if len(comunas) == 1:
                queries.remove(match_query)

        all_stops = []
        for stop in settings.STOP_TYPES:
            if stop == "STOP" and len(comunas) != 1:
                # look only for stops if we know the city for sure
                continue
            all_words = []
            for query in queries:
                query0 = query
                query1 = query0+u"\ufffd"
                # look up plain query string in list of plain keys
                q_pk = db.Query(Stop, keys_only=True)
                if stop == "STOP" and comunas:
                    q_pk.filter("comuna =", comunas[0])
                q_pk.filter("ascii_names >=", query0)
                q_pk.filter("ascii_names <", query1)
                q_pk.filter("stop_type =", stop)
                stops = q_pk.fetch(7)
                logging.debug("%s %d" %(stop,len(stops)))
                logging.debug(stops)
                # convert from list to set
                all_words.append(set(stops))
            # At this point we have the result sets (stop keys) for the words in the query.
            # Now we need to find the Stop entities (hopefully very few) which are in _all_
            # of the sets
            stops = all_words[0]
            for stop in all_words[1:]:
                stops = stops.intersection(stop)
            all_stops.extend(stops)


        # retrieve entries from database
        stop_entries = db.get(list(all_stops))
        grouped = {'STOP': [], 'PLACE': [], 'STATION': []}
        for stop in stop_entries:
            name = ""
            if stop.names:
                name = stop.names[0]
            if len(stop.names) > 1:
                name = "%s (%s)" % (name, ", ".join(stop.names[1:]))
            if stop.comuna:
                name = "%s, %s" % (name, stop.comuna.name)
            if stop.region:
                name = "%s, %s" % (name, stop.region.short_name)
            if stop.country:
                name = "%s, %s" % (name, stop.country.name)
            grouped[stop.stop_type].append(name)
        # return in the order: PLACE, STATION, STOP
        res = grouped['PLACE']
        res.extend(grouped['STATION'])
        if len(comunas) == 1:
            res.extend(grouped['STOP'])

        self.response.headers['Content-Type'] = "text/plain"
        self.response.out.write(json.dumps(res))


application = webapp.WSGIApplication([('/lookup', LookupStop)],settings.DEBUG)

def main():
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

