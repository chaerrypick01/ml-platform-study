"""Input-contract checks; service integration is exercised by the lab itself."""
import unittest

import pandas as pd

from batch_inference import COLUMNS, normalize


class InputContract(unittest.TestCase):
    def test_missing_feature(self):
        with self.assertRaisesRegex(ValueError, "Missing feature columns"):
            normalize(pd.DataFrame())

    def test_missing_values_from_unknown_or_expired_entity(self):
        with self.assertRaisesRegex(ValueError, "Missing Feast values"):
            normalize(pd.DataFrame([{column: None for column in COLUMNS}]))

    def test_training_whitespace_and_column_order(self):
        frame = pd.DataFrame([{column: "  example  " for column in reversed(COLUMNS)}])
        result = normalize(frame)
        self.assertEqual(list(result), COLUMNS)
        self.assertTrue((result == "example").all().all())
        self.assertTrue((frame == "  example  ").all().all())


if __name__ == "__main__":
    unittest.main()
