import unittest
from nmigen import Shape
from ieee754.fpcommon.fpscr import FPSCR, RoundingMode


class TestFPSCR(unittest.TestCase):
    def test_FPSCR_layout(self):
        expected = (
            ('RN', RoundingMode),
            ('NI', 1),
            ('XE', 1),
            ('ZE', 1),
            ('UE', 1),
            ('OE', 1),
            ('VE', 1),
            ('VXCVI', 1),
            ('VXSQRT', 1),
            ('VXSOFT', 1),
            ('rsvd1', 1),
            ('FPRF', (
                ('FPCC', (
                    ('FU', 1),
                    ('FE', 1),
                    ('FG', 1),
                    ('FL', 1))),
                ('C', 1))),
            ('FI', 1),
            ('FR', 1),
            ('VXVC', 1),
            ('VXIMZ', 1),
            ('VXZDZ', 1),
            ('VXIDI', 1),
            ('VXISI', 1),
            ('VXSNAN', 1),
            ('XX', 1),
            ('ZX', 1),
            ('UX', 1),
            ('OX', 1),
            ('VX', 1),
            ('FEX', 1),
            ('FX', 1),
            ('DRN', 3),
            ('rsvd2', 29))
        self.assertEqual(FPSCR.layout, expected)

    def test_FPSCR_against_openpower_isa(self):
        try:
            from openpower.fpscr import FPSCRRecord
        except ImportError:
            self.skipTest("openpower-isa not installed")
        expected = dict(FPSCRRecord.layout)
        self.assertEqual(expected['RN'], Shape.cast(RoundingMode).width)
        expected['RN'] = RoundingMode
        expected = repr(expected).replace("[", "(").replace("]", ")")
        self.assertEqual(repr(dict(FPSCR.layout)), expected)

    def test_parts_are_complete_without_overlaps(self):
        fields = {}
        for part in FPSCR.Part:
            if part is FPSCR.PART:
                continue
            for name, ty in part.layout:
                self.assertNotIn(name, fields)
                fields[name] = ty
        self.assertEqual(fields, dict(FPSCR.layout))


if __name__ == '__main__':
    unittest.main()
