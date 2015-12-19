import sys

"""
Here's the list of all AST nodes produced by the parser, along with their attributes.

 * unit
    * decls: [unit_decls + def]
    * scope: scope (post-sema)
 * unit_decls = [interface + enum + module]
    * all unit decls have `name` and (after sema) `scope`.
 * interface
    * name: str
    * params: [(str, type)]
    * decls: [use + port]
    * scope: scope (post-sema)
 * intf-inst
    * ports: [port]
    * specs
 * use
    * type: type
 * enum
    * name: str
    * enumers: [str]
    * scope: scope (post-sema)
 * member
    * name: str
    * type: type
 * module
    * name: str
    * params: [(str, type)]
    * ports: [port]
    * scope: scope (post-sema)
    * defs: [def] (post-sema)
 * module-inst (post-sema)
    * ports: [port]
    * decls: [signal + inst-inst + always + on]
    * specs
    * scope
 * def
    * name: str
    * decls: [signal + always + on + inst]
    * scope: scope (post-sema)
    * mod: module (post-sema)
 * signal
    * name: str
    * type: type
 * always
    * body: [stmt]
 * on
    * specs: [edgespec]
    * body: [stmt]
 * edgespec
    * name: str # XXX
    * rising: bool
 * inst
    * name: str
    * module: str
    * port_maps: [port_map]
 * inst-inst (post-sema)
    * name: str
    * module: module-inst
    * port-maps: [port-map]
    * type: type
    * specs
 * port_map
    * target: expr
    * source: expr
 * port
    * dir: str
    * name: str
    * type: type

 * type = [bit-type + struct-type + array-type + set-type]
 * bit-type
 * struct-type
    * name: str
    * args: [arg]
    * decl: interface + enum (post-sema)
 * arg
    * kw_name: None + str
    * value: expr
 * array-type
    * subtype: type
    * left_bound: expr
    * right_bound: expr
 * set-type
    * enum: str
    * decl: enum (post-sema)
 
 * stmt = assign-stmt + switch-stmt + if-stmt
 * assign-stmt
    * lhs: expr
    * rhs: expr
    * delayed: bool
 * switch-stmt
    * value: expr
    * cases: [case-stmt]
 * case-stmt
    * value: expr
    * body: [stmt]
 * if-stmt
    * cond: expr
    * true_body: [stmt]
    * false_body: None + [stmt]

 * expr = binary-expr + cast-expr + member-expr + slice-expr + subscript-expr + call-expr + unary-expr + atom + num + sized-num + ref + set-expr
 * binary-expr
    * lhs: expr
    * rhs: expr
    * op: str
 * unary-expr
    * arg: expr
    * op: str
 * cast-expr
    * type: type
    * expr: expr
 * member-expr
    * expr: expr
    * member: str
    * decl (post-sema)
    * type (post-sema)
 * slice-expr
    * expr: expr
    * lower_bound: expr
    * upper_bound: expr
 * subscript-expr
    * expr: expr
    * index: expr
 * call-expr
    * fn: expr
    * args: [expr]
 * atom
    * name: str
 * num
    * value: int
 * sized-num
    * size: int
    * v: str
 * ref
    * name: str
 * enum-expr
    * value_index: int
    * type: enum-type
 * set-expr
    * items: [str]

The value returned by the parser is a list of top declarations: 
"""

class Node:
    def __init__(self, kind, **kw):
        self.__dict__.update(kw)
        self.kind = kind

    def attrs(self):
        return ((k, v) for k, v in self.__dict__.items() if k != 'kind' and not k.startswith('_'))

    def __repr__(self):
        r = [repr(self.kind)]
        r.extend(('{}={!r}'.format(k, v) for k, v in self.attrs()))
        return 'Node({})'.format(', '.join(r))

def _print_value(v, nl=True, indent='', file=sys.stdout):
    if isinstance(v, list):
        if not v:
            file.write('[]')
        else:
            if not nl:
                file.write('\n')
            first = True
            for vv in v:
                if not first:
                    file.write('\n')
                first = False
                file.write('{} - '.format(indent))
                _print_value(vv, nl=False, indent=indent + '    ', file=file)
    elif isinstance(v, Node):
        file.write('@{}'.format(v.kind))
        if not nl:
            indent = indent + '    '
        for k, vv in v.attrs():
            file.write('\n')
            file.write('{}{}: '.format(indent, k))
            _print_value(vv,  nl=False, indent=indent+'    ', file=file)
    else:
        file.write(repr(v))

def print_value(v, file=sys.stdout):
    _print_value(v, file=file)
    file.write('\n')
