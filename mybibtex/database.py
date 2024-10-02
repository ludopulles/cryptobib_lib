# Copyright (c) 2006, 2007, 2008, 2009, 2010, 2011, 2012  Andrey Golovizin
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import re

from collections.abc import Mapping
from functools import total_ordering

from pybtex.exceptions import PybtexError
from pybtex.utils import (
    OrderedCaseInsensitiveDict, CaseInsensitiveDefaultDict, CaseInsensitiveSet
)
from pybtex.bibtex.utils import split_tex_string
from pybtex.errors import report_error
from pybtex import textutils

from .month_names import month_names

_whitespace_re = re.compile(r'\s+')

def normalize_whitespace(s):
    return _whitespace_re.sub(' ', s)


class BibliographyDataError(PybtexError):
    pass


class BibliographyData(object):
    def __init__(self, entries=None, preamble=None):
        self.entries = dict() #OrderedCaseInsensitiveDict()
        self._preamble = []
        if entries:
            if isinstance(entries, Mapping):
                entries = iter(entries.items())
            for (key, entry) in entries:
                self.add_entry(key, entry)
        if preamble:
            self._preamble.extend(preamble)

    def __eq__(self, other):
        if not isinstance(other, BibliographyData):
            return super(BibliographyData, self) == other
        return (
            self.entries == other.entries
            and self._preamble == other._preamble
        )

    def __repr__(self):
        return 'BibliographyData(entries={entries}, preamble={preamble})'.format(
            entries=repr(self.entries),
            preamble=repr(self._preamble),
        )

    def add_to_preamble(self, *values):
        self._preamble.extend(values)

    def preamble(self):
        return ''.join(self._preamble)

    def add_entry(self, key, entry):
        if not isinstance(key, EntryKey):
            key = EntryKey.from_string(key)
        if key in self.entries:
            report_error(BibliographyDataError('repeated bibliography entry: %s' % key))
            return
        entry.collection = self
        entry.key = key
        self.entries[key] = entry

    def add_entries(self, entries):
        for key, entry in entries:
            self.add_entry(key, entry)

class FieldDict(dict):
    def __init__(self, parent, *args, **kwargw):
        self.parent = parent
        dict.__init__(self, *args, **kwargw)
    def __missing__(self, key):
        if key in self.parent.persons:
            persons = self.parent.persons[key]
            return ' and '.join(str(person) for person in persons)
        elif 'crossref' in self:
            return self.parent.get_crossref().fields[key]
        else:
            raise KeyError(key)


class Entry(object):
    """Bibliography entry. Important members are:
    - persons (a dict of Person objects)
    - fields (all dict of string)
    """

    def __init__(self, type_, fields=None, persons=None, collection=None):
        if fields is None:
            fields = {}
        if persons is None:
            persons = {}
        self.type = type_
        self.fields = FieldDict(self, fields)
        self.persons = dict(persons)
        self.collection = collection

        # for BibTeX interpreter
        self.vars = {}

    def __eq__(self, other):
        if not isinstance(other, Entry):
            return super(Entry, self) == other
        return (
                self.type == other.type
                and self.fields == other.fields
                and self.persons == other.persons
        )

    def __repr__(self):
        return 'Entry({type_}, fields={fields}, persons={persons})'.format(
            type_=repr(self.type),
            fields=repr(self.fields),
            persons=repr(self.persons),
        )

    def get_crossref(self):
        return self.collection.entries[EntryKey.from_string(self.fields['crossref'].expand())]

    def add_person(self, person, role):
        self.persons.setdefault(role, []).append(person)


