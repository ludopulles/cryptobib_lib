"""
This library enables to get the list of confs with years from a mybibtex.database
"""

from mybibtex import tools

import logging


def get_confs_years(db) -> dict:
    """ Return a dict associating a conference key to the set of years present in db """
    confs = {}
    for (key, entry) in db.entries.items():
        if key.auth is None:
            continue  # we are only interested in papers !
        conf = key.confkey
        if conf not in confs:
            confs[conf] = set()
        confs[conf].add(tools.short_to_full_year(key.year))

    return confs


def get_confs_years_inter_from_set(confs: dict, missing_years) -> dict:
    """ Convert a dictionnary of conferences (keys) with set of years
    to a dictionnary of conferences with intervals, i.e., tuples (start year, end year)
    If some years are missing, log it except if missing_years[conf] contain this year """

    def get_missing_years(conf):
        if conf in missing_years:
            return missing_years[conf]
        else:
            return set()

    def set_to_tuple(conf, years):
        min_year = min(years)
        max_year = max(years)
        years = years | get_missing_years(conf)
        if not (set(range(min_year, max_year + 1)) <= years):
            mis_years = set(range(min_year, max_year + 1)) - years
            min_year = max(mis_years) + 1
            logging.warning(
                "For conference \"{}\", years {} are missing - so min year={} "
                "- to add an exception please modify db/config.py - variable missing_years".format(
                    conf,
                    ", ".join([str(y) for y in sorted(list(mis_years))]),
                    min_year
                ))
        return min_year, max_year

    confs_inter = {
        conf: set_to_tuple(conf, confs[conf])
        for conf in sorted(confs.keys())
    }
    return confs_inter


def get_confs_years_inter(db, confs_missing_years):
    return get_confs_years_inter_from_set(get_confs_years(db), confs_missing_years)
