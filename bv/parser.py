import speg, os.path
from .ast import Node, print_value

def nl(p):
    return p(r'(?:[ \t]*(?:#[^\n]*)?\n)+')

def ws(p):
    return p(r'[ \t]*')

def ident(p):
    return p('[a-zA-Z_][a-zA-Z_0-9]*')

def indent(p):
    return p(r'[ \t]+')

def kw(p, name):
    return p(name + r'(?![a-zA-Z_0-9])')

_digits = {
    '0': '0000',
    '1': '0001',
    '2': '0010',
    '3': '0011',
    '4': '0100',
    '5': '0101',
    '6': '0110',
    '7': '0111',
    '8': '1000',
    '9': '1001',
    'a': '1010',
    'b': '1011',
    'c': '1100',
    'd': '1101',
    'e': '1110',
    'f': '1111',
    'x': 'xxxx',
    'z': 'zzzz',
    '?': '????',
    }

def num_expr(p):
    v = int(p(r'-?[0-9]+'), 10)
    with p:
        size, v = v, p('\'(?:b[01xz\?_]+|o[0-7xz\?_]+|d[0-9_]+|h[0-9a-fxz\?_]+)')
        base = v[1]
        v = v[2:].replace('_', '')
        if base == 'o':
            v = ''.join((digits[c][1:] for c in v))
        elif base == 'h':
            v = ''.join((digits[c] for c in v))
        elif base == 'd':
            v = bin(int(v, 10))
        return Node('sized-num', size=size, v=v)
    return Node('num', value=v)

def atom_expr(p):
    with p:
        op = p('-')
        arg = p(cast_expr)
        return Node('unary-expr', op=op, arg=arg)

    with p:
        p('\'')
        name = p(ident)
        return Node('atom', name=name)

    with p:
        return p(num_expr)

    with p:
        return Node('ref', name=p(ident))

    with p:
        p(r'\{')
        p(ws)
        items = []
        with p:
            while True:
                items.append(p(ident))
                p(ws)
                p.commit()
                p(',')
                p(ws)
        p(r'\}')
        return Node('set-expr', items=items)

    p(r'\(')
    p(ws)
    r = p(expr)
    p(ws)
    p(r'\)')
    return r

def fn_call(p):
    fn = p(atom_expr)
    with p:
        p(ws)
        p(r'\(')
        p(ws)

        args = []
        with p:
            args.append(p(expr))
            while True:
                p(ws)
                p.commit()
                p(',')
                p(ws)
                args.append(p(expr))

        p(r'\)')
        return Node('call-expr', fn=fn, args=args)

    return fn

def slice_expr(p):
    callee = p(fn_call)
    with p:
        p(ws)
        p(r'\[')
        p(ws)
        lower_bound = p(expr)
        p(ws)
        upper_bound = None
        with p:
            p(':')
            p(ws)
            upper_bound = p(expr)
            p(ws)
        p(r'\]')
        return Node('slice-expr', expr=callee, lower_bound=lower_bound, upper_bound=upper_bound)
    return callee

def member_expr(p):
    container = p(slice_expr)
    with p:
        p(ws)
        p(r'\.')
        p(ws)
        name = p(ident)
        return Node('member-expr', expr=container, member=name)
    return container

def cast_expr(p):
    with p:
        type = p(signal_type)
        p('\'')
        e = p(cast_expr)
        return Node('cast-expr', type=type, expr=e)
    return p(member_expr)

def expr(p):
    lhs = p(cast_expr)
    with p:
        p(ws)
        op = p(r'[+\-*/]')
        p(ws)
        rhs = p(cast_expr)
        return Node('binary-expr', lhs=lhs, rhs=rhs, op=op)
    return lhs

def array_bounds(p):
    bounds = []
    with p:
        while True:
            p(ws)
            p(r'\[')
            p(ws)
            left_bound = p(expr)
            p(ws)
            p(':')
            p(ws)
            right_bound = p(expr)
            p(ws)
            p(r'\]')
            bounds.append((left_bound, right_bound))
            p.commit()
    return bounds

def generic_arg(p):
    with p:
        param_name = p(ident)
        p(ws)
        p('=')
        p(ws)
        value = p(expr)
        return Node('arg', kw_name=param_name, value=value)
    return Node('arg', kw_name=None, value=p(expr))

def generic_args(p):
    p(r'\(')
    p(ws)
    r = []
    with p:
        r.append(p(generic_arg))
        while True:
            p(ws)
            p.commit()
            p(',')
            p(ws)
            r.append(p(generic_arg))
    p(r'\)')
    return r

def simple_type(p):
    name = p(ident)
    if len(name) == 1 and name[0] == 'bit':
        return Node('bit-type')
    gen_args = []
    with p:
        gen_args = p(generic_args)
    return Node('struct-type', name=name, args=gen_args)

def signal_type(p):
    subtype = p(simple_type)
    bounds = p(array_bounds)
    if bounds:
        return Node('array-type', subtype=subtype, bounds=bounds)
    return subtype

def _member_decl(p):
    name = p(ident)
    with p:
        p(ws)
        p(':')
        p(ws)
        type = p(signal_type)
        return name, type
    bounds = p(array_bounds)
    simple_type = Node('bit-type')
    if bounds:
        return name, Node('array-type', subtype=simple_type, bounds=bounds)
    return name, simple_type

def port_decl(p):
    dir = p(ident)
    p(ws)
    name, type = p(_member_decl)
    return Node('port', dir=dir, name=name, type=type)

