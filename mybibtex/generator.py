

import codecs

from .database import *
from . import tools

import io
from abc import ABCMeta, abstractmethod
import logging

# WARNING: do not forge to set this variable to the correct config module when loading this module
# FIXME: need to remove this dirty hack!
config = None

class EntryFilter(object, metaclass=ABCMeta):
    """ Composable entry filters: it is possible to compose a filter FilterA with a filter FilterB by instantiating FilterA(FilterB()) """

    def __init__(self, filter_and=None):
        self.filter_and = filter_and

    @abstractmethod
    def is_selected(self, key, entry):
        """ Return true if the key, entry has to be selected and false otherwise"""
        pass

    def filter(self, entries):
        entries = iter(entries.items()) if self.filter_and == None else self.filter_and.filter(entries)
        for (k,e) in entries:
            if self.is_selected(k, e):
                yield (k,e)

class FilterPaper(EntryFilter):
    """ select papers and filters out conf """

    def is_selected(self, k, e):
        return k.auth != None

class FilterConf(EntryFilter):
    def __init__(self, confkey, filter_and=None):
        """ conf is the short name for conf EC, C, ... """
        super(FilterConf, self).__init__(filter_and = filter_and)
        self.confkey = confkey

    def is_selected(self, k, e):
        return k.confkey == self.confkey

class EntrySort(object, metaclass=ABCMeta):
    @abstractmethod
    def key(self, ke):
        pass

    def sort(self, entries):
        return sorted(entries, key=self.key)

class SortConfYearPage(EntrySort):
    def get_pages(self, key, entry):
        if "pages" in entry.fields:
            try:
                pages = entry.fields["pages"].expand().split("--")
                if len(pages) == 1:
                    return (pages[0], pages[0])
                elif len(pages) == 2:
                    return (pages[0], pages[1])
                else:
                    logging.warning("Problem in entry \"{0}\": incorrect pages !".format(key))
                    return ("0","0")
            except ValueError as e:
                logging.warning("Problem in entry \"{0}\": incorrect pages !".format(key))
                return ("0","0")
        else:
            return ("0","0")
        # Previously pages were integers but because of LIPIcs, pages can now be of the form 5:1--5:10

    def proc_year(self, year):
        full_year = tools.short_to_full_year(year)
        return 9999-full_year # to reverse the order !

    def proc_confkey(self, confkey):
        if confkey in config.confs:
            return ("a-" if config.confs[confkey]["type"] == "conf" else "b-") + config.confs[confkey]["name"]
        else:
            return "xxxxx" + confkey

    def proc_dis(self, e):
        if "crossref" not in e.fields:
            return ""
        else:
            return EntryKey.from_string(e.fields["crossref"].expand()).dis

    pattern_eprint = re.compile(r"^Cryptology ePrint Archive, Report (\d*)/(\d*)")

    def proc_eprint(self, e):
        """ This function is used to sort correctly eprint """
        empty = "xxxx/xxxxx"
        if "howpublished" not in e.fields:
            return empty

        m = self.pattern_eprint.match(e.fields["howpublished"].expand())
        if not m:
            return empty # not an eprint

        return "{:0>4d}/{:0>5d}".format(int(m.group(1)), int(m.group(2)))

    def proc_int_descending(self, val: str):
        """ proc_int_descending is used to convert the value val into an integer so that
        when the value val decreases, the integer increases.
        Assumes that either val is always an integer or is always a non-integer string """
        if val == "":
            return 0
        if not val.isdigit():
            # Convert the value into an integer, looking at the value as a big-endian byte-array
            val = int(codecs.encode(val.encode("utf8"), 'hex'), 16)
        return int(1e20-1) - int(val)

    def proc_volume(self, e):
        if "volume" not in e.fields:
            return 0
        else:
            return self.proc_int_descending(e.fields["volume"].expand())

    def proc_number(self, e):
        if "number" not in e.fields:
            return 0
        else:
            return self.proc_int_descending(e.fields["number"].expand())

    def key(self, ke):
        (k,e) = ke
        (p1, p2) = self.get_pages(k,e)

        return "{:<15}-{:0>4d}-{:<10}-{}-{:>10}-{:0>10d}-{:0>20}-{:0>20}".format(
            self.proc_confkey(k.confkey),
            self.proc_year(k.year),
            self.proc_dis(e),
            self.proc_eprint(e),
            self.proc_volume(e),
            self.proc_number(e),
            p1,
            p2
        )
       
def bibtex_entry_format_fields(db, key, entry, expand_crossrefs=False, expand_values=False):
    """ Return a dictionnay of formatted fields """

    def format_name(person):
        def join(l):
            return ' '.join([name for name in l if name])
        first = person.get_part_as_text('first')
        middle = person.get_part_as_text('middle')
        prelast = person.get_part_as_text('prelast')
        last = person.get_part_as_text('last')
        lineage = person.get_part_as_text('lineage')
        s = '' 
        if last:
            s += join([prelast, last])
        if lineage:
            s += ', %s' % lineage
        if first or middle:
            s += ', '
            s += join([first, middle])
        return s

    def format_persons(persons):
        return Value([ValuePartQuote((" and ").join([format_name(person) for person in persons]))])

    def format_author(author):
        res = author.expand().replace(" and ", " and\n" + " "*18)
        return Value([ValuePartQuote(res, normalize=False)])

    fields = entry.fields.copy()
    
    # expand persons
    for (role, persons) in entry.persons.items():
        if role not in fields:
            fields[role] = format_persons(persons)

    # format author
    if "author" in fields:
        fields["author"] = format_author(fields["author"])

    # expand crossrefs
    if expand_crossrefs:
        if "crossref" in fields:
            crossref_fields = db.entries[EntryKey.from_string(fields["crossref"].expand())].fields.copy()
            del crossref_fields["key"] # a bit of a hack TODO...
            fields = dict(list(crossref_fields.items()) + list(fields.items()))
            del fields["crossref"]

    return fields

