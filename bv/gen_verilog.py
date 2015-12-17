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
        out_dir = 'output' if dir == 'o' else 'input'
        return [(out_dir, '', name)]

def _gen_module(mod, fin):
    ports = []
    for port in mod.ports:
        new_ports = expand_signal(mod.scope, port.dir, port.name, port.type)
        for pre, suf, name in new_ports:
            ports.append('{}{} {}'.format(pre, suf, name))
    fin.write('''\
module {name}(
    {ports}
    );
endmodule
'''.format(name=mod.name, ports=',\n    '.join(ports)))

def gen_verilog(mod, file):
    _gen_module(mod, file)