def generic_param(p):
    name = p(ident)
    with p:
        p(ws)
        p(':')
        p(ws)
        type = p(signal_type)
        return name, type
    return name, Node('auto-type')

def generic_decl(p):
    r = []
    with p:
        p('\(')
        p(ws)
        with p:
            r.append(p(generic_param))
            while True:
                p(ws)
                p.commit()
                p(',')
                p(ws)
                r.append(p(generic_param))
        p('\)')
    return r

def _indent(p):
    return p(p.get('indent', ''))

def _indented(p, stmt):
    p(nl)
    cur = p(_indent)
    new = p(indent)
    with p:
        cur = cur + new
        p.set('indent', cur)

        r = []
        with p:
            r.append(p(stmt))
            while True:
                p.commit()
                p(nl)
                p(cur)
                r.append(p(stmt))
        return r
    return []

def line_enumers(p):
    r = [p(ident)]
    with p:
        while True:
            p(ws)
            p(',')
            p(ws)
            r.append(p(ident))
            p.commit()
    with p:
        p(ws)
        p(',')
    return r

def struct_member(p):
    name, type = p(_member_decl)
    return Node('member', name=name, type=type)

def assign_stmt(p):
    lhs = p(expr)
    p(ws)
    op = p(r'(?:\<=|=)')
    p(ws)
    rhs = p(expr)
    return Node('assign-stmt', lhs=lhs, rhs=rhs, delayed=op == '<=')

def switch_case(p):
    value = p(expr)
    p(ws)
    p(':')
    body = p(_indented, seq_stmt)
    return Node('case-stmt', value=value, body=body)

def seq_stmt(p):
    with p:
        return p(assign_stmt)

    with p:
        p(kw, 'switch')
        p(ws)
        value = p(expr)
        p(ws)
        p(':')
        cases = p(_indented, switch_case)
        return Node('switch-stmt', value=value, cases=cases)

    p(kw, 'if')
    p(ws)
    cond = p(expr)
    p(ws)
    p(':')
    true_body = p(_indented, seq_stmt)
    false_body = None
    with p:
        p(nl)
        p(_indent)
        p(kw, 'else')
        p(ws)
        p(':')
        false_body = p(_indented, seq_stmt)
    return Node('if-stmt', cond=cond, true_body=true_body, false_body=false_body)

def port_map(p):
    name = p(ident)
    p(ws)
    dir = p(r'(?:\<=|=\>)')
    p(ws)
    conn = p(expr)
    return Node('port_map', name=name, into=dir == '<=', conn=conn)

def edge_spec(p):
    with p:
        p(kw, 'posedge')
        rising = True
    if not p:
        p(kw, 'negedge')
        rising = False
    p(ws)
    edge = p(ident)
    return Node('edgespec', rising=rising, name=edge)

def def_decl(p):
    with p:
        p(kw, 'sig')
        p(ws)
        name, type = p(_member_decl)
        return Node('signal', name=name, type=type)
    with p:
        p(kw, 'always')
        p(ws)
        p(':')
        body = p(_indented, seq_stmt)
        return Node('always', body=body)
    with p:
        p(kw, 'on')
        p(ws)
        specs = [p(edge_spec)]
        with p:
            while True:
                p(ws)
                p(kw, 'or')
                p(ws)
                specs.append(p(edge_spec))
                p.commit()
        p(':')
        body = p(_indented, seq_stmt)
        return Node('on', specs=specs, body=body)

    p(kw, 'inst')
    p(ws)
    name = p(ident)
    p(ws)
    p(':')
    p(ws)
    mod = p(ident)
    pms = p(_indented, port_map)
    return Node('inst', name=name, module=mod, port_maps=pms)

def intf_decl(p):
    with p:
        p(kw, 'use')
        p(ws)
        type = p(simple_type)
        return Node('use', type=type)

    return p(port_decl)

def top_decl(p):
    p(_indent)

    with p:
        p(kw, 'interface')
        p(ws)
        name = p(ident)
        p(ws)
        gen_args = p(generic_decl)
        p(':')
        decls = p(_indented, intf_decl)
        return Node('interface', name=name, params=gen_args, decls=decls)

    with p:
        p(kw, 'enum')
        p(ws)
        name = p(ident)
        p(ws)
        p(':')
        enumers = []
        for e in p(_indented, line_enumers):
            enumers.extend(e)
        return Node('enum', name=name, enumers=enumers)

    with p:
        p(kw, 'struct')
        p(ws)
        name = p(ident)
        p(':')
        members = p(_indented, struct_member)
        return Node('struct', name=name, members=members)

    with p:
        p(kw, 'module')
        p(ws)
        name = p(ident)
        p(':')
        ports = p(_indented, port_decl)
        return Node('module', name=name, ports=ports)

    p(kw, 'def')
    p(ws)
    name = p(ident)
    p(':')
    decls = p(_indented, def_decl)
    return Node('def', name=name, decls=decls)

def unit(p):
    p.opt(nl)
    p.set('indent', '')
    decls = []
    with p:
        while True:
            decls.append(p(top_decl))
            p.commit()
            p(nl)
    p.opt(nl)
    p(p.eof)
    return Node('unit', decls=decls)

def parse(fin, name=None):
    if name is None:
        name = os.path.split(fin.name)[1]
        name = os.path.splitext(name)[0]
    r = speg.peg(fin.read().replace('\r', ''), unit)
    r.name = name
    return r
