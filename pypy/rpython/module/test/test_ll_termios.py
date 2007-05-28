
import py
import sys
import os

from pypy.tool.autopath import pypydir
from pypy.translator.c.test.test_genc import compile
from pypy.tool.udir import udir

def setup_module(mod):
    try:
        import pexpect
        mod.pexpect = pexpect
    except ImportError:
        py.test.skip("Pexpect not found")
    try:
        import termios
        mod.termios = termios
    except ImportError:
        py.test.skip("termios not found")
    py_py = py.path.local(pypydir).join('bin', 'py.py')
    assert py_py.check()
    mod.py_py = py_py

class TestTermios(object):
    def _spawn(self, *args, **kwds):
        print 'SPAWN:', args, kwds
        child = pexpect.spawn(*args, **kwds)
        child.logfile = sys.stdout
        return child

    def spawn(self, argv):
        return self._spawn(sys.executable, argv)

    def test_getattr(self):
        source = py.code.Source("""
        import sys
        sys.path.insert(0, '%s')
        from pypy.translator.c.test.test_genc import compile
        import termios
        def runs_tcgetattr():
            tpl = list(termios.tcgetattr(2)[:-1])
            print tpl

        fn = compile(runs_tcgetattr, [], backendopt=False,
)
        print 'XXX'
        fn(expected_extra_mallocs=1)
        print str(termios.tcgetattr(2)[:-1])
        """ % os.path.dirname(pypydir))
        f = udir.join("test_tcgetattr.py")
        f.write(source)
        child = self.spawn([str(f)])
        child.expect("XXX")
        child.expect('\[[^\]]*\]')
        first = child.match.group(0)
        child.expect('\[[^\]]*\]')
        second = child.match.group(0)
        assert first == second

    #def test_one(self):
    #    child = self.spawn()
    #    child.expect("Python ")
    #    child.expect('>>> ')
    #    child.sendline('import termios')
    #    child.expect('>>> ')
    #    child.sendline('termios.tcgetattr(0)')
    #    child.expect('\[.*?\[.*?\]\]')
    #    lst = eval(child.match.group(0))
    #    assert len(lst) == 7
    #    assert len(lst[-1]) == 32 # XXX is this portable???
