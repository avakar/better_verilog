from .parser import parse_type
from .eval import eval_int_expr
from .ast import Node

class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.map = {}

    def add(self, name, node):
        self.map[name] = node

    def lookup(self, name, kind=None):
        r = self.map.get(name)
        if r is not None:
            return r if not kind is None or r.kind != kind else None
        if self.parent:
            return self.parent.lookup(name, kind=kind)
        return None

    def items(self):
        return self.map.items()

def _resolve_type(scope, type):
    if type.kind == 'array-type':
        _resolve_type(scope, type.subtype)
    elif type.kind == 'set-type':
        enum_decl = scope.lookup(type.enum)
        if enum_decl is None:
            raise RuntimeError('unknown type: ' + type.name)
        if enum_decl.kind != 'enum':
            raise RuntimeError('expected enum, found ' + type.enum)
        type.decl = enum_decl
    elif type.kind == 'struct-type':
        decl = scope.lookup(type.name)
        if decl is None:
            raise RuntimeError('unknown type: ' + type.name)
        if decl.kind not in ('interface', 'enum'):
            raise RuntimeError('expected type, found ' + type.name)
        type.decl = decl

def sema(units):
    ctx = Scope()
    for unit in units:
        unit.scope = ctx
        for decl in unit.decls:
            if decl.kind in ('interface', 'enum', 'module'):
                unit.scope.add(decl.name, decl)
                decl.scope = Scope(parent=unit.scope)
            if decl.kind == 'module':
                for port in decl.ports:
                    decl.scope.add(port.name, port)
                decl.defs = []

    for unit in units:
        for decl in unit.decls:
            if decl.kind == 'interface':
                for mem in decl.decls:
                    _resolve_type(decl.scope, mem.type)
                    if mem.kind == 'use' and mem.type.kind != 'struct-type':
                        raise RuntimeError('use directive must refer to an interface')
            elif decl.kind == 'module':
                for port in decl.ports:
                    _resolve_type(decl.scope, port.type)
            elif decl.kind == 'def':
                mod = ctx.lookup(decl.name, 'module')
                mod.defs.append(decl)
                decl.mod = mod
                decl.scope = Scope(parent=mod.scope)
                for def_decl in decl.decls:
                    if def_decl.kind in ('signal', 'inst'):
                        decl.scope.add(def_decl.name, def_decl)
                for def_decl in decl.decls:
                    if def_decl.kind in 'signal':
                        _resolve_type(decl.scope, def_decl.type)

    return ctx

