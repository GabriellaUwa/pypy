import py
from pypy.jit.metainterp.history import ResOperation, BoxInt, ConstInt,\
     BoxPtr, ConstPtr, TreeLoop
from pypy.jit.metainterp.resoperation import rop
from pypy.jit.backend.x86.runner import CPU

def test_bug_rshift():
    v1 = BoxInt()
    v2 = BoxInt()
    v3 = BoxInt()
    v4 = BoxInt()
    loop = TreeLoop('test')
    loop.inputargs = [v1]
    loop.operations = [
        ResOperation(rop.INT_ADD, [v1, v1], v2),
        ResOperation(rop.INT_INVERT, [v2], v3),
        ResOperation(rop.UINT_RSHIFT, [v1, ConstInt(3)], v4),
        ResOperation(rop.FAIL, [v4, v3], None),
        ]
    cpu = CPU(None, None)
    cpu.compile_operations(loop)
    cpu.execute_operations(loop, [BoxInt(9)])
    assert v4.value == (9 >> 3)
    assert v3.value == (~18)

def test_bug_int_is_true_1():
    v1 = BoxInt()
    v2 = BoxInt()
    v3 = BoxInt()
    v4 = BoxInt()
    tmp5 = BoxInt()
    loop = TreeLoop('test')
    loop.inputargs = [v1]
    loop.operations = [
        ResOperation(rop.INT_MUL, [v1, v1], v2),
        ResOperation(rop.INT_MUL, [v2, v1], v3),
        ResOperation(rop.INT_IS_TRUE, [v2], tmp5),
        ResOperation(rop.BOOL_NOT, [tmp5], v4),
        ResOperation(rop.FAIL, [v4, v3, tmp5], None),
            ]
    cpu = CPU(None, None)
    cpu.compile_operations(loop)
    cpu.execute_operations(loop, [BoxInt(-10)])
    assert tmp5.value == 1
    assert v4.value == 0
    assert v3.value == -1000

