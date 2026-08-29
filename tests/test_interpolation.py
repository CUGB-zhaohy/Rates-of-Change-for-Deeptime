import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from roc.interpolation import interpolate_weighted


class BracketingNeighbourInterpolationTest(unittest.TestCase):
    def interpolate(self, ages, values, counts, **kwargs):
        table = pd.DataFrame(
            {
                "Age_node": ages,
                "Value": values,
                "Counts": counts,
            }
        )
        return interpolate_weighted(
            table=table,
            target_col="Value",
            output_col="Interpolated",
            **kwargs,
        )["Interpolated"].to_numpy(dtype=float)

    def test_only_nearest_valid_node_on_each_side_contributes(self):
        result = self.interpolate(
            ages=[0.0, 1.0, 2.0, 3.0, 4.0],
            values=[0.0, np.nan, 20.0, 100.0, 1000.0],
            counts=[1.0, 0.0, 1.0, 1.0, 1.0],
        )
        self.assertAlmostEqual(result[1], 10.0)

    def test_sample_counts_weight_the_two_bracketing_nodes(self):
        result = self.interpolate(
            ages=[0.0, 1.0, 2.0],
            values=[0.0, np.nan, 20.0],
            counts=[2.0, 0.0, 6.0],
        )
        self.assertAlmostEqual(result[1], 15.0)

    def test_temporal_distance_weights_the_two_bracketing_nodes(self):
        result = self.interpolate(
            ages=[0.0, 2.0, 5.0],
            values=[0.0, np.nan, 100.0],
            counts=[1.0, 0.0, 1.0],
        )
        self.assertAlmostEqual(result[1], 40.0)

    def test_consecutive_missing_bins_use_the_same_bracketing_endpoints(self):
        result = self.interpolate(
            ages=[0.0, 1.0, 2.0, 3.0],
            values=[0.0, np.nan, np.nan, 30.0],
            counts=[1.0, 0.0, 0.0, 1.0],
        )
        self.assertAlmostEqual(result[1], 10.0)
        self.assertAlmostEqual(result[2], 20.0)

    def test_distance_beta_zero_uses_count_weights_only(self):
        result = self.interpolate(
            ages=[0.0, 1.0, 4.0],
            values=[0.0, np.nan, 40.0],
            counts=[1.0, 0.0, 3.0],
            distance_beta=0.0,
        )
        self.assertAlmostEqual(result[1], 30.0)

    def test_edge_modes_are_respected(self):
        nearest = self.interpolate(
            ages=[0.0, 1.0, 2.0],
            values=[np.nan, 10.0, 20.0],
            counts=[0.0, 1.0, 1.0],
            edge_mode="nearest",
        )
        keep_nan = self.interpolate(
            ages=[0.0, 1.0, 2.0],
            values=[np.nan, 10.0, 20.0],
            counts=[0.0, 1.0, 1.0],
            edge_mode="nan",
        )
        zero = self.interpolate(
            ages=[0.0, 1.0, 2.0],
            values=[np.nan, 10.0, 20.0],
            counts=[0.0, 1.0, 1.0],
            edge_mode="zero",
        )
        self.assertAlmostEqual(nearest[0], 10.0)
        self.assertTrue(np.isnan(keep_nan[0]))
        self.assertAlmostEqual(zero[0], 0.0)

    def test_existing_values_and_original_row_order_are_preserved(self):
        result = self.interpolate(
            ages=[2.0, 0.0, 1.0],
            values=[20.0, 0.0, np.nan],
            counts=[1.0, 1.0, 0.0],
        )
        np.testing.assert_allclose(result, [20.0, 0.0, 10.0])

    def test_missing_or_nonpositive_counts_fall_back_to_one(self):
        result = self.interpolate(
            ages=[0.0, 1.0, 2.0],
            values=[0.0, np.nan, 20.0],
            counts=[np.nan, 0.0, -2.0],
        )
        self.assertAlmostEqual(result[1], 10.0)


if __name__ == "__main__":
    unittest.main()