class Person(object):
    """Represents a person (usually human).

    >>> p = Person('Avinash K. Dixit')
    >>> print p.first()
    ['Avinash']
    >>> print p.middle()
    ['K.']
    >>> print p.prelast()
    []
    >>> print p.last()
    ['Dixit']
    >>> print p.lineage()
    []
    >>> print unicode(p)
    Dixit, Avinash K.
    >>> p == Person(unicode(p))
    True
    >>> p = Person('Dixit, Jr, Avinash K. ')
    >>> print p.first()
    ['Avinash']
    >>> print p.middle()
    ['K.']
    >>> print p.prelast()
    []
    >>> print p.last()
    ['Dixit']
    >>> print p.lineage()
    ['Jr']
    >>> print unicode(p)
    Dixit, Jr, Avinash K.
    >>> p == Person(unicode(p))
    True

    >>> p = Person('abc')
    >>> print p.first(), p.middle(), p.prelast(), p.last(), p.lineage()
    [] [] [] ['abc'] []
    >>> p = Person('Viktorov, Michail~Markovitch')
    >>> print p.first(), p.middle(), p.prelast(), p.last(), p.lineage()
    ['Michail'] ['Markovitch'] [] ['Viktorov'] []
    """
    valid_roles = ['author', 'editor'] 
    style1_re = re.compile('^(.+),\s*(.+)$')
    style2_re = re.compile('^(.+),\s*(.+),\s*(.+)$')

    def __init__(self, string="", first="", middle="", prelast="", last="", lineage=""):
        self._first = []
        self._middle = []
        self._prelast = []
        self._last = []
        self._lineage = []
        string = string.strip()
        if string:
            self.parse_string(string)
        self._first.extend(split_tex_string(first))
        self._middle.extend(split_tex_string(middle))
        self._prelast.extend(split_tex_string(prelast))
        self._last.extend(split_tex_string(last))
        self._lineage.extend(split_tex_string(lineage))

    def parse_string(self, name):
        """Extract various parts of the name from a string.
        Supported formats are:
         - von Last, First
         - von Last, Jr, First
         - First von Last
        (see BibTeX manual for explanation)
        """
        def process_first_middle(parts):
            try:
                self._first.append(parts[0])
                self._middle.extend(parts[1:])
            except IndexError:
                pass

        def process_von_last(parts):
            von, last = rsplit_at(parts, lambda part: part.islower())
            if von and not last:
                last.append(von.pop())
            self._prelast.extend(von)
            self._last.extend(last)

        def find_pos(lst, pred):
            for i, item in enumerate(lst):
                if pred(item):
                    return i
            return i + 1

        def split_at(lst, pred):
            """Split the given list into two parts.

            The second part starts with the first item for which the given
            predicate is True.
            """
            pos = find_pos(lst, pred)
            return lst[:pos], lst[pos:]

        def rsplit_at(lst, pred):
            rpos = find_pos(reversed(lst), pred)
            pos = len(lst) - rpos
            return lst[:pos], lst[pos:]

        parts = split_tex_string(name, ',')
        if len(parts) == 3: # von Last, Jr, First
            process_von_last(split_tex_string(parts[0]))
            self._lineage.extend(split_tex_string(parts[1]))
            process_first_middle(split_tex_string(parts[2]))
        elif len(parts) == 2: # von Last, First
            process_von_last(split_tex_string(parts[0]))
            process_first_middle(split_tex_string(parts[1]))
        elif len(parts) == 1: # First von Last
            parts = split_tex_string(name)
            first_middle, von_last = split_at(parts, lambda part: part.islower())
            if not von_last and first_middle:
                last = first_middle.pop()
                von_last.append(last)
            process_first_middle(first_middle)
            process_von_last(von_last)
        else:
            raise PybtexError('Invalid name format: %s' % name)

    def __eq__(self, other):
        if not isinstance(other, Person):
            return super(Person, self) == other
        return (
                self._first == other._first
                and self._middle == other._middle
                and self._prelast == other._prelast
                and self._last == other._last
                and self._lineage == other._lineage
        )

    def __unicode__(self):
        # von Last, Jr, First
        von_last = ' '.join(self._prelast + self._last)
        jr = ' '.join(self._lineage)
        first = ' '.join(self._first + self._middle)
        return ', '.join(part for part in (von_last, jr, first) if part)

    def __repr__(self):
        return 'Person({0})'.format(repr(str(self)))

    def get_part_as_text(self, type):
        names = getattr(self, '_' + type)
        return ' '.join(names)

    def get_part(self, type, abbr=False):
        names = getattr(self, '_' + type)
        if abbr:
            from pybtex.textutils import abbreviate
            names = [abbreviate(name) for name in names]
        return names

    #FIXME needs some thinking and cleanup
    def bibtex_first(self):
        """Return first and middle names together.
        (BibTeX treats all middle names as first)
        """
        return self._first + self._middle

    def first(self, abbr=False):
        return self.get_part('first', abbr)
    def middle(self, abbr=False):
        return self.get_part('middle', abbr)
    def prelast(self, abbr=False):
        return self.get_part('prelast', abbr)
    def last(self, abbr=False):
        return self.get_part('last', abbr)
    def lineage(self, abbr=False):
        return self.get_part('lineage', abbr)

        self.entries[key] = entry
        try:
            crossref = entry.fields['crossref'].expand()
        except KeyError:
            pass
        else:
            self.crossref_count[crossref] += 1
            if self.crossref_count[crossref] >= self.min_crossrefs:
                if self.wanted_entries is not None:
                    self.wanted_entries.add(crossref)

    def add_entries(self, entries):
        for key, entry in entries:
            self.add_entry(key, entry)