def test_bug_0():
    v1 = BoxInt()
    v2 = BoxInt()
    v3 = BoxInt()
    v4 = BoxInt()
    v5 = BoxInt()
    v6 = BoxInt()
    v7 = BoxInt()
    v8 = BoxInt()
    v9 = BoxInt()
    v10 = BoxInt()
    v11 = BoxInt()
    v12 = BoxInt()
    v13 = BoxInt()
    v14 = BoxInt()
    v15 = BoxInt()
    v16 = BoxInt()
    v17 = BoxInt()
    v18 = BoxInt()
    v19 = BoxInt()
    v20 = BoxInt()
    v21 = BoxInt()
    v22 = BoxInt()
    v23 = BoxInt()
    v24 = BoxInt()
    v25 = BoxInt()
    v26 = BoxInt()
    v27 = BoxInt()
    v28 = BoxInt()
    v29 = BoxInt()
    v30 = BoxInt()
    v31 = BoxInt()
    v32 = BoxInt()
    v33 = BoxInt()
    v34 = BoxInt()
    v35 = BoxInt()
    v36 = BoxInt()
    v37 = BoxInt()
    v38 = BoxInt()
    v39 = BoxInt()
    v40 = BoxInt()
    tmp41 = BoxInt()
    tmp42 = BoxInt()
    tmp43 = BoxInt()
    tmp44 = BoxInt()
    tmp45 = BoxInt()
    tmp46 = BoxInt()
    loop = TreeLoop('test')
    loop.inputargs = [v1, v2, v3, v4, v5, v6, v7, v8, v9, v10]
    loop.operations = [
        ResOperation(rop.UINT_GT, [v3, ConstInt(-48)], v11),
        ResOperation(rop.INT_XOR, [v8, v1], v12),
        ResOperation(rop.INT_GT, [v6, ConstInt(-9)], v13),
        ResOperation(rop.INT_LE, [v13, v2], v14),
        ResOperation(rop.INT_LE, [v11, v5], v15),
        ResOperation(rop.UINT_GE, [v13, v13], v16),
        ResOperation(rop.INT_OR, [v9, ConstInt(-23)], v17),
        ResOperation(rop.INT_LT, [v10, v13], v18),
        ResOperation(rop.INT_OR, [v15, v5], v19),
        ResOperation(rop.INT_XOR, [v17, ConstInt(54)], v20),
        ResOperation(rop.INT_MUL, [v8, v10], v21),
        ResOperation(rop.INT_OR, [v3, v9], v22),
        ResOperation(rop.INT_AND, [v11, ConstInt(-4)], tmp41),
        ResOperation(rop.INT_OR, [tmp41, ConstInt(1)], tmp42),
        ResOperation(rop.INT_MOD, [v12, tmp42], v23),
        ResOperation(rop.INT_IS_TRUE, [v6], v24),
        ResOperation(rop.UINT_RSHIFT, [v15, ConstInt(6)], v25),
        ResOperation(rop.INT_OR, [ConstInt(-4), v25], v26),
        ResOperation(rop.INT_INVERT, [v8], v27),
        ResOperation(rop.INT_SUB, [ConstInt(-113), v11], v28),
        ResOperation(rop.INT_ABS, [v7], v29),
        ResOperation(rop.INT_NEG, [v24], v30),
        ResOperation(rop.INT_FLOORDIV, [v3, ConstInt(53)], v31),
        ResOperation(rop.INT_MUL, [v28, v27], v32),
        ResOperation(rop.INT_AND, [v18, ConstInt(-4)], tmp43),
        ResOperation(rop.INT_OR, [tmp43, ConstInt(1)], tmp44),
        ResOperation(rop.INT_MOD, [v26, tmp44], v33),
        ResOperation(rop.INT_OR, [v27, v19], v34),
        ResOperation(rop.UINT_LT, [v13, ConstInt(1)], v35),
        ResOperation(rop.INT_AND, [v21, ConstInt(31)], tmp45),
        ResOperation(rop.INT_RSHIFT, [v21, tmp45], v36),
        ResOperation(rop.INT_AND, [v20, ConstInt(31)], tmp46),
        ResOperation(rop.UINT_RSHIFT, [v4, tmp46], v37),
        ResOperation(rop.UINT_GT, [v33, ConstInt(-11)], v38),
        ResOperation(rop.INT_NEG, [v7], v39),
        ResOperation(rop.INT_GT, [v24, v32], v40),
        ResOperation(rop.FAIL, [v40, v36, v37, v31, v16, v34, v35, v23, v22, v29, v14, v39, v30, v38], None),
            ]
    cpu = CPU(None, None)
    cpu.compile_operations(loop)
    cpu.execute_operations(loop, [BoxInt(-13), BoxInt(10), BoxInt(10), BoxInt(8), BoxInt(-8), BoxInt(-16), BoxInt(-18), BoxInt(46), BoxInt(-12), BoxInt(26)])
    assert v40.value == 0
    assert v36.value == 0
    assert v37.value == 0
    assert v31.value == 0
    assert v16.value == 1
    assert v34.value == -7
    assert v35.value == 1
    assert v23.value == 0
    assert v22.value == -2
    assert v29.value == 18
    assert v14.value == 1
    assert v39.value == 18
    assert v30.value == -1
    assert v38.value == 0

