import math

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
