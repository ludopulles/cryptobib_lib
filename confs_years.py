"""
This library enables to get the list of confs with years from a mybibtex.database
"""

import mybibtex.database
from mybibtex import tools

from config import *

import logging

def get_confs_years(db):
    """ Return a dict associating a conference key to the set of years present in db """
    confs = {}
    for (key, entry) in db.entries.iteritems():
        if key.auth == None:
            continue # we are only interested in papers !
        conf = key.confkey
        if conf not in confs:
            confs[conf] = set()
        confs[conf].add(tools.short_to_full_year(key.year))
    
    return confs

def get_confs_years_inter_from_set(confs):
    """ Convert a dictionnary of conferences (keys) with set of years to a dictionnary of conferences with intervals, i.e., tuples (start year, end year)
    If some years are missing, log it except for hardcoded exceptions """

    missing_years = {
        "AC": set([1993, 1995, 1997]),
        "CCS": set([1995]),
        "EC": set([1983]),
        "ESORICS": set([1991, 1993, 1995, 1997, 1999, 2001]),
        "FSE": set([1995]),
        "ICICS": set([1998, 2000]),
        "ICITS": set([2010]),
        "IMA": set([1996, 1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012]),
        "ISC": set([1998, 2013]),
        "LATIN": set([1993, 1994, 1996, 1997, 1999, 2001, 2003, 2005, 2007, 2009, 2011, 2013]),
        "LC": set([2011]),
        "PAIRING": set([2011]),
        "SCN": set([2003, 2005, 2007, 2009, 2011, 2013]),
    }

    def get_missing_years(conf):
        if conf in missing_years:
            return missing_years[conf]
        else:
            return set()

    def set_to_tuple(conf, years):
        min_year = min(years)
        max_year = max(years)
        years = years | get_missing_years(conf)
        if not (set(range(min_year, max_year+1)) <= years):
            mis_years = set(range(min_year, max_year+1)) - years
            min_year = max(mis_years)+1
            logging.warning("For conference \"{}\", years {} are missing - so min year={} - to add an exception please modify lib/confs_years.py - variable missing_years".format(
                conf,
                ", ".join([str(y) for y in sorted(list(mis_years))]),
                min_year
            ))
        return (min_year, max_year)

    confs_inter = {
        conf: set_to_tuple(conf, confs[conf]) 
        for conf in sorted(confs.iterkeys())
    }
    return confs_inter

def get_confs_years_inter(db):
    return get_confs_years_inter_from_set(get_confs_years(db))
    
