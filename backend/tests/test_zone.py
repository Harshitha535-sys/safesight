import pytest

from app.cv.zone import RectZone, bottom_center


def test_bottom_center():
    assert bottom_center((100, 50, 200, 300)) == (150.0, 300)


def test_zone_to_pixels():
    z = RectZone(0.25, 0.5, 0.75, 1.0)
    assert z.to_pixels(400, 200) == (100.0, 100.0, 300.0, 200.0)


def test_contains_inside_outside_edges():
    z = RectZone(0.25, 0.25, 0.75, 0.75)  # on 1000x1000 -> 250..750
    assert z.contains_point(500, 500, 1000, 1000)
    assert not z.contains_point(100, 500, 1000, 1000)
    assert not z.contains_point(500, 800, 1000, 1000)
    assert z.contains_point(250, 250, 1000, 1000)  # corner counts as inside
    assert z.contains_point(750, 750, 1000, 1000)
    assert not z.contains_point(751, 750, 1000, 1000)


def test_foot_point_not_box_centre_decides():
    """Box overlaps the zone but the feet are outside -> not a violation."""
    z = RectZone(0.0, 0.0, 1.0, 0.5)  # top half of a 1000x1000 frame
    box = (400, 300, 480, 600)  # head in zone, feet at y=600 (outside)
    x, y = bottom_center(box)
    assert not z.contains_point(x, y, 1000, 1000)


@pytest.mark.parametrize("args", [(0.5, 0.1, 0.4, 0.9), (0.1, 0.9, 0.9, 0.2), (-0.1, 0, 0.5, 0.5),
                                  (0, 0, 1.2, 0.5), (0.3, 0.3, 0.3, 0.6)])
def test_invalid_zone_rejected(args):
    with pytest.raises(ValueError):
        RectZone(*args)
