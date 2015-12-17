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
    return ctx
