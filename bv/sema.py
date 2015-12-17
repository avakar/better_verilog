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
        return self.map.iteritems()

def sema(units):
    ctx = Scope()
    for unit in units:
        unit.scope = ctx
        for decl in unit.decls:
            if decl.kind in ('interface', 'struct', 'enum', 'module'):
                unit.scope.add(decl.name, decl)
                decl.scope = Scope(parent=unit.scope)
            if decl.kind == 'module':
                for port in decl.ports:
                    decl.scope.add(port.name, port)
                decl.defs = []

    for unit in units:
        for decl in unit.decls:
            if decl.kind == 'def':
                mod = ctx.lookup(decl.name, 'module')
                mod.defs.append(decl)
                decl.mod = mod
                decl.scope = Scope(parent=mod.scope)
                for def_decl in decl.decls:
                    if def_decl.kind in ('signal', 'inst'):
                        decl.scope.add(def_decl.name, def_decl)

    return ctx
