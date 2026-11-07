"""Exercise request validation and failed logging independently of HTTP serving."""
import tempfile
from pathlib import Path
import unittest

from pydantic import ValidationError
from service import IncomeFeatures
from request_log import RequestLog


class ServiceTests(unittest.TestCase):
    def test_missing_features_are_rejected(self):
        with self.assertRaises(ValidationError):
            IncomeFeatures(Education="Masters")

    def test_log_error_does_not_escape_to_caller(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "file"
            blocker.write_text("not a directory")
            recorder = RequestLog(blocker / "requests.jsonl")
            recorder.submit({"prediction": 0})
            recorder.queue.join()
            self.assertEqual(recorder.errors, 1)


if __name__ == "__main__":
    unittest.main()