class Context:
    def __init__(self, units, root_scope):
        self.units = units
        self._root_scope = root_scope
        self._intfs = {}
        self._modules = {}

        self._active_intf_insts = set()
        self._active_mod_insts = set()

    def all_modules(self):
        return self._modules.values()

    def instantiate_module(self, scope, module_name, args):
        mod = self._root_scope.lookup(module_name, 'module')
        if mod is None:
            raise RuntimeError('unknown module: ' + module_name)

        arg_values = self._match_args(scope, mod.params, args)

        mod_inst_spec = (module_name, tuple(arg_values))
        if mod_inst_spec in self._active_intf_insts:
            raise RuntimeError('recursive instantiation')

        if mod_inst_spec in self._modules:
            return self._modules[mod_inst_spec]

        mod_inst = Node('module-inst', specs=(mod, tuple(arg_values)))
        self._active_mod_insts.add(mod_inst_spec)
        self._modules[mod_inst_spec] = mod_inst
        self._inst_module(mod_inst)
        self._active_mod_insts.remove(mod_inst_spec)
        return mod_inst

    def instantiate_intf(self, scope, intf_name, args):
        intf = self._root_scope.lookup(intf_name, 'interface')
        if intf is None:
            raise RuntimeError('unknown interface: ' + intf_name)

        arg_values = self._match_args(scope, intf.params, args)

        intf_inst_spec = (intf_name, tuple(arg_values))
        if intf_inst_spec in self._active_intf_insts:
            raise RuntimeError('recursive instantiation')

        if intf_inst_spec in self._intfs:
            return self._intfs[intf_inst_spec]

        intf_inst = Node('intf-inst', specs=(intf, tuple(arg_values)))
        self._intfs[intf_inst_spec] = intf_inst
        self._active_intf_insts.add(intf_inst_spec)
        self._inst_intf(intf_inst)
        self._active_intf_insts.remove(intf_inst_spec)
        return intf_inst

    def _match_args(self, scope, params, args):
        arg_values = [None]*len(params)
        for i, arg in enumerate(args):
            if arg.kw_name is not None:
                for param_idx, (param_name, param_type) in enumerate(params):
                    if param_name == arg.kw_name:
                        i = param_idx
                        break
                else:
                    raise RuntimeError('invalid parameter name: ' + arg.kw_name)

            val = eval_int_expr(scope, arg.value)
            arg_values[i] = val

        if any(val is None for val in arg_values):
            raise RuntimeError('not all arguments are specified')

        return arg_values

    def _inst_type(self, scope, type):
        if type.kind == 'struct-type':
            type_decl = scope.lookup(type.name)
            if type_decl is None or type_decl.kind not in ('interface', 'enum'):
                raise RuntimeError('expected type')
            if type_decl.kind == 'interface':
                type_decl = self.instantiate_intf(scope, type.name, type.args)
                return Node('intf-inst-type', decl=type_decl)
            elif type_decl.kind == 'enum':
                return Node('enum-type', decl=type_decl)
            else:
                raise RuntimeError('invalid type')
        if type.kind == 'array-type':
            subtype = self._inst_type(scope, type.subtype)
            lb = eval_int_expr(scope, type.left_bound)
            rb = eval_int_expr(scope, type.right_bound)
            return Node('resolved-array-type', subtype=subtype, left_bound=lb, right_bound=rb)
        return type

    def _make_arg_scope(self, params, args):
        assert len(params) == len(args)
        r = Scope(parent=self._root_scope)
        for (param_name, param_type), arg in zip(params, args):
            r.add(param_name, Node('num', value=arg))
        return r

    def _inst_intf(self, intf_inst):
        intf, args = intf_inst.specs
        scope = self._make_arg_scope(intf.params, args)

        ports = []
        for decl in intf.decls:
            if decl.kind == 'port':
                ports.append(Node('port', dir=decl.dir, name=decl.name, type=self._inst_type(scope, decl.type)))
            elif decl.kind == 'use':
                intf = self.instantiate_intf(scope, decl.type.name, decl.type.args)
                for port in intf.ports:
                    ports.append(Node('port', dir=port.dir, name=port.name, type=port.type))
        intf_inst.ports = ports

    def _inst_module(self, mod_inst):
        mod, args = mod_inst.specs
        scope = self._make_arg_scope(mod.params, args)

        ports = []
        for port in mod.ports:
            port = Node('port', dir=port.dir, name=port.name, type=self._inst_type(scope, port.type))
            scope.add(port.name, port)
            ports.append(port)

        mod_inst.scope = scope
        mod_inst.ports = ports

        new_decls = []
        for mod_def in mod.defs:
            def_scope = Scope(parent=scope)
            for decl in mod_def.decls:
                if decl.kind == 'signal':
                    new_decl = Node('signal', name=decl.name, type=self._inst_type(scope, decl.type))
                    def_scope.add(decl.name, new_decl)
                    new_decls.append(new_decl)
                elif decl.kind == 'inst':
                    inst_mod = self.instantiate_module(scope, decl.module, []) # XXX: module should have args
                    new_decl = Node('inst-inst', name=decl.name, module=inst_mod, specs=decl, type=Node('module-inst-type', decl=inst_mod))
                    def_scope.add(decl.name, new_decl)
                    new_decls.append(new_decl)
                else:
                    assert decl.kind in ('always', 'on')

            for inst in new_decls:
                if inst.kind != 'inst-inst':
                    continue
                new_pms = []
                for pm in inst.specs.port_maps:
                    target = self._inst_target_port_expr(inst.module, pm.target)
                    new_pms.append(Node('port_map', target=target, source=self._inst_expr(def_scope, pm.source)))
                inst.port_maps = new_pms

            for decl in mod_def.decls:
                if decl.kind == 'always':
                    new_decls.append(Node('always', body=self._inst_stmts(def_scope, decl.body)))
                elif decl.kind == 'on':
                    new_decls.append(Node('on', specs=decl.specs, body=self._inst_stmts(def_scope, decl.body)))
                else:
                    assert decl.kind in ('signal', 'inst')

        mod_inst.decls = new_decls

    def _inst_stmts(self, scope, stmts):
        return [self._inst_stmt(scope, stmt) for stmt in stmts]

    def _inst_stmt(self, scope, stmt):
        if stmt.kind == 'assign-stmt':
            lhs = self._inst_expr(scope, stmt.lhs)
            rhs = self._inst_expr(scope, stmt.rhs)

            if rhs.type.kind == 'atom-type':
                assert rhs.kind == 'atom'
                if lhs.type.kind == 'enum-type':
                    index = lhs.type.decl.enumers.index(rhs.name)
                    rhs = Node('enum-expr', value_index=index, type=lhs.type)
                elif lhs.type.kind == 'intf-inst-type':
                    if rhs.name != 'x':
                        raise RuntimeError('you can only assign \'x to a structure')
                    rhs = Node('x-expr', type=Node('x-type'))
                else:
                    raise RuntimeError('unsupported yet')
            elif rhs.type.kind == 'set-lit-type':
                assert rhs.kind == 'set-expr'
                if lhs.type.kind != 'set-type':
                    raise RuntimeError('type mismatch')
                v = ['0']*len(lhs.type.decl.enumers)
                for item in rhs.items:
                    v[lhs.type.decl.enumers.index(item)] = '1'
                rhs = Node('sized-num', size=len(v), v=''.join(v[::-1]), type=Node('int-type'))

            return Node('assign-stmt', lhs=lhs, rhs=rhs, delayed=stmt.delayed)
        elif stmt.kind == 'if-stmt':
            cond = self._inst_expr(scope, stmt.cond)
            true_body = self._inst_stmts(scope, stmt.true_body)
            false_body = self._inst_stmts(scope, stmt.false_body) if stmt.false_body is not None else None
            return Node('if-stmt', cond=cond, true_body=true_body, false_body=false_body)
        elif stmt.kind == 'switch-stmt':
            value = self._inst_expr(scope, stmt.value)
            cases = []
            for case in stmt.cases:
                case_value = self._inst_expr(scope, case.value)
                case_body = self._inst_stmts(scope, case.body)
                cases.append(Node('case-stmt', value=case_value, body=case_body))
            return Node('switch-stmt', value=value, cases=cases)
        else:
            raise RuntimeError('invalid stmt')

    def _inst_target_port_expr(self, mod_inst, expr):
        if expr.kind == 'ref':
            for port in mod_inst.ports:
                if port.name == expr.name:
                    break
            else:
                raise RuntimeError('invalid port name')
            return Node('ref', name=expr.name, decl=port, type=port.type)

    def _inst_expr(self, scope, expr):
        if expr.kind == 'binary-expr':
            lhs = self._inst_expr(scope, expr.lhs)
            rhs = self._inst_expr(scope, expr.rhs)
            return Node('binary-expr', lhs=lhs, rhs=rhs, op=expr.op, type=Node('arith-type'))
        elif expr.kind == 'unary-expr':
            arg = self._inst_expr(scope, expr.arg)
            return Node('unary-expr', arg=arg, op=expr.op, type=arg.type)
        elif expr.kind == 'cast-expr':
            type = self._inst_type(scope, expr.type)
            expr = self._inst_expr(scope, expr.expr)
            return Node('cast-expr', type=type, expr=expr)
        elif expr.kind == 'member-expr':
            e = self._inst_expr(scope, expr.expr)
            if e.type.kind not in ('intf-inst-type', 'module-inst-type'):
                raise RuntimeError('member access on non-interface')
            for port in e.type.decl.ports:
                if expr.member == port.name:
                    break
            else:
                raise RuntimeError('non-existent member')
            return Node('member-expr', expr=e, member=expr.member, decl=port, type=port.type)
        elif expr.kind == 'slice-expr':
            e = self._inst_expr(scope, expr.expr)
            if e.type.kind != 'resolved-array-type':
                raise RuntimeError('slicing is only possible on arrays')
            lb = eval_int_expr(scope, expr.lower_bound)
            rb = eval_int_expr(scope, expr.upper_bound)
            lower_bound = e.type.left_bound
            upper_bound = e.type.right_bound
            if lower_bound > upper_bound:
                lower_bound, upper_bound = upper_bound, lower_bound
            if not lower_bound <= lb <= upper_bound or not lower_bound <= rb <= upper_bound:
                raise RuntimeError('invalid slice bounds')
            t = Node('resolved-array-type', subtype=e.type.subtype, left_bound=lb, right_bound=rb)
            return Node('slice-expr', expr=e, lower_bound=lb, upper_bound=rb, type=t)
        elif expr.kind == 'subscript-expr':
            e = self._inst_expr(scope, expr.expr)
            if e.type.kind != 'resolved-array-type':
                raise RuntimeError('only arrays can be subscripted')
            index = self._inst_expr(scope, expr.index)
            if index.type != 'int-type':
                raise RuntimeError('array subscripts must be integers')
            return Node('subscript-expr', expr=e, index=index, type=e.type.subtype)
        #elif expr.kind == 'call-expr':
        #    fn = self._inst_expr(scope, expr.fn)
        #    args = [self._inst_expr(scope, arg) for arg in expr.args]
        #    return Node('call-expr', fn=fn, args=args)
        elif expr.kind == 'ref':
            decl = scope.lookup(expr.name)
            return Node('ref', name=expr.name, decl=decl, type=decl.type)
        elif expr.kind == 'atom':
            return Node('atom', name=expr.name, type=Node('atom-type'))
        elif expr.kind == 'num':
            return Node('num', value=expr.value, type=Node('int-type'))
        elif expr.kind == 'sized-num':
            return Node('sized-num', size=expr.size, v=expr.v, type=Node('int-type'))
        elif expr.kind == 'set-expr':
            return Node('set-expr', items=expr.items, type=Node('set-lit-type'))
        else:
            raise RuntimeError('invalid expr')
