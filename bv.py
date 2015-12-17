import argparse, sys
from bv.parser import parse as parse_bv
from bv.ast import print_value
from bv.gen_verilog import gen_verilog
from bv.sema import sema

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-m', '--module')
    p.add_argument('--print-ast', action='store_true')
    p.add_argument('input', nargs='+', type=argparse.FileType('r'))
    args = p.parse_args()

    units = [parse_bv(input) for input in args.input]
    if args.print_ast:
        print_value(units, file=sys.stdout)

    ctx = sema(units)
    if args.module:
        mod = ctx.lookup(args.module, 'module')
        if mod is None:
            raise RuntimeError('no module')
        gen_verilog(mod, file=sys.stdout)
