from pypy.rlib.rarithmetic import intmask
from pypy.rlib.unroll import unrolling_iterable
from pypy.rlib.objectmodel import we_are_translated, CDefinedIntSymbolic
from pypy.rpython.lltypesystem import lltype, llmemory, lloperation
from pypy.rpython.annlowlevel import cast_base_ptr_to_instance
from pypy.jit.timeshifter import rvalue
from pypy.jit.timeshifter.greenkey import empty_key, GreenKey
from pypy.jit.rainbow.interpreter import SIGN_EXTEND2, arguments


class FallbackInterpreter(object):
    """
    The fallback interp takes an existing suspended jitstate and
    actual values for the live red vars, and interprets the jitcode
    normally until it reaches the 'jit_merge_point' or raises.
    """
    def __init__(self, hotrunnerdesc):
        self.hotrunnerdesc = hotrunnerdesc
        self.interpreter = hotrunnerdesc.interpreter
        self.rgenop = self.interpreter.rgenop
        self.exceptiondesc = hotrunnerdesc.exceptiondesc
        self.register_opcode_impls(self.interpreter)

    def initialize_state(self, fallback_point, framebase):
        self.interpreter.debug_trace("fallback_interp")
        jitstate = fallback_point.saved_jitstate
        incoming_gv = jitstate.get_locals_gv()
        self.framebase = framebase
        self.frameinfo = fallback_point.frameinfo
        self.containers_gv = {}
        self.gv_to_index = {}
        for i in range(len(incoming_gv)):
            self.gv_to_index[incoming_gv[i]] = i

        self.initialize_from_frame(jitstate.frame)
        self.gv_exc_type  = self.getinitialboxgv(jitstate.exc_type_box)
        self.gv_exc_value = self.getinitialboxgv(jitstate.exc_value_box)
        self.seen_can_enter_jit = False

    def getinitialboxgv(self, box):
        gv = box.genvar
        if gv is None:
            return self.build_gv_container(box)
        if not gv.is_const:
            # fetch the value from the machine code stack
            gv = self.rgenop.genconst_from_frame_var(box.kind, self.framebase,
                                                     self.frameinfo,
                                                     self.gv_to_index[gv])
        return gv

    def build_gv_container(self, box):
        # allocate a real structure on the heap mirroring the virtual
        # container of the box
        assert isinstance(box, rvalue.PtrRedBox)
        content = box.content
        assert content is not None
        try:
            return self.containers_gv[content]
        except KeyError:
            gv_result = content.allocate_gv_container(self.rgenop)
            self.containers_gv[content] = gv_result
            content.populate_gv_container(gv_result, self.getinitialboxgv)
            return gv_result

    def initialize_from_frame(self, frame):
        # note that both local_green and local_red contain GenConsts
        self.current_source_jitframe = frame
        self.pc = frame.pc
        self.bytecode = frame.bytecode
        self.local_green = frame.local_green[:]
        self.local_red = []
        for box in frame.local_boxes:
            self.local_red.append(self.getinitialboxgv(box))

    def capture_exception(self, e):
        if not we_are_translated():
            from pypy.rpython.llinterp import LLException
            if not isinstance(e, LLException):
                raise      # don't know how to capture it, and it
                           # probably shows a bug anyway
            llexctype, llvalue = e.args
            self.gv_exc_type  = self.rgenop.genconst(llexctype)
            self.gv_exc_value = self.rgenop.genconst(llvalue)
        else:
            Xxx("capture_exception")

    def run_directly(self, greenargs, redargs, targetbytecode):
        calldesc = targetbytecode.owncalldesc
        try:
            gv_res = calldesc.perform_call_mixed(self.rgenop,
                                                 targetbytecode.gv_ownfnptr,
                                                 greenargs, redargs)
        except Exception, e:
            self.capture_exception(e)
            gv_res = calldesc.gv_whatever_return_value
        return gv_res

    def oopspec_call(self, oopspec, arglist):
        try:
            return oopspec.do_call(self.rgenop, arglist)
        except Exception, e:
            self.capture_exception(e)
            return oopspec.gv_whatever_return_value

    def leave_fallback_interp(self, gv_result):
        # at this point we might have an exception set in self.gv_exc_xxx
        # and we have to really raise it.
        exceptiondesc = self.exceptiondesc
        llvalue = self.gv_exc_value.revealconst(exceptiondesc.LL_EXC_VALUE)
        if llvalue:
            if we_are_translated():
                exception = cast_base_ptr_to_instance(Exception, llvalue)
                self.interpreter.debug_trace("fb_raise", str(exception))
                raise Exception, exception
            # non-translatable hack follows...
            from pypy.rpython.llinterp import LLException, type_name
            llexctype = self.gv_exc_type.revealconst(exceptiondesc.LL_EXC_TYPE)
            assert llexctype and llvalue
            self.interpreter.debug_trace("fb_raise", type_name(llexctype))
            raise LLException(llexctype, llvalue)
        else:
            ARG = self.hotrunnerdesc.RAISE_DONE_FUNCPTR.TO.ARGS[0]
            if ARG is not lltype.Void:
                result = gv_result.revealconst(ARG)
            else:
                result = None
            self.interpreter.debug_trace("fb_return", result)
            DoneWithThisFrame = self.hotrunnerdesc.DoneWithThisFrame
            raise DoneWithThisFrame(result)

    # ____________________________________________________________
    # XXX Lots of copy and paste from interp.py!

    def bytecode_loop(self):
        while 1:
            bytecode = self.load_2byte()
            assert bytecode >= 0
            result = self.opcode_implementations[bytecode](self)

    # operation helper functions
    def getjitcode(self):
        return self.bytecode

    def load_byte(self):
        pc = self.pc
        assert pc >= 0
        result = ord(self.bytecode.code[pc])
        self.pc = pc + 1
        return result

    def load_2byte(self):
        pc = self.pc
        assert pc >= 0
        result = ((ord(self.bytecode.code[pc]) << 8) |
                   ord(self.bytecode.code[pc + 1]))
        self.pc = pc + 2
        return intmask((result ^ SIGN_EXTEND2) - SIGN_EXTEND2)

    def load_4byte(self):
        pc = self.pc
        assert pc >= 0
        result = ((ord(self.bytecode.code[pc + 0]) << 24) |
                  (ord(self.bytecode.code[pc + 1]) << 16) |
                  (ord(self.bytecode.code[pc + 2]) <<  8) |
                  (ord(self.bytecode.code[pc + 3]) <<  0))
        self.pc = pc + 4
        return intmask(result)

    def load_bool(self):
        return bool(self.load_byte())

    def get_greenarg(self):
        i = self.load_2byte()
        if i < 0:
            return self.bytecode.constants[~i]
        return self.local_green[i]

    def get_green_varargs(self):
        greenargs = []
        num = self.load_2byte()
        for i in range(num):
            greenargs.append(self.get_greenarg())
        return greenargs

    def get_red_varargs(self):
        redargs = []
        num = self.load_2byte()
        for i in range(num):
            redargs.append(self.get_redarg())
        return redargs

    def get_redarg(self):
        return self.local_red[self.load_2byte()]

    def get_greenkey(self):
        keydescnum = self.load_2byte()
        if keydescnum == -1:
            return empty_key
        else:
            keydesc = self.bytecode.keydescs[keydescnum]
            return GreenKey(self.local_green[:keydesc.nb_vals], keydesc)

    def red_result(self, gv):
        assert gv.is_const
        self.local_red.append(gv)

    def green_result(self, gv):
        assert gv.is_const
        self.local_green.append(gv)

    def green_result_from_red(self, gv):
        self.green_result(gv)

    def trace(self):
        bytecode = self.bytecode
        msg = '*** fallback trace: in %s position %d ***' % (bytecode.name,
                                                             self.pc)
        print msg
        if bytecode.dump_copy is not None:
            print bytecode.dump_copy
        return msg

    # ____________________________________________________________
    # Operation implementations

    @arguments()
    def opimpl_trace(self):
        msg = self.trace()
        self.interpreter.debug_trace(msg)

    @arguments("green", "2byte", returns="red")
    def opimpl_make_redbox(self, genconst, typeid):
        return genconst

    @arguments("red", returns="green_from_red")
    def opimpl_revealconst(self, gv_value):
        return gv_value

    @arguments("jumptarget")
    def opimpl_goto(self, target):
        self.pc = target

    @arguments("green", "jumptarget")
    def opimpl_green_goto_iftrue(self, genconst, target):
        if genconst.revealconst(lltype.Bool):
            self.pc = target

    @arguments("green", "green_varargs", "jumptargets")
    def opimpl_green_switch(self, exitcase, cases, targets):
        arg = exitcase.revealconst(lltype.Signed)
        assert len(cases) == len(targets)
        for i in range(len(cases)):
            if arg == cases[i].revealconst(lltype.Signed):
                self.pc = targets[i]
                break

    @arguments("bool", "red", "red", "jumptarget")
    def opimpl_red_goto_ifptrnonzero(self, reverse, gv_ptr, gv_switch, target):
        Xxx("red_goto_ifptrnonzero")

    @arguments("red", "jumptarget")
    def opimpl_goto_if_constant(self, gv_value, target):
        Xxx("goto_if_constant")


    @arguments("red", returns="red")
    def opimpl_red_ptr_nonzero(self, gv_ptr):
        addr = gv_ptr.revealconst(llmemory.Address)
        return self.rgenop.genconst(bool(addr))

    @arguments("red", returns="red")
    def opimpl_red_ptr_iszero(self, gv_ptr):
        addr = gv_ptr.revealconst(llmemory.Address)
        return self.rgenop.genconst(not addr)

    @arguments("red", "red", returns="red")
    def opimpl_red_ptr_eq(self, gv_ptr1, gv_ptr2):
        Xxx("red_ptr_eq")

    @arguments("red", "red", returns="red")
    def opimpl_red_ptr_ne(self, gv_ptr1, gv_ptr2):
        Xxx("red_ptr_ne")


    @arguments("red_varargs")
    def opimpl_make_new_redvars(self, local_red):
        self.local_red = local_red

    def opimpl_make_new_greenvars(self):
        # this uses a "green_varargs" argument, but we do the decoding
        # manually for the fast case
        num = self.load_2byte()
        if num == 0 and len(self.local_green) == 0:
            # fast (very common) case
            return
        newgreens = []
        for i in range(num):
            newgreens.append(self.get_greenarg())
        self.local_green = newgreens
    opimpl_make_new_greenvars.argspec = arguments("green_varargs")

    @arguments("green", "calldesc", "green_varargs")
    def opimpl_green_call(self, gv_fnptr, calldesc, greenargs):
        gv_res = calldesc.perform_call(self.rgenop, gv_fnptr, greenargs)
        self.green_result(gv_res)

    @arguments("green_varargs", "red_varargs", "red", "indirectcalldesc")
    def opimpl_indirect_call_const(self, greenargs, redargs,
                                      gv_funcptr, callset):
        Xxx("indirect_call_const")

    @arguments("oopspec", "bool", returns="red")
    def opimpl_red_oopspec_call_0(self, oopspec, deepfrozen):
        return self.oopspec_call(oopspec, [])

    @arguments("oopspec", "bool", "red", returns="red")
    def opimpl_red_oopspec_call_1(self, oopspec, deepfrozen, arg1):
        return self.oopspec_call(oopspec, [arg1])

    @arguments("oopspec", "bool", "red", "red", returns="red")
    def opimpl_red_oopspec_call_2(self, oopspec, deepfrozen, arg1, arg2):
        return self.oopspec_call(oopspec, [arg1, arg2])

    @arguments("oopspec", "bool", "red", "red", "red", returns="red")
    def opimpl_red_oopspec_call_3(self, oopspec, deepfrozen, arg1, arg2, arg3):
        return self.oopspec_call(oopspec, [arg1, arg2, arg3])

    @arguments("oopspec", "bool")
    def opimpl_red_oopspec_call_noresult_0(self, oopspec, deepfrozen):
        self.oopspec_call(oopspec, [])

    @arguments("oopspec", "bool", "red")
    def opimpl_red_oopspec_call_noresult_1(self, oopspec, deepfrozen, arg1):
        self.oopspec_call(oopspec, [arg1])

    @arguments("oopspec", "bool", "red", "red")
    def opimpl_red_oopspec_call_noresult_2(self, oopspec, deepfrozen, arg1, arg2):
        self.oopspec_call(oopspec, [arg1, arg2])

    @arguments("oopspec", "bool", "red", "red", "red")
    def opimpl_red_oopspec_call_noresult_3(self, oopspec, deepfrozen, arg1, arg2, arg3):
        self.oopspec_call(oopspec, [arg1, arg2, arg3])

    @arguments("metacalldesc", "red_varargs", returns="red")
    def opimpl_metacall(self, metafunc, redargs):
        Xxx("metacall")

    # exceptions

    @arguments(returns="red")
    def opimpl_read_exctype(self):
        return self.gv_exc_type

    @arguments(returns="red")
    def opimpl_read_excvalue(self):
        return self.gv_exc_value

    @arguments("red")
    def opimpl_write_exctype(self, gv_type):
        self.gv_exc_type = gv_type

    @arguments("red")
    def opimpl_write_excvalue(self, gv_value):
        self.gv_exc_value = gv_value

    @arguments("red", "red")
    def opimpl_setexception(self, gv_type, gv_value):
        self.gv_exc_type  = gv_type
        self.gv_exc_value = gv_value

    # structs and arrays

    @arguments("structtypedesc", returns="red")
    def opimpl_red_malloc(self, structtypedesc):
        return structtypedesc.allocate(self.rgenop)

    @arguments("structtypedesc", "red", returns="red")
    def opimpl_red_malloc_varsize_struct(self, structtypedesc, gv_size):
        Xxx("red_malloc_varsize_struct")

    @arguments("arraydesc", "red", returns="red")
    def opimpl_red_malloc_varsize_array(self, arraytypedesc, gv_size):
        Xxx("red_malloc_varsize_array")

    @arguments("red", "fielddesc", "bool", returns="red")
    def opimpl_red_getfield(self, gv_struct, fielddesc, deepfrozen):
        gv_res = fielddesc.getfield_if_non_null(self.rgenop, gv_struct)
        assert gv_res is not None, "segfault!"
        return gv_res

    @arguments("red", "fielddesc", "bool", returns="green_from_red")
    def opimpl_green_getfield(self, gv_struct, fielddesc, deepfrozen):
        gv_res = fielddesc.getfield_if_non_null(self.rgenop, gv_struct)
        assert gv_res is not None, "segfault!"
        return gv_res

    @arguments("red", "fielddesc", "red")
    def opimpl_red_setfield(self, gv_dest, fielddesc, gv_value):
        fielddesc.setfield(self.rgenop, gv_dest, gv_value)

    @arguments("red", "arraydesc", "red", "bool", returns="red")
    def opimpl_red_getarrayitem(self, gv_array, fielddesc, gv_index, deepfrozen):
        Xxx("red_getarrayitem")

    @arguments("red", "arraydesc", "red", "red")
    def opimpl_red_setarrayitem(self, gv_dest, fielddesc, gv_index, gv_value):
        Xxx("red_setarrayitem")

    @arguments("red", "arraydesc", returns="red")
    def opimpl_red_getarraysize(self, gv_array, fielddesc):
        Xxx("red_getarraysize")

    @arguments("red", "arraydesc", returns="green_from_red")
    def opimpl_green_getarraysize(self, gv_array, fielddesc):
        Xxx("green_getarraysize")

    @arguments("red", "interiordesc", "bool", "red_varargs", returns="red")
    def opimpl_red_getinteriorfield(self, gv_struct, interiordesc, deepfrozen,
                                    indexes_gv):
        Xxx("red_getinteriorfield")

    @arguments("red", "interiordesc", "bool", "red_varargs",
               returns="green_from_red")
    def opimpl_green_getinteriorfield(self, gv_struct, interiordesc, deepfrozen,
                                      indexes_gv):
        Xxx("green_getinteriorfield")

    @arguments("red", "interiordesc", "red_varargs", "red")
    def opimpl_red_setinteriorfield(self, gv_dest, interiordesc, indexes_gv,
                                    gv_value):
        Xxx("red_setinteriorfield")

    @arguments("red", "interiordesc", "red_varargs", returns="red")
    def opimpl_red_getinteriorarraysize(self, gv_array, interiordesc, indexes_gv):
        Xxx("red_getinteriorarraysize")

    @arguments("red", "interiordesc", "red_varargs", returns="green_from_red")
    def opimpl_green_getinteriorarraysize(self, gv_array, interiordesc,
                                          indexes_gv):
        Xxx("green_getinteriorarraysize")

    @arguments("red", "green", "green", returns="green")
    def opimpl_is_constant(self, arg, true, false):
        Xxx("is_constant")

    # hotpath-specific operations

    @arguments("greenkey")
    def opimpl_jit_merge_point(self, key):
        ContinueRunningNormally = self.hotrunnerdesc.ContinueRunningNormally
        raise ContinueRunningNormally(self.local_green + self.local_red,
                                      self.seen_can_enter_jit)

    @arguments()
    def opimpl_can_enter_jit(self):
        self.seen_can_enter_jit = True

    @arguments("red", "jumptarget")
    def opimpl_hp_red_goto_iftrue(self, gv_switch, target):
        if gv_switch.revealconst(lltype.Bool):
            self.pc = target

    @arguments("red", "promotiondesc")
    def opimpl_hp_promote(self, gv_promote, promotiondesc):
        self.green_result(gv_promote)

    @arguments("green_varargs", "red_varargs", "bytecode")
    def opimpl_hp_red_direct_call(self, greenargs, redargs, targetbytecode):
        gv_res = self.run_directly(greenargs, redargs, targetbytecode)
        self.red_result(gv_res)

    @arguments("green_varargs", "red_varargs", "bytecode")
    def opimpl_hp_gray_direct_call(self, greenargs, redargs, targetbytecode):
        gv_res = self.run_directly(greenargs, redargs, targetbytecode)
        assert gv_res is None

    @arguments("green_varargs", "red_varargs", "bytecode")
    def opimpl_hp_yellow_direct_call(self, greenargs, redargs, targetbytecode):
        gv_res = self.run_directly(greenargs, redargs, targetbytecode)
        self.green_result(gv_res)

    @arguments("red", "calldesc", "bool", "bool", "red_varargs")
    def opimpl_hp_residual_call(self, gv_func, calldesc, withexc, has_result,
                                redargs_gv):
        try:
            gv_res = calldesc.perform_call(self.rgenop, gv_func, redargs_gv)
        except Exception, e:
            self.capture_exception(e)
            gv_res = calldesc.gv_whatever_return_value
        if has_result:
            self.red_result(gv_res)

    def hp_return(self):
        frame = self.current_source_jitframe.backframe
        if frame is None:
            return True
        else:
            self.initialize_from_frame(frame)
            return False

    @arguments()
    def opimpl_hp_gray_return(self):
        if self.hp_return():
            self.leave_fallback_interp(None)

    @arguments()
    def opimpl_hp_red_return(self):
        gv_result = self.local_red[0]
        if self.hp_return():
            self.leave_fallback_interp(gv_result)
        else:
            self.red_result(gv_result)

    @arguments()
    def opimpl_hp_yellow_return(self):
        gv_result = self.local_green[0]
        if self.hp_return():
            self.leave_fallback_interp(gv_result)
        else:
            self.green_result(gv_result)

    # ____________________________________________________________
    # construction-time helpers

    def register_opcode_impls(self, interp):
        impl = [None] * len(interp.opcode_implementations)
        for opname, index in interp.opname_to_index.items():
            argspec = interp.opcode_implementations[index].argspec
            name = 'opimpl_' + opname
            if hasattr(self, name):
                fbopimpl = getattr(self, name).im_func
                assert fbopimpl.argspec == argspec
            else:
                opdesc = interp.opcode_descs[index]
                if opdesc is None:
                    raise Exception("no fallback interpreter support for %r" %
                                    (opname,))
                fbopimpl = self.get_opcode_implementation(name, argspec,
                                                          opdesc)
            impl[index] = fbopimpl
        self.opcode_implementations = impl

    def get_opcode_implementation(self, func_name, argspec, opdesc):
        numargs = unrolling_iterable(range(opdesc.nb_args))
        def implementation(self, *args_gv):
            args = (opdesc.RESULT, )
            for i in numargs:
                arg = args_gv[i].revealconst(opdesc.ARGS[i])
                args += (arg, )
            if not we_are_translated():
                if opdesc.opname == "int_is_true":
                    # special case for tests, as in llinterp.py
                    if type(args[1]) is CDefinedIntSymbolic:
                        args = (args[0], args[1].default)
            return self.rgenop.genconst(opdesc.llop(*args))
        implementation.func_name = func_name
        # the argspec may unwrap *args_gv from local_red or local_green
        # and put the result back into local_red or local_green
        return argspec(implementation)


def Xxx(msg):
    lloperation.llop.debug_fatalerror(lltype.Void, "not implemented: " + msg)
    assert 0
