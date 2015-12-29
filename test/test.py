from better_verilog.__main__ import main as bv_main
import sys, os.path

try:
    from StringIO import StringIO
except:
    from io import StringIO

def main():
    this_dir = os.path.split(__file__)[0]

    out = StringIO()
    r = bv_main([os.path.join(this_dir, 'hello_world.bv')], stdout=out)
    if r:
        print('failed: {}'.format(r))
        return r
    with open(os.path.join(this_dir, 'hello_world.v'), 'r') as fin:
        real = out.getvalue()
        exp = fin.read()
        if real != exp:
            print('incorrect output')
            print(real)
            print(exp)
            return 1
    print('success')

if __name__ == '__main__':
    sys.exit(main())
