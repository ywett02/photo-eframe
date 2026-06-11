import hashlib
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RGB_SHA256 = "60ce835bb5f0a71b52058b06b07dc0d01158dd4a5e78358114ec20a7270c986c"
EXPECTED_PALETTE = {
    (0, 0, 0),
    (18, 120, 40),
    (25, 55, 175),
    (155, 20, 10),
    (210, 100, 20),
    (255, 200, 0),
    (255, 255, 255),
}
EXPECTED_COUNTS = Counter({
    (255, 255, 255): 175608,
    (0, 0, 0): 58861,
    (25, 55, 175): 49292,
    (18, 120, 40): 39939,
    (210, 100, 20): 39021,
    (155, 20, 10): 19229,
    (255, 200, 0): 2050,
})


class ConvertRegressionTest(unittest.TestCase):
    def test_gdansk_city_matches_current_look(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "gdansk_city.bmp"
            command = [
                sys.executable,
                str(ROOT / "6ColorsConverter" / "convert.py"),
                str(ROOT / "assets" / "gdansk_city.jpg"),
                "--mode", "scale",
                "--dither", "3",
                "--brightness", "1.15",
                "--contrast", "1.20",
                "--saturation", "2.00",
                "--sharpness", "1.50",
                "--gamma", "1.00",
                "--gamap", "0.25",
                "--output", str(output_path),
            ]

            subprocess.run(command, cwd=ROOT, check=True)

            self.assertTrue(output_path.exists())

            generated = Image.open(output_path).convert("RGB")
            golden = Image.open(ROOT / "assets" / "gdansk_city.bmp").convert("RGB")
            generated_pixels = generated.tobytes()
            golden_pixels = golden.tobytes()
            generated_counts = Counter(generated.getdata())

            self.assertEqual((800, 480), generated.size)
            self.assertEqual(EXPECTED_RGB_SHA256, hashlib.sha256(generated_pixels).hexdigest())
            self.assertEqual(golden_pixels, generated_pixels)
            self.assertEqual(EXPECTED_PALETTE, set(generated.getdata()))
            self.assertEqual(EXPECTED_COUNTS, generated_counts)


if __name__ == "__main__":
    unittest.main()
