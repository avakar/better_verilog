import argparse, sys, glob
from .parser import parse as parse_bv, parse_type
from .ast import print_value
from .gen_verilog import gen_verilog
from .sema import sema, Context

def main(args=None, stdout=sys.stdout):
    p = argparse.ArgumentParser()
    p.add_argument('-m', '--module')
    p.add_argument('--print-ast', action='store_true')
    p.add_argument('input', nargs='+')
    args = p.parse_args(args=args)

    new_inputs = []
    for input_glob in args.input:
        inputs = [open(fname, 'r') for fname in glob.iglob(input_glob)]
        if not inputs:
            print>>sys.stderr, 'error: not found: {}'.format(input_glob)
            sys.exit(2)
        new_inputs.extend(inputs)
    args.input = new_inputs

    units = [parse_bv(input) for input in args.input]
    if args.print_ast:
        print_value(units, file=stdout)

    root_scope = sema(units)
    ctx = Context(units, root_scope)

    if args.module:
        mod_inst_spec = parse_type(args.module)
        ctx.instantiate_module(root_scope, mod_inst_spec.name, mod_inst_spec.args)
    else:
        for name, entity in root_scope.items():
            if entity.kind == 'module' and not entity.params:
                ctx.instantiate_module(root_scope, name, ())
    gen_verilog(ctx.all_modules(), file=stdout)

if __name__ == '__main__':
    sys.exit(main())
