import sys

class Node:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.kw = kw

    def __getattr__(self, key):
        return self.kw[key]

    def __repr__(self):
        r = [repr(self.kind)]
        r.extend(('{}={!r}'.format(k, v) for k, v in self.kw.items()))
        return 'Node({})'.format(', '.join(r))

def _print_value(v, nl=True, indent='', file=sys.stdout):
    if isinstance(v, list):
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
        for k, vv in v.kw.items():
            file.write('\n')
            file.write('{}{}: '.format(indent, k))
            _print_value(vv,  nl=False, indent=indent+'    ', file=file)
    else:
        file.write(repr(v))

def print_value(v, file=sys.stdout):
    _print_value(v, file=file)
    file.write('\n')
