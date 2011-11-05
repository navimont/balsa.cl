"""Helper functions

    Stefan Wehner (2011)
"""

import unicodedata

def plainify(string):
    """Removes all accents and special characters form string and converts
    string to lower case. If the string is made up of several words a list
    of these words is returned.

    Returns an array of plainified strings (splitted at space)
    """
    res = []
    for s1 in string.split(" "):
        s1 = s1.strip(",.;:\\?/!@#$%^&*()[]{}|\"'")
        s1 = unicode(s1)
        s1 = unicodedata.normalize('NFD',s1.lower())
        s1 = s1.replace("`", "")
        s1 = s1.encode('ascii','ignore')
        s1 = s1.replace("~", "")
        s1 = s1.strip()
        if len(s1):
            res.append(s1)

    return res
