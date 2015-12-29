import math
from .ast import Node
from .eval import eval_int_expr

def expand_port(name, dir, type, out_dir='o'):
    # -> (output: bool, name: str, bounds: str)
    bounds = []
    while type.kind == 'resolved-array-type':
        bounds.append('[{}:{}]'.format(type.left_bound, type.right_bound))
        type = type.subtype
    bounds.reverse()
    bounds = ''.join(bounds)

    if type.kind == 'bit-type':
        return [(dir == out_dir, name, bounds)]
    elif type.kind == 'intf-inst-type':
        r = []
        for e_out, e_name, e_bounds in expand_ports(type.decl.ports, dir):
            r.append((e_out, '{}__{}'.format(name, e_name), bounds + e_bounds))
        return r
    elif type.kind == 'enum-type':
        return [(dir == out_dir, name, '[{}:0]'.format(int(math.ceil(math.log(len(type.decl.enumers), 2)))-1))]
    elif type.kind == 'set-type':
        return [(dir == out_dir, name, '[{}:0]'.format(len(type.decl.enumers)-1))]
    else:
        raise RuntimeError('unknown type')

def expand_ports(ports, out_dir='o'):
    # -> [(output: bool, name: str, bounds: str)]
    r = []
    for port in ports:
        r.extend(expand_port(port.name, port.dir, port.type, out_dir))
    return r

def _resolve_expr(expr):
    if expr.kind == 'ref':
        assert expr.decl.kind in ('port', 'signal', 'inst-inst')
        return (expr.decl.name, '')
    if expr.kind == 'slice-expr':
        if expr.type.kind != 'resolved-array-type':
            raise RuntimeError('slice operator requires an array')
        name, suffix = _resolve_expr(expr.expr)
        return (name, suffix + '[{}:{}]'.format(expr.lower_bound, expr.upper_bound))
    if expr.kind == 'member-expr':
        name, suffix = _resolve_expr(expr.expr)
        return ('{}__{}'.format(name, expr.member), suffix)
    if expr.kind == 'unary-expr':
        arg = resolve_expr(expr.arg)
        if expr.op == 'not':
            return '!{}'.format(arg), ''
        else:
            return '{}{}'.format(expr.op, arg), ''
    if expr.kind == 'num':
        return (str(expr.value), '')
    if expr.kind == 'sized-num':
        return ('{}\'b{}'.format(expr.size, expr.v), '')
    if expr.kind == 'enum-expr':
        return ('{}\'d{}'.format(int(math.ceil(math.log(len(expr.type.decl.enumers), 2))), expr.value_index), '')
    if expr.kind == 'binary-expr':
        return '{} {} {}'.format(resolve_expr(expr.lhs), expr.op, resolve_expr(expr.rhs)), ''
    raise RuntimeError('unknown expr')

def resolve_expr(expr):
    name, suffix = _resolve_expr(expr)
    return name + suffix

def format_assign_stmt(lhs, rhs, fmt):
    if rhs.type.kind == 'x-type':
        assert rhs.kind == 'x-expr'
        if lhs.type.kind == 'intf-inst-type':
            lhs_name, lhs_suf = _resolve_expr(lhs)
            r = []
            for output, name, bounds in expand_ports(lhs.type.decl.ports):
                r.append(fmt.format('{}__{}{}{}'.format(lhs_name, name, lhs_suf, bounds), '1\'sbx'))
            return r
        elif lhs.type.kind == 'resolved-array-type':
            return [fmt.format(resolve_expr(lhs), '1\'sbx')]
        else:
            raise RuntimeError('invalid type')
    else:
        lhs = resolve_expr(lhs)
        rhs = resolve_expr(rhs)
        return [fmt.format(lhs, rhs)]

def format_stmt(stmt, indent):
    if stmt.kind == 'assign-stmt':
        return ''.join(format_assign_stmt(stmt.lhs, stmt.rhs, '{}{} {} {};\n'.format(indent, '{}', '<=' if stmt.delayed else '=', '{}')))
    if stmt.kind == 'if-stmt':
        cond = resolve_expr(stmt.cond)
        true_body = format_stmts(stmt.true_body, indent + '    ')
        if stmt.false_body is not None:
            false_body = format_stmts(stmt.false_body, indent + '    ')
            return '{ind}if ({cond}) begin\n{tr}{ind}end else begin\n{fal}{ind}end\n'.format(ind=indent, cond=cond, tr=true_body, fal=false_body)
        else:
            return '{ind}if ({cond}) begin\n{tr}{ind}end\n'.format(ind=indent, cond=cond, tr=true_body)
    if stmt.kind == 'switch-stmt':
        body = []
        for case in stmt.cases:
            case_value = resolve_expr(case.value)
            stmts = format_stmts(case.body, indent + '        ')
            body.append('{ind}{val}: begin\n{stmts}{ind}end\n'.format(ind=indent + '    ', val=case_value, stmts=stmts))
        return '{ind}casez ({val})\n{body}{ind}endcase\n'.format(ind=indent, val=resolve_expr(stmt.value), body=''.join(body))
    raise RuntimeError('unknown stmt')

def format_stmts(stmts, indent):
    return ''.join([format_stmt(stmt, indent) for stmt in stmts])

def _gen_module(mod, fin):
    ports = []

    for output, name, bounds in expand_ports(mod.ports):
        ports.append('{}{} {}'.format('output reg' if output else 'input', bounds, name))

    decls = []
    for decl in mod.decls:
        if decl.kind == 'always':
            decls.append('always @(*) begin\n{}end\n'.format(format_stmts(decl.body, '    ')))
        elif decl.kind == 'on':
            specs = []
            for spec in decl.specs:
                dir = 'posedge' if spec.rising else 'negedge'
                specs.append('{} {}'.format(dir, spec.name))
            decls.append('always @({}) begin\n{}end\n'.format(' or '.join(specs), format_stmts(decl.body, '    ')))
        elif decl.kind == 'inst-inst':
            out = []
            pms = []
            for output, name, bounds in expand_ports(decl.module.ports):
                if output:
                    out.append('wire{} {}__{};\n'.format(bounds, decl.name, name))
                    pms.append('.{}({}__{})'.format(name, decl.name, name))

            for pm in decl.port_maps:
                pms.append('.{}({})'.format(resolve_expr(pm.target), resolve_expr(pm.source)))
            out.append('{} {}(\n    {}\n    );\n'.format(decl.module.specs[0].name, decl.name, ',\n    '.join(pms)))
            decls.append(''.join(out))
        elif decl.kind == 'signal':
            for output, name, bounds in expand_port(decl.name, None, decl.type):
                decls.append('reg{} {};\n'.format(bounds, name))
        else:
            raise RuntimeError('unknown decl')
    fin.write('''\
module {name}(
    {ports}
    );

{decls}
endmodule

'''.format(name=mod.specs[0].name, ports=',\n    '.join(ports), decls='\n'.join(decls)))

def gen_verilog(mods, file):
    for mod in mods:
        _gen_module(mod, file)