class FieldDict(dict):
    def __init__(self, parent, *args, **kwargw):
        self.parent = parent
        dict.__init__(self, *args, **kwargw)
    def __missing__(self, key):
        if key in self.parent.persons:
            persons = self.parent.persons[key]
            return ' and '.join(str(person) for person in persons)
        elif 'crossref' in self:
            return self.parent.get_crossref().fields[key]
        else:
            raise KeyError(key)
        self.entries[key] = entry

    def add_entries(self, entries):
        for key, entry in entries:
            self.add_entry(key, entry)

class EntryKeyParsingError(Exception):
    def __init__(self, key):
        self.key = key
        message = 'Error while parsing key "{0}"'.format(key)
        super(EntryKeyParsingError, self).__init__(message)

class EntryKey(object):
    """ Model an entry key in our bibliographies """
    def __init__(self, confkey, year, auth=None, dis=""):
        self.confkey = confkey
        """ conference abbreviation for key """
        self.auth = auth
        """ authors formatted as required in key (last name or first letters or ...) or None if this is a conference """
        self.year = int(year) % 100
        """ year of the conference (2 digits) """
        self.dis = dis
        """ disambiguation string ("", "a", "b", "-1", "-2", ...) if same conf, same authors and same year for a paper or if multiple volumes in one conf"""

    _str_regexp = re.compile("^([a-zA-Z]+)(?::([a-zA-Z-_']+))?(\d+)(.*)$")

    @classmethod
    def from_string(cls, s):
        r = cls._str_regexp.match(s)
        if r is None:
            raise EntryKeyParsingError(s)
        (confkey, auth, year, dis) = r.groups()
        return cls(confkey, year, auth, dis)

    def __str__(self):
        if self.auth == None:
            return "{0}{1:02d}{2}".format(self.confkey, self.year, self.dis)
        else:
            return "{0}:{1}{2:02d}{3}".format(self.confkey, self.auth, self.year, self.dis)

    def __repr__(self):
        return "EntryKey({0})".format(str(self))

    def __hash__(self):
        return str(self).__hash__()

    def __eq__(self, other):
        return (self.confkey == other.confkey and
                self.auth == other.auth and
                self.year == other.year and
                self.dis == other.dis)

class Value(list):
    """ Model a value in bibtex, i.e., a concatenation of value parts """
    def expand(self):
        return ''.join([value_part.expand() for value_part in self])

    def __repr__(self):
        return "Value({0})".format(repr(list(self)))

    def to_bib(self, expand=False):
        """ transform the value into a bib value; if expand=True, expand all macros EXCEPT month names """
        return " # ".join([value_part.to_bib(expand=expand) for value_part in self])

class ValuePart(object):
    """ Model a value part """
    def __init__(self, val, normalize = True):
        self.val = val if normalize == False else normalize_whitespace(val)

    def __str__(self):
        """ Return the original bibtex representation """
        return self.val

    def __repr__(self):
        return repr(self.val)

    def expand(self):
        """ Return the expanded resulting string (after macro expansion, unquoting, ...) """
        return self.val

    def to_bib(self, expand=False):
        return str(self)

class ValuePartNumber(ValuePart):
    pass

class ValuePartQuote(ValuePart):
    def __str__(self):
        return '"{0}"'.format(self.val)

class ValuePartBrace(ValuePart):
    def __str__(self):
        return '{{{0}}}'.format(self.val)

class ValuePartMacro(ValuePart):
    def __init__(self, macro_name, macro_val):
        """
        @arg macro_val: value of the macro (type Value)
        """
        self.macro_name = macro_name
        self.macro_val = macro_val

    def __str__(self):
        return self.macro_name

    def __repr__(self):
        return 'Macro({0})'.format(self.macro_name)

    def expand(self):
        return self.macro_val.expand()

    def to_bib(self, expand=False):
        if expand==False or self.macro_name in month_names:
            return self.macro_name
        else:
            return self.macro_val.to_bib(expand=expand)


