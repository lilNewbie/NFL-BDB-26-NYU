"""Circular-angle helpers. Convention: 0 deg = +y, measured clockwise (NGS)."""
from __future__ import annotations

import numpy as np


def ang_diff(a, b):
    """Absolute smallest difference between two angles, 0..180 degrees."""
    return np.abs((np.asarray(a, dtype=float) - np.asarray(b, dtype=float) + 180.0) % 360.0 - 180.0)


def bearing(x0, y0, x1, y1):
    """Direction from (x0, y0) to (x1, y1) in NGS convention."""
    return np.rad2deg(np.arctan2(np.asarray(x1) - x0, np.asarray(y1) - y0)) % 360.0


def circ_mean(angles):
    rad = np.deg2rad(np.asarray(angles, dtype=float))
    return float(np.rad2deg(np.arctan2(np.nanmean(np.sin(rad)), np.nanmean(np.cos(rad)))) % 360.0)


def unit(angle_deg):
    """(dx, dy) unit vector for an NGS angle."""
    rad = np.deg2rad(np.asarray(angle_deg, dtype=float))
    return np.sin(rad), np.cos(rad)
