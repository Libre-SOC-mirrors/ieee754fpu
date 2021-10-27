# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

import unittest
import math
from ieee754.part.util import FpElWid, IntElWid, SimdMap, SimdWHintMap


class TestElWid(unittest.TestCase):
    def test_repr(self):
        self.assertEqual(repr(FpElWid.F64), "FpElWid.F64")
        self.assertEqual(repr(IntElWid.I8), "IntElWid.I8")


class TestSimdMap(unittest.TestCase):
    def test_extract_value(self):
        self.assertEqual(SimdMap.extract_value(IntElWid.I8, None), None)
        self.assertEqual(SimdMap.extract_value(IntElWid.I8, None, 5), 5)
        self.assertEqual(SimdMap.extract_value(IntElWid.I8, 3, 5), 3)
        self.assertEqual(SimdMap.extract_value(IntElWid.I8,
                                               {FpElWid.F64: 3}, 5), 5)
        self.assertEqual(SimdMap.extract_value(IntElWid.I8,
                                               {FpElWid.F64: 3}), None)
        self.assertEqual(SimdMap.extract_value(FpElWid.F16,
                                               {FpElWid.F64: 3}), None)
        self.assertEqual(SimdMap.extract_value(FpElWid.F64,
                                               {FpElWid.F64: 3}), 3)
        self.assertEqual(SimdMap.extract_value(FpElWid.F64,
                                               {FpElWid.F64: None}, 5), 5)
        self.assertEqual(SimdMap.extract_value(FpElWid.F64,
                                               {FpElWid.F64: None}), None)
        self.assertEqual(SimdMap.extract_value(
            FpElWid.F64, {FpElWid.F64: {FpElWid.F64: 5}}), 5)
        self.assertEqual(SimdMap.extract_value(
            FpElWid.F64, {FpElWid.F64: {FpElWid.F32: 5}}), None)
        simd_map = SimdMap({IntElWid.I8: 3, FpElWid.F64: 5})
        self.assertEqual(SimdMap.extract_value(
            FpElWid.F64, simd_map), 5)
        self.assertEqual(SimdMap.extract_value(
            FpElWid.F32, simd_map), None)
        self.assertEqual(SimdMap.extract_value(
            IntElWid.I8, simd_map), 3)
        with self.assertRaisesRegex(
                AssertionError, "can't resolve infinitely recursive value"):
            m = {}
            m[IntElWid.I32] = m
            SimdMap.extract_value(IntElWid.I32, m)

    def test_init(self):
        self.assertEqual(repr(SimdMap(0).mapping),
                         "mappingproxy({FpElWid.F64: 0, FpElWid.F32: 0, "
                         "FpElWid.F16: 0, FpElWid.BF16: 0, IntElWid.I64: 0, "
                         "IntElWid.I32: 0, IntElWid.I16: 0, IntElWid.I8: 0})")
        self.assertEqual(repr(SimdMap(None).mapping), "mappingproxy({})")
        self.assertEqual(repr(SimdMap().mapping), "mappingproxy({})")
        self.assertEqual(repr(SimdMap({FpElWid.F64: 5,
                                       IntElWid.I8: 10}).mapping),
                         "mappingproxy({FpElWid.F64: 5, IntElWid.I8: 10})")
        self.assertEqual(repr(SimdMap(SimdMap({FpElWid.F64: 5,
                                               IntElWid.I8: 10})).mapping),
                         "mappingproxy({FpElWid.F64: 5, IntElWid.I8: 10})")

    def test_values(self):
        self.assertEqual(repr(SimdMap({FpElWid.F64: 5,
                                       IntElWid.I8: 10}).values()),
                         "dict_values([5, 10])")

    def test_keys(self):
        self.assertEqual(repr(SimdMap({FpElWid.F64: 5,
                                       IntElWid.I8: 10}).keys()),
                         "dict_keys([FpElWid.F64, IntElWid.I8])")

    def test_items(self):
        self.assertEqual(repr(SimdMap({FpElWid.F64: 5,
                                       IntElWid.I8: 10}).items()),
                         "dict_items([(FpElWid.F64, 5), (IntElWid.I8, 10)])")

    def test_map_and_map_with_elwid(self):
        def case(*args, expected, expected_args):
            calls = []

            def callback(*args):
                calls.append(args)
                return len(calls)

            self.assertEqual(repr(SimdMap.map_with_elwid(callback, *args)),
                             repr(SimdMap(expected)))
            self.assertEqual(calls, expected_args)

            calls = []
            expected_args = [tuple(i[1:]) for i in expected_args]

            self.assertEqual(repr(SimdMap.map(callback, *args)),
                             repr(SimdMap(expected)))
            self.assertEqual(calls, expected_args)

        case(expected={
            FpElWid.F64: 1, FpElWid.F32: 2, FpElWid.F16: 3, FpElWid.BF16: 4,
            IntElWid.I64: 5, IntElWid.I32: 6, IntElWid.I16: 7, IntElWid.I8: 8,
        }, expected_args=[
            (FpElWid.F64,), (FpElWid.F32,), (FpElWid.F16,), (FpElWid.BF16,),
            (IntElWid.I64,), (IntElWid.I32,), (IntElWid.I16,), (IntElWid.I8,),
        ])

        case(None, expected={}, expected_args=[])
        case(1, expected={
            FpElWid.F64: 1, FpElWid.F32: 2, FpElWid.F16: 3, FpElWid.BF16: 4,
            IntElWid.I64: 5, IntElWid.I32: 6, IntElWid.I16: 7, IntElWid.I8: 8,
        }, expected_args=[
            (FpElWid.F64, 1), (FpElWid.F32, 1),
            (FpElWid.F16, 1), (FpElWid.BF16, 1),
            (IntElWid.I64, 1), (IntElWid.I32, 1),
            (IntElWid.I16, 1), (IntElWid.I8, 1),
        ])
        case(1, 5, expected={
            FpElWid.F64: 1, FpElWid.F32: 2, FpElWid.F16: 3, FpElWid.BF16: 4,
            IntElWid.I64: 5, IntElWid.I32: 6, IntElWid.I16: 7, IntElWid.I8: 8,
        }, expected_args=[
            (FpElWid.F64, 1, 5), (FpElWid.F32, 1, 5),
            (FpElWid.F16, 1, 5), (FpElWid.BF16, 1, 5),
            (IntElWid.I64, 1, 5), (IntElWid.I32, 1, 5),
            (IntElWid.I16, 1, 5), (IntElWid.I8, 1, 5),
        ])
        case({FpElWid.F64: 1, IntElWid.I8: 3, FpElWid.F32: 5}, 5, expected={
            FpElWid.F64: 1, FpElWid.F32: 2, IntElWid.I8: 3,
        }, expected_args=[
            (FpElWid.F64, 1, 5), (FpElWid.F32, 5, 5), (IntElWid.I8, 3, 5),
        ])
        case({FpElWid.F64: 1, IntElWid.I8: 3},
             {FpElWid.F64: 5, IntElWid.I8: 7},
             expected={FpElWid.F64: 1, IntElWid.I8: 2},
             expected_args=[(FpElWid.F64, 1, 5), (IntElWid.I8, 3, 7)])
        case(SimdMap({FpElWid.F64: 1, IntElWid.I8: 3}),
             SimdMap({FpElWid.F64: 5, IntElWid.I8: 7}),
             expected={FpElWid.F64: 1, IntElWid.I8: 2},
             expected_args=[(FpElWid.F64, 1, 5), (IntElWid.I8, 3, 7)])

    def test_get(self):
        v = SimdMap({FpElWid.F64: 1, IntElWid.I8: 3})
        self.assertEqual(v.get(IntElWid.I8), 3)
        self.assertEqual(v.get(IntElWid.I16), None)
        self.assertEqual(v.get(FpElWid.F64), 1)
        self.assertEqual(v.get(IntElWid.I16, default="blah"), "blah")
        self.assertEqual(v.get(FpElWid.F64, default="blah"), 1)
        with self.assertRaises(KeyError):
            v.get(IntElWid.I16, raise_key_error=True)

    def test_iter(self):
        self.assertEqual(list(SimdMap({FpElWid.F64: 5,
                                       IntElWid.I8: 10})),
                         [(FpElWid.F64, 5), (IntElWid.I8, 10)])

    def test_ops(self):
        a = SimdMap({FpElWid.F64: 5, IntElWid.I8: 10})
        b = SimdMap({FpElWid.F64: "abc", IntElWid.I8: "def"})
        c = SimdMap({FpElWid.F64: -5, IntElWid.I8: 10})
        d = SimdMap({FpElWid.F64: -3.5, IntElWid.I8: 10.5})
        # add
        self.assertEqual(a + 20,
                         SimdMap({FpElWid.F64: 25, IntElWid.I8: 30}))
        self.assertEqual(20 + a,
                         SimdMap({FpElWid.F64: 25, IntElWid.I8: 30}))
        self.assertEqual(b + "ghi",
                         SimdMap({FpElWid.F64: "abcghi",
                                  IntElWid.I8: "defghi"}))
        self.assertEqual("ghi" + b,
                         SimdMap({FpElWid.F64: "ghiabc",
                                  IntElWid.I8: "ghidef"}))
        # sub
        self.assertEqual(a - 20,
                         SimdMap({FpElWid.F64: -15, IntElWid.I8: -10}))
        self.assertEqual(20 - a,
                         SimdMap({FpElWid.F64: 15, IntElWid.I8: 10}))
        # mul
        self.assertEqual(a * 2,
                         SimdMap({FpElWid.F64: 10, IntElWid.I8: 20}))
        self.assertEqual(2 * a,
                         SimdMap({FpElWid.F64: 10, IntElWid.I8: 20}))
        self.assertEqual(b * 2,
                         SimdMap({FpElWid.F64: "abcabc",
                                  IntElWid.I8: "defdef"}))
        self.assertEqual(2 * b,
                         SimdMap({FpElWid.F64: "abcabc",
                                  IntElWid.I8: "defdef"}))

        # floordiv
        self.assertEqual(a // 2,
                         SimdMap({FpElWid.F64: 2, IntElWid.I8: 5}))
        self.assertEqual(20 // a,
                         SimdMap({FpElWid.F64: 4, IntElWid.I8: 2}))

        # truediv
        self.assertEqual(repr(a / 2),
                         repr(SimdMap({FpElWid.F64: 2.5, IntElWid.I8: 5.0})))
        self.assertEqual(repr(20 / a),
                         repr(SimdMap({FpElWid.F64: 4.0, IntElWid.I8: 2.0})))

        # mod
        self.assertEqual(a % 3,
                         SimdMap({FpElWid.F64: 2, IntElWid.I8: 1}))
        self.assertEqual(17 % a,
                         SimdMap({FpElWid.F64: 2, IntElWid.I8: 7}))

        # abs
        self.assertEqual(abs(a),
                         SimdMap({FpElWid.F64: 5, IntElWid.I8: 10}))
        self.assertEqual(abs(c),
                         SimdMap({FpElWid.F64: 5, IntElWid.I8: 10}))

        # and
        self.assertEqual(a & 3,
                         SimdMap({FpElWid.F64: 1, IntElWid.I8: 2}))
        self.assertEqual(31 & a,
                         SimdMap({FpElWid.F64: 5, IntElWid.I8: 10}))

        # divmod
        self.assertEqual(divmod(a, 3),
                         SimdMap({FpElWid.F64: (1, 2), IntElWid.I8: (3, 1)}))

        # ceil
        self.assertEqual(math.ceil(d),
                         SimdMap({FpElWid.F64: -3, IntElWid.I8: 11}))

        # floor
        self.assertEqual(math.floor(d),
                         SimdMap({FpElWid.F64: -4, IntElWid.I8: 10}))

        # invert
        self.assertEqual(~a,
                         SimdMap({FpElWid.F64: -6, IntElWid.I8: -11}))
        self.assertEqual(~c,
                         SimdMap({FpElWid.F64: 4, IntElWid.I8: -11}))

        # lshift
        self.assertEqual(a << 2,
                         SimdMap({FpElWid.F64: 20, IntElWid.I8: 40}))
        self.assertEqual(1 << a,
                         SimdMap({FpElWid.F64: 32, IntElWid.I8: 1024}))

        # rshift
        self.assertEqual(a >> 1,
                         SimdMap({FpElWid.F64: 2, IntElWid.I8: 5}))
        self.assertEqual(1000 >> a,
                         SimdMap({FpElWid.F64: 31, IntElWid.I8: 0}))

        # neg
        self.assertEqual(-a,
                         SimdMap({FpElWid.F64: -5, IntElWid.I8: -10}))
        self.assertEqual(-c,
                         SimdMap({FpElWid.F64: 5, IntElWid.I8: -10}))

        # pos
        self.assertEqual(+a,
                         SimdMap({FpElWid.F64: 5, IntElWid.I8: 10}))
        self.assertEqual(+c,
                         SimdMap({FpElWid.F64: -5, IntElWid.I8: 10}))

        # or
        self.assertEqual(a | 2,
                         SimdMap({FpElWid.F64: 7, IntElWid.I8: 10}))
        self.assertEqual(1 | a,
                         SimdMap({FpElWid.F64: 5, IntElWid.I8: 11}))

        # xor
        self.assertEqual(a ^ 2,
                         SimdMap({FpElWid.F64: 7, IntElWid.I8: 8}))
        self.assertEqual(1 ^ a,
                         SimdMap({FpElWid.F64: 4, IntElWid.I8: 11}))


