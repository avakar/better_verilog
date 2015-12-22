import argparse, sys, glob
from bv.parser import parse as parse_bv, parse_type
from bv.ast import print_value
from bv.gen_verilog import gen_verilog
from bv.sema import sema, Context

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-m', '--module')
    p.add_argument('--print-ast', action='store_true')
    p.add_argument('input', nargs='+')
    args = p.parse_args()

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
        print_value(units, file=sys.stdout)

    root_scope = sema(units)
    ctx = Context(units, root_scope)

    if args.module:
        mod_inst_spec = parse_type(args.module)
        ctx.instantiate_module(root_scope, mod_inst_spec.name, mod_inst_spec.args)
        gen_verilog(ctx.all_modules(), file=sys.stdout)
