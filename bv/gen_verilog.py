import math
from .sema import Scope
from .ast import Node

_builtin_fns = {
    'log2': lambda x: int(math.log(x, 2))
    }

def eval_builtin_fn(scope, expr):
    if expr.kind == 'ref':
        return _builtin_fns[expr.name]
    raise RuntimeError('invalid fn')

def eval_int_expr(scope, expr):
    if expr.kind == 'num':
        return expr.value
    if expr.kind == 'sized-num':
        if any(c in 'xz?' for c in expr.v):
            raise RuntimeError('invalid int expr')
        return int(expr.v, 2)
    if expr.kind == 'unary-expr':
        if expr.op == '-':
            return -eval_int_expr(scope, expr.arg)
    if expr.kind == 'binary-expr':
        lhs = eval_int_expr(scope, expr.lhs)
        rhs = eval_int_expr(scope, expr.rhs)
        if expr.op == '+':
            return lhs + rhs
        if expr.op == '-':
            return lhs - rhs
        if expr.op == '*':
            return lhs * rhs
        if expr.op == '/':
            return lhs / rhs
    if expr.kind == 'call-expr':
        callee = eval_builtin_fn(scope, expr.fn)
        args = [eval_int_expr(scope, arg) for arg in expr.args]
        return callee(*args)
    if expr.kind == 'ref':
        target = scope.lookup(expr.name)
        return eval_int_expr(getattr(target, 'scope', None), target)
    raise RuntimeError('invalid int expr')

def make_type_scope(decl, arg_scope, args):
    res = Scope(parent=decl.scope)
    if decl.kind != 'interface':
        if args:
            raise RuntimeError('argument cound mismatch')
        return res

    def assoc_arg(param, arg):
        res.add(param, Node('num', value=eval_int_expr(arg_scope, arg)))

    for i, arg in enumerate(args):
        if arg.kw_name is None:
            assoc_arg(decl.params[i][0], arg.value)
        else:
            assoc_arg(arg.kw_name, arg.value)
    return res

def expand_signal(scope, dir, name, type):
    if type.kind == 'array-type':
        suffix = []
        for lb, rb in type.bounds:
            lb = eval_int_expr(scope, lb)
            rb = eval_int_expr(scope, rb)
            suffix.append('[{}:{}]'.format(lb, rb))
        suffix = ''.join(suffix)
        sublist = expand_signal(scope, dir, name, type.subtype)
        res = []
        for pre, suf, name in sublist:
            res.append((pre, suffix + suf, name))
        return res
    if type.kind == 'struct-type':
        subtype = scope.lookup(type.name)
        subtype_scope = make_type_scope(subtype, scope, type.args)
        res = []
        for member in subtype.decls:
            if member.kind == 'use':
                res.extend(expand_signal(subtype_scope, dir, name, member.type))
            if member.kind == 'port':
                new_dir = 'o' if member.dir == dir else 'i'
                res.extend(expand_signal(subtype_scope, new_dir, '{}__{}'.format(name, member.name), member.type))
        return res
    if type.kind == 'bit-type':
        if dir is None:
            out_dir = 'reg'
        else:
            out_dir = 'output reg' if dir == 'o' else 'input'
        return [(out_dir, '', name)]

def format_expr(scope, expr):
    if expr.kind == 'binary-expr':
        lhs = format_expr(scope, expr.lhs)
        rhs = format_expr(scope, expr.rhs)
        return '({}) {} ({})'.format(lhs, expr.op, rhs)
    if expr.kind == 'unary-expr':
        e = format_expr(scope, expr.arg)
        return '{}({})'.format(expr.op, e)
    if expr.kind == 'member-expr':
        e = format_expr(scope, expr.expr)
        return '({}).{}'.format(e, expr.member)
    if expr.kind == 'num':
        return str(expr.value)
    if expr.kind == 'sized-num':
        return '{}\'b{}'.format(expr.size, expr.v)
    if expr.kind == 'ref':
        return expr.name
    raise RuntimeError('unknown expr')

def format_stmt(scope, stmt, indent):
    if stmt.kind == 'assign-stmt':
        lhs = format_expr(scope, stmt.lhs)
        rhs = format_expr(scope, stmt.rhs)
        op = '<=' if stmt.delayed else '='
        return '{}{} {} {};\n'.format(indent, lhs, op, rhs)
    if stmt.kind == 'if-stmt':
        cond = format_expr(scope, stmt.cond)
        true_body = format_stmts(scope, stmt.true_body, indent + '    ')
        if stmt.false_body is not None:
            false_body = format_stmts(scope, stmt.false_body, indent + '    ')
            return '{ind}if ({cond}) begin\n{tr}{ind}end else begin\n{fal}{ind}end\n'.format(ind=indent, cond=cond, tr=true_body, fal=false_body)
        else:
            return '{ind}if ({cond}) begin\n{tr}{ind}end\n'.format(ind=indent, cond=cond, tr=true_body)
    raise RuntimeError('unknown stmt')

def format_stmts(scope, stmts, indent):
    return ''.join([format_stmt(scope, stmt, indent) for stmt in stmts])

def _gen_module(mod, fin):
    ports = []
    for port in mod.ports:
        new_ports = expand_signal(mod.scope, port.dir, port.name, port.type)
        for pre, suf, name in new_ports:
            ports.append('{}{} {}'.format(pre, suf, name))

    decls = []
    for def_ in mod.defs:
        for decl in def_.decls:
            if decl.kind == 'always':
                decls.append('always @(*) begin\n{}end\n'.format(format_stmts(mod, decl.body, '    ')))
            elif decl.kind == 'on':
                specs = []
                for spec in decl.specs:
                    dir = 'posedge' if spec.rising else 'negedge'
                    specs.append('{} {}'.format(dir, spec.name))
                decls.append('always @({}) begin\n{}end\n'.format(' or '.join(specs), format_stmts(mod, decl.body, '    ')))
            elif decl.kind == 'inst':
                pms = []
                for pm in decl.port_maps:
                    pms.append('.{}({})'.format(pm.name, format_expr(mod.scope, pm.conn)))
                decls.append('{} {}(\n    {}\n    );\n'.format(decl.module, decl.name, ',\n    '.join(pms)))
            elif decl.kind == 'signal':
                new_sigs = expand_signal(mod.scope, None, decl.name, decl.type)
                for pre, suf, name in new_sigs:
                    decls.append('{}{} {};\n'.format(pre, suf, name))
            else:
                raise RuntimeError('unknown decl')
    fin.write('''\
module {name}(
    {ports}
    );

{decls}
endmodule
'''.format(name=mod.name, ports=',\n    '.join(ports), decls='\n'.join(decls)))

def gen_verilog(mod, file):
    _gen_module(mod, file)

