import math

from app.config import CONFIG
from app.geometry.spiral import angle_for_time, radius_for_angle, revolutions_for_duration


def test_45_rpm_math():
    assert math.isclose(CONFIG.revolution_duration_sec, 1.3333333333333333)
    assert math.isclose(revolutions_for_duration(30.0, 45.0), 22.5)
    assert math.isclose(angle_for_time(30.0, 45.0), 45.0 * math.pi)


def test_spiral_moves_one_pitch_per_revolution():
    start = 87.1
    assert math.isclose(radius_for_angle(2 * math.pi, start, 0.82), start - 0.82)

