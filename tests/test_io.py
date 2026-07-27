import json

import pytest

from geomotif import generate_spiral, save_points

POINTS = [(1.25, -2.5), (0.0, 3.14159), (100.0, 200.0)]


def test_csv_export(tmp_path):
    out = save_points(POINTS, tmp_path / "points.csv")
    lines = out.read_text().splitlines()
    assert lines[0] == "x,y"
    assert lines[1] == "1.25,-2.5"
    assert len(lines) == 1 + len(POINTS)


def test_txt_export_tab_separated(tmp_path):
    out = save_points(POINTS, tmp_path / "points.txt")
    lines = out.read_text().splitlines()
    assert lines[0] == "1.25\t-2.5"
    assert len(lines) == len(POINTS)


def test_tsv_suffix_maps_to_txt(tmp_path):
    out = save_points(POINTS, tmp_path / "points.tsv")
    assert "\t" in out.read_text().splitlines()[0]


def test_json_export_round_trips(tmp_path):
    out = save_points(POINTS, tmp_path / "points.json")
    data = json.loads(out.read_text())
    assert data == [[x, y] for x, y in POINTS]


def test_precision_zero_writes_integers(tmp_path):
    out = save_points(POINTS, tmp_path / "points.txt", precision=0)
    first = out.read_text().splitlines()[0]
    assert first == "1\t-2"  # banker's rounding on .25/.5 toward even


def test_precision_rounds_decimals(tmp_path):
    out = save_points(POINTS, tmp_path / "points.csv", precision=2)
    assert out.read_text().splitlines()[2] == "0.0,3.14"


def test_explicit_fmt_overrides_suffix(tmp_path):
    out = save_points(POINTS, tmp_path / "points.dat", fmt="json")
    assert json.loads(out.read_text())


def test_unknown_suffix_rejected(tmp_path):
    with pytest.raises(ValueError):
        save_points(POINTS, tmp_path / "points.xyz")


def test_export_generated_spiral(tmp_path):
    points = generate_spiral((200, 0), (20, 0), 16, turns=1)
    out = save_points(points, tmp_path / "spiral.csv", precision=1)
    assert len(out.read_text().splitlines()) == 17
