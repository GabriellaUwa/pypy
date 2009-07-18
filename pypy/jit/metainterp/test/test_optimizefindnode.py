import py, random

from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.lltypesystem.rclass import OBJECT, OBJECT_VTABLE

from pypy.jit.backend.llgraph import runner
from pypy.jit.metainterp.history import (BoxInt, BoxPtr, ConstInt, ConstPtr,
                                         Const, ConstAddr, TreeLoop, BoxObj,
                                         ConstObj, AbstractDescr)
from pypy.jit.metainterp.optimizefindnode import PerfectSpecializationFinder
from pypy.jit.metainterp.optimizefindnode import BridgeSpecializationFinder
from pypy.jit.metainterp.optimize import sort_descrs
from pypy.jit.metainterp.specnode import NotSpecNode, prebuiltNotSpecNode
from pypy.jit.metainterp.specnode import FixedClassSpecNode
from pypy.jit.metainterp.specnode import VirtualInstanceSpecNode
from pypy.jit.metainterp.test.oparser import parse

# ____________________________________________________________

def equaloplists(oplist1, oplist2):
    print '-'*20, 'Comparing lists', '-'*20
    for op1, op2 in zip(oplist1, oplist2):
        txt1 = str(op1)
        txt2 = str(op2)
        while txt1 or txt2:
            print '%-39s| %s' % (txt1[:39], txt2[:39])
            txt1 = txt1[39:]
            txt2 = txt2[39:]
        assert op1.opnum == op2.opnum
        assert len(op1.args) == len(op2.args)
        for x, y in zip(op1.args, op2.args):
            assert x == y
        assert op1.result == op2.result
        assert op1.descr == op2.descr
        if op1.suboperations:
            assert equaloplists(op1.suboperations, op2.suboperations)
    assert len(oplist1) == len(oplist2)
    print '-'*57
    return True

def test_equaloplists():
    ops = """
    [i0]
    i1 = int_add(i0, 1)
    guard_true(i1)
        i2 = int_add(i1, 1)
        fail(i2)
    jump(i1)
    """
    loop1 = parse(ops)
    loop2 = parse(ops)
    loop3 = parse(ops.replace("i2 = int_add", "i2 = int_sub"))
    assert equaloplists(loop1.operations, loop2.operations)
    py.test.raises(AssertionError,
                   "equaloplists(loop1.operations, loop3.operations)")

def test_sort_descrs():
    class PseudoDescr(AbstractDescr):
        def __init__(self, n):
            self.n = n
        def sort_key(self):
            return self.n
    lst = [PseudoDescr(2), PseudoDescr(3), PseudoDescr(6)]
    lst2 = lst[:]
    random.shuffle(lst2)
    sort_descrs(lst2)
    assert lst2 == lst

# ____________________________________________________________

class LLtypeMixin(object):
    type_system = 'lltype'

    node_vtable = lltype.malloc(OBJECT_VTABLE, immortal=True)
    node_vtable_adr = llmemory.cast_ptr_to_adr(node_vtable)
    node_vtable2 = lltype.malloc(OBJECT_VTABLE, immortal=True)
    node_vtable_adr2 = llmemory.cast_ptr_to_adr(node_vtable2)
    cpu = runner.LLtypeCPU(None)

    NODE = lltype.GcForwardReference()
    NODE.become(lltype.GcStruct('NODE', ('parent', OBJECT),
                                        ('value', lltype.Signed),
                                        ('next', lltype.Ptr(NODE))))
    NODE2 = lltype.GcStruct('NODE2', ('parent', NODE),
                                     ('other', lltype.Ptr(NODE)))
    node = lltype.malloc(NODE)
    nodebox = BoxPtr(lltype.cast_opaque_ptr(llmemory.GCREF, node))
    nodebox2 = BoxPtr(lltype.cast_opaque_ptr(llmemory.GCREF, node))
    nodesize = cpu.sizeof(NODE)
    nodesize2 = cpu.sizeof(NODE2)
    valuedescr = cpu.fielddescrof(NODE, 'value')
    nextdescr = cpu.fielddescrof(NODE, 'next')

    cpu.class_sizes = {cpu.cast_adr_to_int(node_vtable_adr): cpu.sizeof(NODE),
                      cpu.cast_adr_to_int(node_vtable_adr2): cpu.sizeof(NODE2)}
    namespace = locals()

