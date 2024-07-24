# Functions for web/app/controllers/default.py

# Note: we need to target Python 3.6
# and thus cannot use the new syntax tuple[dict, dict, dict]
# and instead need Tuple[dict, dict, dict]

from typing import Tuple
import re

re_years = re.compile(r"^\s*(\d*)\s*(-\s*(\d*)\s*)?$")


def get_years(confs: iter, vars: dict) -> Tuple[dict, dict, int]:
    errors = {}
    years = {}
    nb = 0

    for conf in confs:
        years_conf = vars["years" + conf["key"]]
        r = re_years.match(years_conf)
        if r is not None:
            a = r.group(1)
            b = r.group(2)
            c = r.group(3)

            a = None if a == "" else a
            b = None if b == "" else b
            c = None if c == "" else c

            start_year = int(a) if a is not None else a
            end_year = int(c) if c is not None else c
            end_year = start_year if b is not None else end_year

            if a is not None or b is not None:
                start_year = max(start_year, conf["start_year"]) if start_year != None else conf["start_year"]
                end_year = min(end_year, conf["end_year"]) if end_year != None else conf["end_year"]

                if start_year > end_year:
                    errors[conf["key"]] = True
                    continue

                nb += 1
                years[conf["key"]] = (start_year, end_year)
        else:
            errors[conf["key"]] = True

    return errors, years, nb
