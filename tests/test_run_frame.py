import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUN_FRAME_PATH = ROOT / "piBoot" / "run_frame.py"

spec = importlib.util.spec_from_file_location("run_frame", RUN_FRAME_PATH)
run_frame = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_frame)


class RunFrameTest(unittest.TestCase):
    def test_display_once_delegates_to_random_display_script(self):
        with mock.patch.object(run_frame.subprocess, "run") as run:
            run_frame.display_once("/photos", "/frame/display_random_picture.py")

        run.assert_called_once_with([
            "python3",
            "/frame/display_random_picture.py",
            "--image-dir",
            "/photos",
        ], check=True)

    def test_run_frame_runs_display_script_then_sleeps(self):
        class StopAfterSleep:
            def __call__(self, seconds):
                self.seconds = seconds
                raise KeyboardInterrupt

        sleeper = StopAfterSleep()

        with mock.patch.object(run_frame, "display_once") as display_once:
            with self.assertRaises(KeyboardInterrupt):
                run_frame.run_frame(
                    "/photos",
                    "/frame/display_random_picture.py",
                    interval_hours=0.5,
                    sleeper=sleeper,
                )

        display_once.assert_called_once_with("/photos", "/frame/display_random_picture.py")
        self.assertEqual(30 * 60, sleeper.seconds)

    def test_main_rejects_non_positive_interval(self):
        with mock.patch.object(run_frame, "parse_args") as parse_args:
            parse_args.return_value.image_dir = "/photos"
            parse_args.return_value.display_script = "/frame/display_random_picture.py"
            parse_args.return_value.interval_hours = 0

            with mock.patch.object(run_frame.sys, "stderr") as stderr:
                with self.assertRaises(SystemExit) as raised:
                    run_frame.main()

        self.assertEqual(1, raised.exception.code)
        stderr_text = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn("--interval-hours must be greater than 0", stderr_text)


if __name__ == "__main__":
    unittest.main()