def test_bug_1():
    v1 = BoxInt()
    v2 = BoxInt()
    v3 = BoxInt()
    v4 = BoxInt()
    v5 = BoxInt()
    v6 = BoxInt()
    v7 = BoxInt()
    v8 = BoxInt()
    v9 = BoxInt()
    v10 = BoxInt()
    v11 = BoxInt()
    v12 = BoxInt()
    v13 = BoxInt()
    v14 = BoxInt()
    v15 = BoxInt()
    v16 = BoxInt()
    v17 = BoxInt()
    v18 = BoxInt()
    v19 = BoxInt()
    v20 = BoxInt()
    v21 = BoxInt()
    v22 = BoxInt()
    v23 = BoxInt()
    v24 = BoxInt()
    v25 = BoxInt()
    v26 = BoxInt()
    v27 = BoxInt()
    v28 = BoxInt()
    v29 = BoxInt()
    v30 = BoxInt()
    v31 = BoxInt()
    v32 = BoxInt()
    v33 = BoxInt()
    v34 = BoxInt()
    v35 = BoxInt()
    v36 = BoxInt()
    v37 = BoxInt()
    v38 = BoxInt()
    v39 = BoxInt()
    v40 = BoxInt()
    tmp41 = BoxInt()
    tmp42 = BoxInt()
    tmp43 = BoxInt()
    tmp44 = BoxInt()
    tmp45 = BoxInt()
    loop = TreeLoop('test')
    loop.inputargs = [v1, v2, v3, v4, v5, v6, v7, v8, v9, v10]
    loop.operations = [
        ResOperation(rop.UINT_LT, [v6, ConstInt(0)], v11),
        ResOperation(rop.INT_AND, [v3, ConstInt(31)], tmp41),
        ResOperation(rop.INT_RSHIFT, [v3, tmp41], v12),
        ResOperation(rop.INT_NEG, [v2], v13),
        ResOperation(rop.INT_ADD, [v11, v7], v14),
        ResOperation(rop.INT_OR, [v3, v2], v15),
        ResOperation(rop.INT_OR, [v12, v12], v16),
        ResOperation(rop.INT_NE, [v2, v5], v17),
        ResOperation(rop.INT_AND, [v5, ConstInt(31)], tmp42),
        ResOperation(rop.UINT_RSHIFT, [v14, tmp42], v18),
        ResOperation(rop.INT_AND, [v14, ConstInt(31)], tmp43),
        ResOperation(rop.INT_LSHIFT, [ConstInt(7), tmp43], v19),
        ResOperation(rop.INT_ABS, [v19], v20),
        ResOperation(rop.INT_MOD, [v3, ConstInt(1)], v21),
        ResOperation(rop.UINT_GE, [v15, v1], v22),
        ResOperation(rop.INT_AND, [v16, ConstInt(31)], tmp44),
        ResOperation(rop.INT_LSHIFT, [v8, tmp44], v23),
        ResOperation(rop.INT_IS_TRUE, [v17], v24),
        ResOperation(rop.INT_AND, [v5, ConstInt(31)], tmp45),
        ResOperation(rop.INT_LSHIFT, [v14, tmp45], v25),
        ResOperation(rop.INT_LSHIFT, [v5, ConstInt(17)], v26),
        ResOperation(rop.INT_EQ, [v9, v15], v27),
        ResOperation(rop.INT_GE, [ConstInt(0), v6], v28),
        ResOperation(rop.INT_NEG, [v15], v29),
        ResOperation(rop.INT_ABS, [v22], v30),
        ResOperation(rop.INT_ADD, [v7, v16], v31),
        ResOperation(rop.UINT_LT, [v19, v19], v32),
        ResOperation(rop.INT_ADD, [v2, ConstInt(1)], v33),
        ResOperation(rop.INT_ABS, [v5], v34),
        ResOperation(rop.INT_ADD, [v17, v24], v35),
        ResOperation(rop.UINT_LT, [ConstInt(2), v16], v36),
        ResOperation(rop.INT_ABS, [v9], v37),
        ResOperation(rop.INT_GT, [v4, v11], v38),
        ResOperation(rop.INT_LT, [v27, v22], v39),
        ResOperation(rop.INT_ABS, [v27], v40),
        ResOperation(rop.FAIL, [v40, v10, v36, v26, v13, v30, v21, v33, v18, v25, v31, v32, v28, v29, v35, v38, v20, v39, v34, v23, v37], None),
            ]
    cpu = CPU(None, None)
    cpu.compile_operations(loop)
    cpu.execute_operations(loop, [BoxInt(17), BoxInt(-20), BoxInt(-6), BoxInt(6), BoxInt(1), BoxInt(13), BoxInt(13), BoxInt(9), BoxInt(49), BoxInt(8)])
    assert v40.value == 0
    assert v10.value == 8
    assert v36.value == 1
    assert v26.value == 131072
    assert v13.value == 20
    assert v30.value == 1
    assert v21.value == 0
    assert v33.value == -19
    assert v18.value == 6
    assert v25.value == 26
    assert v31.value == 12
    assert v32.value == 0
    assert v28.value == 0
    assert v29.value == 2
    assert v35.value == 2
    assert v38.value == 1
    assert v20.value == 57344
    assert v39.value == 1
    assert v34.value == 1
    assert v23.value == -2147483648
    assert v37.value == 49
