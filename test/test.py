from better_verilog.__main__ import main as bv_main
from cStringIO import StringIO
import sys

def main():
    out = StringIO()
    r = bv_main(['hello_world.bv'], stdout=out)
    if r:
        print('failed: {}'.format(r))
        return r
    with open('hello_world.v', 'r') as fin:
        real = out.getvalue()
        exp = fin.read()
        if real != exp:
            print('incorrect output')
            print(real)
            print(exp)
            return 1

if __name__ == '__main__':
    sys.exit(main())
