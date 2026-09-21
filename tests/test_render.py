import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "video"))
import render as R


def lanes():
    loaded = R.load_race()
    return loaded, R.pace(loaded)


def test_pointer_is_on_the_square_it_clicks():
    loaded, _ = lanes()
    for stages in loaded.values():
        for stage in stages:
            clicks = [tuple(state["clicked"]) for state in stage["states"]]
            for k in range(len(clicks)):
                start, _, _ = R.cursor_at(stage, k, 0.0, 0.0)
                assert np.allclose(start, R.cell_center(stage["player"], clicks[k]))
                arrived, _, _ = R.cursor_at(stage, k, 1.0, 0.0)
                assert np.allclose(arrived, R.cell_center(stage["player"], clicks[min(k + 1, len(clicks) - 1)]))


def test_pointer_rests_before_it_glides():
    loaded, _ = lanes()
    stage = loaded["fly"][0]
    if len(stage["states"]) < 2:
        return
    resting, _, _ = R.cursor_at(stage, 0, R.CURSOR_HOLD * 0.9, 0.0)
    assert np.allclose(resting, R.cell_center("fly", tuple(stage["states"][0]["clicked"])))


def test_pointer_fades_out_as_the_board_finishes():
    loaded, _ = lanes()
    for stages in loaded.values():
        stage = stages[-1]
        last = len(stage["states"]) - 1
        _, early, _ = R.cursor_at(stage, last, 1.0, 0.0)
        _, late, _ = R.cursor_at(stage, last, 1.0, 1.0)
        assert early > 0.9 and late < 0.05


def test_race_stays_inside_the_target_length():
    loaded, unit = lanes()
    finishes = [R.make_timeline(stages, unit)[1] for stages in loaded.values()]
    total = max(finishes) + R.OUTRO
    assert R.MOVE_LIMITS[0] <= unit <= R.MOVE_LIMITS[1]
    assert total <= R.TARGET_SECONDS + 1.5


def test_stage_boxes_follow_the_recorded_outcomes():
    loaded, unit = lanes()
    for player, stages in loaded.items():
        timeline, finish = R.make_timeline(stages, unit)
        _, _, _, _, status, _ = R.lane_at(stages, timeline, finish + 0.01)
        assert status == ["won" if stage["game"].won else "lost" for stage in stages]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
