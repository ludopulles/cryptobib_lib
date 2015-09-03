# Functions for web/app/controllers/default.py

import re

re_years = re.compile(r"^\s*(\d*)\s*(-\s*(\d*)\s*)?$")

def get_years(confs, vars):
    errors = {}
    years = {}
    nb = 0

    for conf in confs:
        years_conf = vars["years"+conf["key"]]
        r = re_years.match(years_conf)
        if r != None:
            a = r.group(1)
            b = r.group(2)
            c = r.group(3)

            a = None if a=="" else a
            b = None if b=="" else b
            c = None if c=="" else c

            start_year = int(a) if a!=None else a
            end_year   = int(c) if c!=None else c
            end_year   = start_year if b == None else end_year

            if a != None or b != None:
                start_year = max(start_year, conf["start_year"]) if start_year != None else conf["start_year"]
                end_year = min(end_year, conf["end_year"]) if end_year != None else conf["end_year"]

                if start_year > end_year:
                    errors[conf["key"]] = True
                    continue

                nb += 1
                years[conf["key"]] = (start_year, end_year)
        else:
            errors[conf["key"]] = True

    return (errors, years, nb)