def bibtex_write_entry(out, db, key, entry, expand_crossrefs=False, expand_values=False, remove_empty_fields=False):
    """ Write a bibtex entry in out """

    def key_sort(key):
        if key in config.first_keys:
            return "{0:03d}:{1}".format(config.first_keys.index(key),key)
        else:
            return "{0:03d}:{1}".format(len(config.first_keys),key)

    def format_type(type_):
        if type_.lower() in config.types:
            return config.types[type_.lower()]
        else:
            return type_.capitalize()

    fields = bibtex_entry_format_fields(db, key, entry, expand_crossrefs, expand_values)

    # actual writing
    out.write("@{0}{{{1},\n".format(format_type(entry.type), str(key)))

    for k in sorted(iter(fields.keys()), key=key_sort):
        # remove empty fields after expansion
        if remove_empty_fields:
            v_expanded = fields[k].to_bib(expand = True)
            if v_expanded == '""':
                continue

        v = fields[k].to_bib(expand = expand_values)

        # v_ascii only contains ascii characters
        try:
            v_ascii = v.encode("ascii").decode("ascii")
        except UnicodeEncodeError as ex:
            logging.warning("Problem of encoding in entry \"{0}\", key \"{1}\", value \"{2}\" -> replace bad caracter(s) with '?'".format(key,k,repr(v)))
            v_ascii = v.encode("ascii", "replace").decode("ascii")

        out.write("  {0:<15}{1},\n".format((k + " ="), v_ascii ))

    out.write("}")

def bibtex_write_entries(out, db, entries, *args, **kwargs):
    """ internal function used to write bibtex entries """

    for key, entry in entries:
        bibtex_write_entry(out, db, key, entry, *args, **kwargs)
        out.write("\n\n")


def bibtex_gen(out, db, entry_filter=FilterPaper(), entry_sort=SortConfYearPage(), expand_crossrefs=False, include_crossrefs=False, *args, **kwargs):
    """
    Generate bibtex file

    Options:
    @arg expand_crossrefs: expand crossrefs inside entries instead of keeping the crossref field if True,
    @arg include_crossrefs: include crossrefs in the output if True and expand_crossrefs=False,
    @arg expand_values: expand values (using macros) if True
    @arg remove_empty_fields: remove empty fields if True, empty fields are ones that are either empty or expand to an empty value
      (in case expand_values=False and multiple macros values may be used using, e.g., multiple "abbrev*.bib" files, be extra careful)
    """
    entries = dict(entry_filter.filter(db.entries))
    bibtex_write_entries(
        out,
        db,
        entry_sort.sort(iter(entries.items())),
        expand_crossrefs=expand_crossrefs,
        *args, **kwargs
    )

    if expand_crossrefs==False and include_crossrefs==True:
        # works because an entry crossrefed cannot crossref another entry
        crossrefs = dict()
        for k,e in entries.items():
            if "crossref" in e.fields:
                crossref = EntryKey.from_string(e.fields["crossref"].expand())
                if crossref not in crossrefs:
                    crossrefs[crossref] = db.entries[crossref]

        bibtex_write_entries(
            out,
            db,
            entry_sort.sort(iter(crossrefs.items())),
            expand_crossrefs=expand_crossrefs,
            *args, **kwargs
        )

def bibtex_gen_str(db, *args, **kwargs):
    out = io.StringIO()
    bibtex_gen(out, db, *args, **kwargs)
    return out.getvalue()


def sql_write_entry(out, entry, crossref=None):
    """ write entry for an entry in web2py sqlite (entry is a row corresponding to an entry)
    @entry
    @arg crossref if None, does nothing, otherwise, merge fields in entry
    """
    def key_sort(key):
        if key in config.first_keys:
            return "{0:03d}:{1}".format(config.first_keys.index(key),key)
        else:
            return "{0:03d}:{1}".format(len(config.first_keys),key)

    def format_type(type_):
        if type_.lower() in config.types:
            return config.types[type_.lower()]
        else:
            return type_.capitalize()

    key = EntryKey(entry.key_conf, entry.key_year%100, entry.key_auth, entry.key_dis)

    fields = entry.as_dict().copy()

    if crossref != None:
        del fields["crossref"]
        fields = {k: v if v != None else crossref[k] for (k,v) in fields.items()}

    if fields["start_page"]!=None:
        if fields["end_page"]==None:
            fields["pages"] = str(fields["start_page"])
        else:
            fields["pages"] = '"{}--{}"'.format(fields["start_page"], fields["end_page"])

    del fields["id"]

    del fields["key_conf"]
    del fields["key_year"]
    del fields["key_auth"]
    del fields["key_dis"]

    del fields["type"]

    del fields["start_page"]
    del fields["end_page"]

    # actual writing
    out.write("@{0}{{{1},\n".format(format_type(entry.type), str(key)))

    for k in sorted(iter(fields.keys()), key=key_sort):
        v = fields[k]
        if v == None:
            continue
        v = str(v)

        try:
            v_ascii = v.encode("ascii").decode()
        except UnicodeEncodeError as ex:
            logging.warning("Problem of encoding in entry \"{0}\", key \"{1}\", value \"{2}\" -> replace bad caracter(s) with '?'".format(key,k,repr(v)))
            v_ascii = v.encode("ascii", "replace").decode()

        out.write("  {0:<15}{1},\n".format((k + " ="), v_ascii))

    out.write("}")
