from __future__ import print_function

from database import *
import tools

import StringIO
from abc import ABCMeta, abstractmethod
import logging

# WARNING: do not forge to set this variable to the correct config module when loading this module
# FIXME: need to remove this dirty hack!
config = None 

class EntryFilter(object):
    """ Composable entry filters: it is possible to compose a filter FilterA with a filter FilterB by instantiating FilterA(FilterB()) """
    __metaclass__ = ABCMeta

    def __init__(self, filter_and=None):
        self.filter_and = filter_and

    @abstractmethod
    def is_selected(self, key, entry):
        """ Return true if the key, entry has to be selected and false otherwise"""
        pass

    def filter(self, entries):
        entries = entries if self.filter_and == None else self.filter_and.filter(entries)
        for (k,e) in entries.iteritems():
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

class EntrySort(object):
    __metaclass__ = ABCMeta

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
            except ValueError, e:
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

    def proc_volume(self, e):
        if "volume" not in e.fields:
            return 0
        else:
            vol = e.fields["volume"].expand()
            if vol.isdigit():
                return 999999-int(vol)

    def proc_number(self, e):
        if "number" not in e.fields:
            return 0
        else:
            return 999999-int(e.fields["number"].expand())

    def key(self, ke):
        (k,e) = ke
        (p1, p2) = self.get_pages(k,e)
        return u"{:<15}-{:0>4d}-{:<10}-{:>10}-{:0>10d}-{:>10}-{:>10}".format(
            self.proc_confkey(k.confkey), 
            self.proc_year(k.year), 
            self.proc_dis(e),
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
        return Value([ValuePartQuote((u" and ").join([format_name(person) for person in persons]))])

    def format_author(author):
        res = author.expand().replace(" and ", u" and\n" + u" "*18)
        return Value([ValuePartQuote(res, normalize=False)])

    fields = entry.fields.copy()
    
    # expand persons
    for (role, persons) in entry.persons.iteritems():
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
            fields = dict(crossref_fields.items() + fields.items())
            del fields["crossref"]

    return fields

def bibtex_write_entry(out, db, key, entry, expand_crossrefs=False, expand_values=False):
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
    out.write("@{0}{{{1},\n".format(format_type(entry.type), unicode(key)))

    for k in sorted(fields.iterkeys(), key=key_sort):
        v = fields[k].to_bib(expand = expand_values)

        try:
            venc = v.encode("ascii")
        except UnicodeEncodeError, ex:
            logging.warning("Problem of encoding in entry \"{0}\", key \"{1}\", value \"{2}\" -> replace bad caracter(s) with '?'".format(key,k,repr(v)))
            venc = v.encode("ascii", "replace")

        out.write("  {0:<15}{1},\n".format((k + " ="), venc))

    out.write("}")

def bibtex_write_entries(out, db, entries, *args, **kwargs):
    """ internal function used to write bibtex entries """

    for key, entry in entries:
        bibtex_write_entry(out, db, key, entry, *args, **kwargs)
        out.write("\n\n")
        

def bibtex_gen(out, db, entry_filter=FilterPaper(), entry_sort=SortConfYearPage(), expand_crossrefs=False, include_crossrefs=False, *args, **kwargs):
    """ Options:
    @arg expand_crossrefs: expand crossrefs inside entries instead of keeping the crossref field if True,
    @arg include_crossrefs: include crossrefs in the output if True and expand_crossrefs=False,
    @arg expand_values: expand values (using macros) if True
    """
    entries = dict(entry_filter.filter(db.entries))
    bibtex_write_entries(
        out, 
        db, 
        entry_sort.sort(entries.iteritems()), 
        expand_crossrefs=expand_crossrefs, 
        *args, **kwargs
    )
    
    if expand_crossrefs==False and include_crossrefs==True:
        # works because an entry crossrefed cannot crossref another entry
        crossrefs = dict()
        for k,e in entries.iteritems():
            if "crossref" in e.fields:
                crossref = EntryKey.from_string(e.fields["crossref"].expand())
                if crossref not in crossrefs:
                    crossrefs[crossref] = db.entries[crossref]

        bibtex_write_entries(
            out, 
            db, 
            entry_sort.sort(crossrefs.iteritems()), 
            expand_crossrefs=expand_crossrefs, 
            *args, **kwargs
        )

def bibtex_gen_str(db, *args, **kwargs):
    out = StringIO.StringIO()
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
        fields = {k: v if v != None else crossref[k] for (k,v) in fields.iteritems()}

    if fields["start_page"]!=None:
        if fields["end_page"]==None:
            fields["pages"] = str(fields["start_page"])
        else:
            fields["pages"] = '"{:d}--{:d}"'.format(fields["start_page"], fields["end_page"])

    del fields["id"]

    del fields["key_conf"]
    del fields["key_year"]
    del fields["key_auth"]
    del fields["key_dis"]

    del fields["type"]

    del fields["start_page"]
    del fields["end_page"]

    # actual writing
    out.write("@{0}{{{1},\n".format(format_type(entry.type), unicode(key)))

    for k in sorted(fields.iterkeys(), key=key_sort):
        v = fields[k]
        if v == None:
            continue
        v = str(v)

        try:
            venc = v.encode("ascii")
        except UnicodeEncodeError, ex:
            logging.warning("Problem of encoding in entry \"{0}\", key \"{1}\", value \"{2}\" -> replace bad caracter(s) with '?'".format(key,k,repr(v)))
            venc = v.encode("ascii", "replace")

        out.write("  {0:<15}{1},\n".format((k + " ="), venc))

    out.write("}")