class OOtypeMixin(object):
    type_system = 'ootype'
    
    cpu = runner.OOtypeCPU(None)

    NODE = ootype.Instance('NODE', ootype.ROOT, {})
    NODE._add_fields({'value': ootype.Signed,
                      'next': NODE})
    NODE2 = ootype.Instance('NODE2', NODE, {'other': NODE})

    node_vtable = ootype.runtimeClass(NODE)
    node_vtable_adr = ootype.cast_to_object(node_vtable)
    node_vtable2 = ootype.runtimeClass(NODE2)
    node_vtable_adr2 = ootype.cast_to_object(node_vtable2)

    node = ootype.new(NODE)
    nodebox = BoxObj(ootype.cast_to_object(node))
    nodebox2 = BoxObj(ootype.cast_to_object(node))
    valuedescr = cpu.fielddescrof(NODE, 'value')
    nextdescr = cpu.fielddescrof(NODE, 'next')
    nodesize = cpu.typedescrof(NODE)
    nodesize2 = cpu.typedescrof(NODE2)

    cpu.class_sizes = {node_vtable_adr: cpu.typedescrof(NODE),
                       node_vtable_adr2: cpu.typedescrof(NODE2)}
    namespace = locals()

# ____________________________________________________________

class BaseTestOptimize(object):

    def parse(self, s, boxkinds=None):
        return parse(s, self.cpu, self.namespace,
                     type_system=self.type_system,
                     boxkinds=boxkinds)

    def assert_equal(self, optimized, expected):
        equaloplists(optimized.operations,
                     self.parse(expected).operations)

    def unpack_specnodes(self, text):
        #
        def constclass(cls_vtable):
            if self.type_system == 'lltype':
                return ConstAddr(llmemory.cast_ptr_to_adr(cls_vtable),
                                 self.cpu)
            else:
                return ConstObj(ootype.cast_to_object(cls_vtable))
        def makeFixed(cls_vtable):
            return FixedClassSpecNode(constclass(cls_vtable))
        def makeVirtual(cls_vtable, **kwds_fields):
            fields = []
            for key, value in kwds_fields.items():
                fields.append((self.namespace[key], value))
            fields.sort(key = lambda (x, _): x.sort_key())
            return VirtualInstanceSpecNode(constclass(cls_vtable), fields)
        #
        context = {'Not': prebuiltNotSpecNode,
                   'Fixed': makeFixed,
                   'Virtual': makeVirtual}
        lst = eval('[' + text + ']', self.namespace, context)
        return lst

    def check_specnodes(self, specnodes, text):
        lst = self.unpack_specnodes(text)
        assert len(specnodes) == len(lst)
        for x, y in zip(specnodes, lst):
            assert x._equals(y)
        return True

    def find_nodes(self, ops, spectext, boxkinds=None):
        loop = self.parse(ops, boxkinds=boxkinds)
        perfect_specialization_finder = PerfectSpecializationFinder()
        perfect_specialization_finder.find_nodes_loop(loop)
        self.check_specnodes(perfect_specialization_finder.specnodes, spectext)
        return (loop.getboxes(), perfect_specialization_finder.getnode)

    def test_find_nodes_simple(self):
        ops = """
        [i]
        i0 = int_sub(i, 1)
        guard_value(i0, 0)
          fail(i0)
        jump(i0)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        assert getnode(boxes.i).fromstart
        assert not getnode(boxes.i0).fromstart

    def test_find_nodes_non_escape(self):
        ops = """
        [p0]
        p1 = getfield_gc(p0, descr=nextdescr)
        i0 = getfield_gc(p1, descr=valuedescr)
        i1 = int_sub(i0, 1)
        p2 = getfield_gc(p0, descr=nextdescr)
        setfield_gc(p2, i1, descr=valuedescr)
        jump(p0)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        assert not getnode(boxes.p0).escaped
        assert not getnode(boxes.p1).escaped
        assert not getnode(boxes.p2).escaped
        assert getnode(boxes.p0).fromstart
        assert getnode(boxes.p1).fromstart
        assert getnode(boxes.p2).fromstart

    def test_find_nodes_escape(self):
        ops = """
        [p0]
        p1 = getfield_gc(p0, descr=nextdescr)
        p2 = getfield_gc(p1, descr=nextdescr)
        i0 = getfield_gc(p2, descr=valuedescr)
        i1 = int_sub(i0, 1)
        escape(p1)
        p3 = getfield_gc(p0, descr=nextdescr)
        setfield_gc(p3, i1, descr=valuedescr)
        p4 = getfield_gc(p1, descr=nextdescr)
        setfield_gc(p4, i1, descr=valuedescr)
        jump(p0)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        assert not getnode(boxes.p0).escaped
        assert getnode(boxes.p1).escaped
        assert getnode(boxes.p2).escaped    # forced by p1
        assert getnode(boxes.p3).escaped    # forced because p3 == p1
        assert getnode(boxes.p4).escaped    # forced by p1
        assert getnode(boxes.p0).fromstart
        assert getnode(boxes.p1).fromstart
        assert getnode(boxes.p2).fromstart
        assert getnode(boxes.p3).fromstart
        assert not getnode(boxes.p4).fromstart

    def test_find_nodes_guard_class_1(self):
        ops = """
        [p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        jump(p1)
        """
        boxes, getnode = self.find_nodes(ops, 'Fixed(node_vtable)')
        boxp1 = getnode(boxes.p1)
        assert boxp1.knownclsbox.value == self.node_vtable_adr

    def test_find_nodes_guard_class_2(self):
        ops = """
        [p1]
        p2 = getfield_gc(p1, descr=nextdescr)
        guard_class(p2, ConstClass(node_vtable))
            fail()
        jump(p1)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        assert boxp1.knownclsbox is None
        assert boxp2.knownclsbox.value == self.node_vtable_adr

    def test_find_nodes_guard_class_outonly(self):
        ops = """
        [p1]
        p2 = escape()
        guard_class(p2, ConstClass(node_vtable))
            fail()
        jump(p2)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        assert boxp1.knownclsbox is None
        assert boxp2.knownclsbox.value == self.node_vtable_adr

    def test_find_nodes_guard_class_inonly(self):
        ops = """
        [p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        p2 = escape()
        jump(p2)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        assert boxp1.knownclsbox.value == self.node_vtable_adr
        assert boxp2.knownclsbox is None

    def test_find_nodes_guard_class_inout(self):
        ops = """
        [p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        p2 = escape()
        guard_class(p2, ConstClass(node_vtable))
            fail()
        jump(p2)
        """
        boxes, getnode = self.find_nodes(ops, 'Fixed(node_vtable)')
        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        assert boxp1.knownclsbox.value == self.node_vtable_adr
        assert boxp2.knownclsbox.value == self.node_vtable_adr

    def test_find_nodes_guard_class_mismatch(self):
        ops = """
        [p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        p2 = escape()
        guard_class(p2, ConstClass(node_vtable2))
            fail()
        jump(p2)
        """
        boxes, getnode = self.find_nodes(ops, 'Not')
        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        assert boxp1.knownclsbox.value == self.node_vtable_adr
        assert boxp2.knownclsbox.value == self.node_vtable_adr2

    def test_find_nodes_new_1(self):
        ops = """
        [p1]
        p2 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        jump(p2)
        """
        boxes, getnode = self.find_nodes(ops, 'Virtual(node_vtable)')

        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        assert not boxp1.escaped
        assert not boxp2.escaped

        assert not boxp1.origfields
        assert not boxp1.curfields
        assert not boxp2.origfields
        assert not boxp2.curfields

        assert boxp1.fromstart
        assert not boxp2.fromstart

        assert boxp1.knownclsbox is None
        assert boxp2.knownclsbox.value == self.node_vtable_adr

    def test_find_nodes_new_2(self):
        ops = """
        [i1, p1]
        p2 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        p3 = new_with_vtable(ConstClass(node_vtable2), descr=nodesize2)
        setfield_gc(p2, p3, descr=nextdescr)
        setfield_gc(p3, i1, descr=valuedescr)
        jump(i1, p2)
        """
        self.find_nodes(ops,
            '''Not,
               Virtual(node_vtable,
                       nextdescr=Virtual(node_vtable2,
                                         valuedescr=Not))''')

    def test_find_nodes_new_3(self):
        ops = """
        [sum, p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        i1 = getfield_gc(p1, descr=valuedescr)
        i2 = int_sub(i1, 1)
        sum2 = int_add(sum, i1)
        p2 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        setfield_gc(p2, i2, descr=valuedescr)
        p3 = new_with_vtable(ConstClass(node_vtable2), descr=nodesize2)
        setfield_gc(p2, p3, descr=nextdescr)
        jump(sum2, p2)
        """
        boxes, getnode = self.find_nodes(
            ops,
            '''Not,
               Virtual(node_vtable,
                       valuedescr=Not,
                       nextdescr=Virtual(node_vtable2))''',
            boxkinds={'sum': BoxInt, 'sum2': BoxInt})
        assert getnode(boxes.sum) is not getnode(boxes.sum2)
        assert getnode(boxes.p1) is not getnode(boxes.p2)

        boxp1 = getnode(boxes.p1)
        boxp2 = getnode(boxes.p2)
        boxp3 = getnode(boxes.p3)
        assert not boxp1.escaped
        assert not boxp2.escaped
        assert not boxp3.escaped

        assert not boxp1.curfields
        assert boxp1.origfields[self.valuedescr] is getnode(boxes.i1)
        assert not boxp2.origfields
        assert boxp2.curfields[self.nextdescr] is boxp3

        assert boxp1.fromstart
        assert not boxp2.fromstart
        assert not boxp3.fromstart

        assert boxp1.knownclsbox.value == self.node_vtable_adr
        assert boxp2.knownclsbox.value == self.node_vtable_adr
        assert boxp3.knownclsbox.value == self.node_vtable_adr2

    def test_find_nodes_new_aliasing_0(self):
        ops = """
        [p1, p2]
        p3 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        jump(p3, p3)
        """
        # both p1 and p2 must be NotSpecNodes; it's not possible to pass
        # the same Virtual both in p1 and p2 (at least so far).
        self.find_nodes(ops, 'Not, Not')

    def test_find_nodes_new_aliasing_1(self):
        ops = """
        [sum, p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        p3 = getfield_gc(p1, descr=nextdescr)
        guard_class(p3, ConstClass(node_vtable))
            fail()
        i1 = getfield_gc(p1, descr=valuedescr)
        i2 = int_sub(i1, 1)
        sum2 = int_add(sum, i1)
        p2 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        setfield_gc(p2, i2, descr=valuedescr)
        setfield_gc(p2, p2, descr=nextdescr)
        jump(sum2, p2)
        """
        # the issue is the cycle "p2->p2", which cannot be represented
        # with SpecNodes so far
        self.find_nodes(ops, 'Not, Fixed(node_vtable)',
                        boxkinds={'sum': BoxInt, 'sum2': BoxInt})

    def test_find_nodes_new_aliasing_2(self):
        ops = """
        [p1, p2]
        escape(p2)
        p3 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        jump(p3, p3)
        """
        # both p1 and p2 must be NotSpecNodes; it's not possible to pass
        # in p1 a Virtual and not in p2, as they both come from the same p3.
        self.find_nodes(ops, 'Not, Not')

    def test_find_nodes_new_mismatch(self):
        ops = """
        [p1]
        guard_class(p1, ConstClass(node_vtable))
            fail()
        p2 = new_with_vtable(ConstClass(node_vtable2), descr=nodesize2)
        jump(p2)
        """
        self.find_nodes(ops, 'Not')

    def test_find_nodes_new_aliasing_mismatch(self):
        ops = """
        [p0, p1]
        guard_class(p0, ConstClass(node_vtable))
            fail()
        guard_class(p1, ConstClass(node_vtable2))
            fail()
        p2 = new_with_vtable(ConstClass(node_vtable2), descr=nodesize2)
        jump(p2, p2)
        """
        self.find_nodes(ops, 'Not, Fixed(node_vtable2)')

    def test_find_nodes_new_escapes(self):
        ops = """
        [p0]
        escape(p0)
        p1 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        jump(p1)
        """
        self.find_nodes(ops, 'Not')

    def test_find_nodes_new_unused(self):
        ops = """
        [p0]
        p1 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        p2 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        p3 = new_with_vtable(ConstClass(node_vtable), descr=nodesize)
        setfield_gc(p1, p2, descr=nextdescr)
        setfield_gc(p2, p3, descr=nextdescr)
        jump(p1)
        """
        self.find_nodes(ops, '''
            Virtual(node_vtable,
                    nextdescr=Virtual(node_vtable,
                                      nextdescr=Virtual(node_vtable)))''')

    # ------------------------------
    # Bridge tests

    def find_bridge(self, ops, inputspectext, outputspectext, boxkinds=None,
                    mismatch=False):
        inputspecnodes = self.unpack_specnodes(inputspectext)
        outputspecnodes = self.unpack_specnodes(outputspectext)
        bridge = self.parse(ops, boxkinds=boxkinds)
        bridge_specialization_finder = BridgeSpecializationFinder()
        bridge_specialization_finder.find_nodes_bridge(bridge, inputspecnodes)
        matches = bridge_specialization_finder.bridge_matches(
            bridge.operations[-1],
            outputspecnodes)
        if mismatch:
            assert not matches
        else:
            assert matches

    def test_bridge_simple(self):
        ops = """
        [i0]
        i1 = int_add(i0, 1)
        jump(i1)
        """
        self.find_bridge(ops, 'Not', 'Not')
        self.find_bridge(ops, 'Not', 'Virtual(node_vtable)', mismatch=True)

    def test_bridge_simple_known_class(self):
        ops = """
        [p0]
        setfield_gc(p0, 123, descr=valuedescr)
        jump(p0)
        """
        self.find_bridge(ops, 'Not', 'Not')
        self.find_bridge(ops, 'Fixed(node_vtable)', 'Not')
        self.find_bridge(ops, 'Fixed(node_vtable)', 'Fixed(node_vtable)')
        #
        self.find_bridge(ops, 'Not', 'Fixed(node_vtable)', mismatch=True)
        self.find_bridge(ops, 'Fixed(node_vtable)', 'Fixed(node_vtable2)',
                         mismatch=True)


class TestLLtype(BaseTestOptimize, LLtypeMixin):
    pass

class TestOOtype(BaseTestOptimize, OOtypeMixin):
    pass
