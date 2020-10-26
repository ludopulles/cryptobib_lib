"""
Library for parsing bibyml format.

bibyml is a variant of a subset YAML for bibtex values.
It can only represent dictionnaries and values are dictionnaries or bibtex values (or both)
In addition, tabulations are not supported.

Example:

eurocrypt: test
    2013: aa
    2015: bb

corresponds to the dictionnary:
{
  "eurocrypt": {
    "": test,
    "2013": aa,
    "2015": bb
  }
}


"""

import re
import io
from collections import OrderedDict

_parser_re = re.compile(r'^(\s*)([^:]+):(.*)$')
_spaces_re = re.compile(r'^ *$')

class ParserError(Exception):
    def __init__(self, line, msg=""):
        message = """BibYml parsing error:\n    line: "{}"\n    message: {}""".format(line[:-1], msg)
        super(ParserError,self).__init__(message)

def dict_get_path(d, p, make=False):
    """ get the element of path p in dictionnary d,
        make the path if it does not exists and make=True """
    cur = d
    for i in p:
        if make and i not in cur:
            cur[i] = OrderedDict()
        cur = cur[i]

    return cur

def parse(f):
    """ Parse a bibyml file f intro a dictionnary """
    res = OrderedDict()
    path = []            # path of the current element
    path_indent = [0]    # indentation of all elements along the path + indentation of the children of the path
                         # can end by -1 if the indentation of the children is not yet known (i.e., before the first children)

    for line in f:
        if line.strip() == "":
            continue
        r = _parser_re.match(line)
        if r == None:
            raise ParserError(line)

        (spaces_indent, key, value) = r.groups()
        if _spaces_re.match(spaces_indent) == None:
            raise ParserError(line, "only spaces are accepted")
        value = value.strip()
        key = key.strip()
        indent = len(spaces_indent)

        if path_indent[-1] == -1:
            if indent > path_indent[-2]:
                # new indentation level
                path_indent[-1] = indent
            else:
                # no new indentation level
                path_indent.pop()
                path.pop()

        # find indentation level
        while len(path_indent) > 1 and path_indent[-1] > indent:
            path_indent.pop()
            path.pop()
        
        if indent != path_indent[-1]:
            raise ParserError(line, "indentation problem")

        d = dict_get_path(res, path)
    
        d[key] = OrderedDict([("", value)]) if value != "" else OrderedDict()
        path_indent.append(-1) # we do not know the next indentation level
        path.append(key)

    return res

def write(out, d, indent_key=4, indent_value=24, cur_indent=0):
    for (k,v) in d.items():
        if k=="":
            continue
        if "" in v and v[""] != "":
            out.write("{}{}: {}{}\n".format(
                " "*indent_key*cur_indent, 
                k, 
                " "*(max(0, indent_value-(len(k)+2+indent_key*cur_indent))),
                v[""]
            ))
        else:
            out.write("{}{}: \n".format(
                " "*indent_key*cur_indent, 
                k
            ))
        write(out, v, cur_indent=cur_indent+1)

def write_str(d, *args, **kwargs):
    out = io.StringIO()
    write(out, d, *args, **kwargs)
    return out.getvalue()
            
