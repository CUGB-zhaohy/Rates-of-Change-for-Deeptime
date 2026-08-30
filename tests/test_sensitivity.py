import numpy as np
import pandas as pd

from roc.sensitivity import (
    compute_mae_mape,
    interpolate_two_point,
    random_subsample_once,
)


def test_interpolation_uses_nearest_bracketing_bins_and_nearest_edge():
    source = pd.DataFrame(
        {
            "Age_node": [-10.0, 0.0, 10.0, 20.0],
            "Counts": [0, 1, 0, 3],
            "Mean_origin": [np.nan, 0.0, np.nan, 10.0],
        }
    )

    result = interpolate_two_point(
        source,
        age_col="Age_node",
        counts_col="Counts",
        target_col="Mean_origin",
        output_col="Mean",
        edge="nearest",
    )

    assert result.loc[result["Age_node"] == -10.0, "Mean"].iloc[0] == 0.0
    assert result.loc[result["Age_node"] == 10.0, "Mean"].iloc[0] == 7.5


def test_random_subsampling_retains_one_observation_per_occupied_interval():
    data = pd.DataFrame(
        {
            "Age": [1.0, 5.0, 21.0, 25.0, 41.0],
            "Value": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )

    sampled = random_subsample_once(data, 20, np.random.default_rng(42))

    assert len(sampled) == 3
    assert sampled["Age"].between(0, 60, inclusive="left").all()


def test_mae_mape_are_computed_against_nonzero_reference_values():
    reference = pd.Series([0.0, 2.0, 4.0], index=[0, 1, 2])
    prediction = pd.Series([1.0, 1.0, 6.0], index=[0, 1, 2])

    mae, mape = compute_mae_mape(prediction, reference)

    assert np.isclose(mae, 4.0 / 3.0)
    assert np.isclose(mape, 50.0)