class TestSimdWHintMap(unittest.TestCase):
    def test_extract_width_hint(self):
        self.assertEqual(SimdWHintMap.extract_width_hint(None), None)
        self.assertEqual(SimdWHintMap.extract_width_hint(None, 5), 5)
        self.assertEqual(SimdWHintMap.extract_width_hint(3), 3)
        self.assertEqual(SimdWHintMap.extract_width_hint(3, 5), 3)
        self.assertEqual(SimdWHintMap.extract_width_hint(
            {FpElWid.F64: 3}, 5), 5)
        self.assertEqual(SimdWHintMap.extract_width_hint(
            {FpElWid.F64: 3}), None)
        a = SimdWHintMap({IntElWid.I8: 3, FpElWid.F64: 5}, width_hint=7)
        b = SimdMap(a)
        self.assertEqual(SimdWHintMap.extract_width_hint(a), 7)
        self.assertEqual(SimdWHintMap.extract_width_hint(b), None)

    def test_init(self):
        self.assertEqual(repr(SimdWHintMap(width_hint=1)),
                         "SimdWHintMap({}, width_hint=1)")
        self.assertEqual(repr(SimdWHintMap(width_hint="abc")),
                         "SimdWHintMap({}, width_hint='abc')")
        self.assertEqual(repr(SimdWHintMap()),
                         "SimdWHintMap({})")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap(width_hint=1))),
                         "SimdWHintMap({}, width_hint=1)")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap(width_hint="abc"))),
                         "SimdWHintMap({}, width_hint='abc')")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap())),
                         "SimdWHintMap({})")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap(width_hint=1),
                                           width_hint=2)),
                         "SimdWHintMap({}, width_hint=2)")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap({FpElWid.F16: 5},
                                                        width_hint=1),
                                           width_hint=2)),
                         "SimdWHintMap({FpElWid.F16: 5}, width_hint=2)")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap({FpElWid.F16: 5},
                                                        width_hint=1))),
                         "SimdWHintMap({FpElWid.F16: 5}, width_hint=1)")
        self.assertEqual(repr(SimdWHintMap(SimdWHintMap({FpElWid.F16: 5}))),
                         "SimdWHintMap({FpElWid.F16: 5})")

    def test_eq(self):
        self.assertEqual(SimdWHintMap(), SimdMap())
        self.assertEqual(SimdWHintMap({FpElWid.F16: 5}),
                         SimdMap({FpElWid.F16: 5}))
        self.assertNotEqual(SimdWHintMap({FpElWid.F16: 5}),
                            SimdMap({FpElWid.F16: 6}))
        self.assertNotEqual(SimdWHintMap({FpElWid.F16: 5}, width_hint=3),
                            SimdMap({FpElWid.F16: 5}))
        self.assertEqual(SimdWHintMap({FpElWid.F16: 5}, width_hint=3),
                         SimdWHintMap({FpElWid.F16: 5}, width_hint=3))

    def test_ops(self):
        a = SimdWHintMap({FpElWid.F16: 3, FpElWid.F32: 10}, width_hint=12)
        self.assertEqual(a + 1,
                         SimdWHintMap({FpElWid.F32: 11, FpElWid.F16: 4},
                                      width_hint=13))
        self.assertEqual(a - a,
                         SimdWHintMap({FpElWid.F32: 0, FpElWid.F16: 0},
                                      width_hint=0))
        self.assertEqual(a - 12,
                         SimdWHintMap({FpElWid.F32: -2, FpElWid.F16: -9},
                                      width_hint=0))
        # test exceptions being suppressed for width_hint
        self.assertEqual(5 // (a - 12),
                         SimdWHintMap({FpElWid.F32: -3, FpElWid.F16: -1}))
        # test exceptions not being suppressed for non-width_hint
        with self.assertRaises(ZeroDivisionError):
            5 // (a - 3)


if __name__ == '__main__':
    unittest.main()
