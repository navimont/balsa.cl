# -*- coding: UTF-8 -*-
"""Settings file for Balsa

Stefan Wehner (2011)
"""

import os
import logging
from google.appengine.dist import use_library

DEBUG = os.environ['SERVER_SOFTWARE'].startswith('Dev')

# select lates Django library
use_library('django', '1.2')

LOG_LEVEL=logging.INFO
if DEBUG:
    LOG_LEVEL=logging.DEBUG

# number of serach results to be displayed on one page
RESULT_SIZE = 8

STOP_TYPES = set(["STOP", "STATION", "PLACE"])
CONFIRM_TYPES = set(["NO", "UPDATE", "NEW"])

# batch size for writing datasets at import or update
BATCH_SIZE = 50

REGIONS = [
    ("V", u"Valparaíso"),
    ("XIII", u"Metropolitana"),
    ("VIII", u"Bio-Bío"),
    ("III", u"Atacama"),
    ("I", u"Tarapacá"),
    ("X", u"Los Lagos"),
    ("IV", u"Coquimbo"),
    ("IX", u"La Araucanía"),
    ("XII", u"Magallanes"),
    ("II", u"Antofagasta"),
    ("XV", u"Arica/Parinacota"),
    ("XI", u"Aysén"),
    ("VII", u"Maule"),
    ("VI", u"O'Higgins"),
    ("XIV", u"Los Ríos"),
    ("BaWü", u"Baden-Württemberg"),
    ("NY", u"New York"),
    ("OH", u"Ohio")
]
