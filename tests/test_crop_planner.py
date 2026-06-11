import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONVERTER_DIR = ROOT / "6ColorsConverter"
sys.path.insert(0, str(CONVERTER_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crop_planner = load_module("crop_planner", CONVERTER_DIR / "crop_planner.py")
analyze = load_module("analyze", CONVERTER_DIR / "analyze.py")


class CropPlannerTest(unittest.TestCase):
    def test_four_by_three_landscape_is_fill_safe(self):
        plan = crop_planner.plan_fill_crop(
            4000, 3000, 800, 480, face_detection="opencv unavailable"
        )

        self.assertEqual("cut", plan.mode)
        self.assertAlmostEqual(0.20, plan.crop_loss, places=2)

    def test_large_crop_loss_stays_scale(self):
        plan = crop_planner.plan_fill_crop(
            3000, 3000, 800, 480, face_detection="opencv unavailable"
        )

        self.assertEqual("scale", plan.mode)
        self.assertIn("above the 30% limit", plan.reason)

    def test_face_inside_center_crop_allows_cut(self):
        plan = crop_planner.plan_fill_crop(
            4000, 3000, 800, 480, faces=[(1000, 1000, 1300, 1300)]
        )

        self.assertEqual("cut", plan.mode)
        self.assertIn("center crop keeps", plan.reason)

    def test_face_near_edge_can_shift_crop(self):
        center_box = crop_planner.center_crop_box(4000, 3000, 800, 480)
        face = (1000, 100, 1300, 400)

        shifted_box = crop_planner.shift_crop_to_include_faces(
            4000, 3000, center_box, [face]
        )
        plan = crop_planner.plan_fill_crop(
            4000, 3000, 800, 480, faces=[face]
        )

        self.assertNotEqual(center_box, shifted_box)
        self.assertTrue(crop_planner.faces_fit_crop([face], shifted_box))
        self.assertEqual("cut", plan.mode)
        self.assertIn("shifted crop keeps", plan.reason)

    def test_face_too_large_to_preserve_forces_scale(self):
        plan = crop_planner.plan_fill_crop(
            4000, 3000, 800, 480, faces=[(1000, 200, 1300, 2800)]
        )

        self.assertEqual("scale", plan.mode)
        self.assertIn("face would be cropped", plan.reason)

    def test_best_effort_shift_moves_toward_edge_face(self):
        center_box = crop_planner.center_crop_box(3648, 2736, 800, 480)
        faces = [
            (1194, 58, 1234, 98),
            (805, 534, 1220, 949),
            (3147, 558, 3589, 1000),
        ]

        shifted_box = crop_planner.shift_crop_to_include_faces(
            3648, 2736, center_box, faces
        )
        best_effort_box = crop_planner.best_effort_shift_crop_to_faces(
            3648, 2736, center_box, faces
        )

        self.assertEqual(center_box, shifted_box)
        self.assertNotEqual(center_box, best_effort_box)
        self.assertEqual(0, best_effort_box[1])


class AnalyzeModeTest(unittest.TestCase):
    def test_analyzer_auto_prefers_safe_fill(self):
        rgb = Image.new("RGB", (4000, 3000), "white")
        with mock.patch.object(analyze, "detect_faces", return_value=((), "opencv unavailable")):
            mode, reason = analyze.suggest_mode(4000, 3000, 800, 480, rgb)

        self.assertEqual("cut", mode)
        self.assertIn("safe crop", reason)

    def test_analyzer_auto_scales_when_face_would_be_cut(self):
        rgb = Image.new("RGB", (4000, 3000), "white")
        faces = ((1000, 200, 1300, 2800),)
        with mock.patch.object(analyze, "detect_faces", return_value=(faces, "detected 1 face(s)")):
            mode, reason = analyze.suggest_mode(4000, 3000, 800, 480, rgb)

        self.assertEqual("scale", mode)
        self.assertIn("face would be cropped", reason)

    def test_analyzer_forced_mode_reports_auto_choice(self):
        rgb = Image.new("RGB", (4000, 3000), "white")
        with mock.patch.object(analyze, "detect_faces", return_value=((), "opencv unavailable")):
            mode, reason = analyze.suggest_mode(4000, 3000, 800, 480, rgb, "scale")

        self.assertEqual("scale", mode)
        self.assertIn("forced by --mode scale", reason)
        self.assertIn("auto would choose cut", reason)


if __name__ == "__main__":
    unittest.main()
