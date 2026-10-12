import unittest
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from kit_body_paint import skin_coordinates

class BodyPaintTests(unittest.TestCase):
    def test_anatomical_fields_are_finite_bounded_repeatable_and_not_flat(self):
        co=np.array([[-.12,-.10,1.30],[.12,-.10,1.30],[0,-.10,1.42],[0,-.10,1.65],[-.12,0,.20],[.12,0,.20]])
        normal=np.tile([0,-1,0],(len(co),1))
        uv=skin_coordinates(co,normal,1.50,1.32,1.02,.48,.08)
        np.testing.assert_array_equal(uv,skin_coordinates(co,normal,1.50,1.32,1.02,.48,.08))
        self.assertTrue(np.isfinite(uv).all())
        self.assertTrue(((uv[:,0]>=.60)&(uv[:,0]<=1.05)).all())
        self.assertTrue(((uv[:,1]>=.05)&(uv[:,1]<=.95)).all())
        self.assertGreater(np.ptp(uv[:,0]),.06)
        self.assertGreater(np.ptp(uv[:,1]),.10)

    def test_real_pigment_bitmap_matches_its_provenance(self):
        asset = Path(__file__).resolve().parents[2] / "assets/characters/kit/body_brush_pigment-v1.png"
        raw = asset.read_bytes()
        self.assertEqual(b"\x89PNG\r\n\x1a\n", raw[:8])
        width, height = struct.unpack(">II", raw[16:24])
        self.assertGreaterEqual(min(width, height), 256)
        manifest = json.loads(Path(str(asset) + ".provenance.json").read_text())
        self.assertEqual(manifest["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest["dimensions"], [width, height])
        self.assertIn("pending", manifest["approval"])

    def test_nonfinite_body_data_fails(self):
        co=np.array([[0,0,0],[0,0,float('nan')]])
        with self.assertRaises(ValueError): skin_coordinates(co,np.zeros_like(co),1.50,1.32,1.02,.48,.08)

if __name__=='__main__': unittest.main()
