"""Settings file for Balsa"""

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
