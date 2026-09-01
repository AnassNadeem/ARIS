from backend.sessions import (
    build_path_traces,
    project_points_along_path,
    project_points_to_path,
    sample_path_trace,
    stabilize_path_fracs,
)


def test_path_traces_follow_the_circuit():
    path_x = [0.0, 10.0, 10.0, 0.0, 0.0]
    path_y = [0.0, 0.0, 10.0, 10.0, 0.0]
    samples = {
        "VER": [
            (100.0, 0.0, 0.0, "OnTrack"),
            (101.0, 10.0, 0.0, "OnTrack"),
            (102.0, 10.0, 10.0, "OnTrack"),
            (103.0, 0.0, 10.0, "OnTrack"),
        ]
    }
    traces = build_path_traces(samples, path_x, path_y, min_dt=0.0)
    assert "VER" in traces
    assert len(traces["VER"]["t"]) == 4
    start = sample_path_trace(traces["VER"], 100.0)
    mid = sample_path_trace(traces["VER"], 101.5)
    assert start is not None and start < 0.1
    assert mid is not None and 0.3 < mid < 0.7


def test_stabilize_path_fracs_drops_reverse_jumps():
    out = stabilize_path_fracs([0.10, 0.14, 0.40, 0.18, 0.22])
    assert out[0] == 0.10
    assert out[1] > out[0]
    # 0.40 → 0.18 is a reverse projection; drop the sample (keep last good)
    assert out[3] == out[2]
    assert out[4] == out[3]
    assert all(0 <= v < 1 for v in out)


def test_stabilize_path_fracs_allows_start_finish():
    out = stabilize_path_fracs([0.96, 0.98, 0.02, 0.05])
    assert out[2] < 0.1
    assert out[3] > out[2]


def test_path_trace_wraps_start_finish():
    trace = {"t": [10.0, 11.0], "f": [0.95, 0.05]}
    mid = sample_path_trace(trace, 10.5)
    assert mid is not None
    assert mid < 0.15 or mid > 0.85


def test_align_raw_gps_onto_normalized_path():
    from backend.sessions import align_pos_samples_to_path, build_path_traces

    bounds = {"min_x": -1000.0, "max_x": 8000.0, "min_y": -1600.0, "max_y": 6700.0}
    raw = {
        "VER": [
            (1.0, 0.0, 0.0, "OnTrack"),
            (2.0, 0.0, 0.0, "OnTrack"),
            (3.0, -800.0, -1400.0, "OnTrack"),
            (4.0, 7000.0, -1400.0, "OnTrack"),
            (5.0, 7000.0, 6000.0, "OnTrack"),
        ]
    }
    fitted, changed = align_pos_samples_to_path(raw, bounds)
    assert changed
    assert fitted["VER"][0][1] > 20
    assert max(p[1] for p in fitted["VER"]) < 430
    path_x = [20.0, 420.0, 420.0, 20.0, 20.0]
    path_y = [20.0, 20.0, 260.0, 260.0, 20.0]
    traces = build_path_traces(fitted, path_x, path_y, min_dt=0.0)
    fracs = traces["VER"]["f"]
    assert fracs[-1] > fracs[0]


def test_apply_bounds_accepts_disk_dict():
    from backend.sessions import _apply_bounds, _coerce_bounds

    raw = {"min_x": 0.0, "max_x": 100.0, "min_y": 0.0, "max_y": 50.0}
    assert _coerce_bounds(raw) is not None
    x, y = _apply_bounds(50.0, 25.0, raw)
    assert 20 < x < 400
    assert 20 < y < 260


def test_nudge_path_frac_drops_reverse_jumps():
    from backend.sessions import nudge_path_frac

    path_x = [0.0, 10.0, 10.0, 0.0, 0.0]
    path_y = [0.0, 0.0, 1.0, 1.0, 0.0]
    # Point on the return lane would snap globally; drop GPS and keep previous.
    held = nudge_path_frac(0.25, 5.1, 0.8, path_x, path_y)
    assert held < 0.45


def test_correct_path_frac_discards_hairpin_gps():
    from backend.sessions import compute_timing_path_frac, correct_path_frac, display_path_frac

    timing = compute_timing_path_frac(lap_number=1, time_since_lap_start_s=45, expected_lap_time_s=90)
    assert abs(timing - 0.5) < 1e-9
    assert abs(correct_path_frac(0.16, 0.40) - 0.16) < 1e-9
    grid = display_path_frac(timing_frac=0.0, gps_frac=0.97, grid_position=1, race_lap_frac=0.0)
    assert abs(grid) < 1e-6


def test_ff1_pack_ready_requires_gps():
    from backend.live import _ff1_pack_ready

    assert not _ff1_pack_ready({"source": "openf1", "ff1": {}})
    assert not _ff1_pack_ready({"source": "fastf1", "ff1": {"ok": True}})
    assert _ff1_pack_ready({"source": "fastf1", "ff1": {"pos_samples": {"VER": [(1.0, 0.0, 0.0, "OnTrack")]}}})


def test_along_path_does_not_snap_to_return_lane():
    # Out-and-back: bottom y=0 going right, top y=1 going left.
    path_x = [0.0, 10.0, 10.0, 0.0, 0.0]
    path_y = [0.0, 0.0, 1.0, 1.0, 0.0]
    xs = [1.0, 3.0, 5.0, 5.1]
    ys = [0.0, 0.0, 0.0, 0.8]
    nearest = project_points_to_path(xs, ys, path_x, path_y)
    along = project_points_along_path(xs, ys, path_x, path_y)
    assert nearest[-1] > 0.5
    assert along[-1] < 0.45
    for a, b in zip(along, along[1:]):
        d = b - a
        if d < -0.5:
            d += 1.0
        assert d >= -0.02
