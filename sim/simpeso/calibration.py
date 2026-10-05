"""Optional calibration of shopper behavior against real sales history (see scripts/calibrate_real.py).

A Calibration changes two things and nothing else:
  * when shoppers arrive: the archetype hour curve is blended with the real hour-of-day profile (weight = how much we
    trust the real sample; the sample is small, so it is a parameter, not 1.0);
  * how big the basket is: a scale that brings simulated lines per visit to the real lines per sale.
Real sales outside simulated trading hours (00:00 to 05:59) cannot be reproduced and are reported, not used.
Default behavior (no calibration) is unchanged."""
import json
from dataclasses import dataclass
from pathlib import Path

from . import behavior

OPEN_H, CLOSE_H = behavior.OPEN_H, behavior.CLOSE_H


@dataclass(frozen=True)
class Calibration:
    hour_share: tuple              # real share of sales per hour for OPEN_H..CLOSE_H-1, renormalised to 1
    weight: float = 0.5            # weight on the real hour profile in the blend
    basket_scale: float = 1.0      # multiplies the archetype basket size
    outside_hours_share: float = 0.0   # real share of sales between 00:00 and 05:59 that the simulator cannot place

    def blend(self, arch_weights) -> list:
        """arch_weights: the archetype's weights over OPEN_H..CLOSE_H-1 (sum 1)."""
        return [(1 - self.weight) * a + self.weight * r for a, r in zip(arch_weights, self.hour_share)]


def from_real(real: dict, weight: float = 0.5, basket_scale: float = 1.0) -> Calibration:
    """real: the 'all' block of real-calibration.json (hour_share keyed by hour string)."""
    hs = {int(h): v for h, v in real["hour_share"].items()}
    inside = [hs.get(h, 0.0) for h in range(OPEN_H, CLOSE_H)]
    total = sum(inside)
    if total <= 0:
        raise ValueError("no real sales inside simulated trading hours")
    return Calibration(tuple(x / total for x in inside), weight, basket_scale, round(sum(v for h, v in hs.items() if h < OPEN_H), 3))


def load(path, weight: float = 0.5, basket_scale: float = 1.0) -> Calibration:
    return from_real(json.loads(Path(path).read_text(encoding="utf-8"))["all"], weight, basket_scale)


def fit_basket_scale(plan, individuals, seed: int, real_lines_per_sale: float, day: int = 1, tolerance: float = 0.03) -> float:
    """Scale so simulated lines per visit match the real lines per sale (two secant steps; clamped)."""
    scale = 1.0
    for _ in range(3):
        c = Calibration(tuple(1.0 / (CLOSE_H - OPEN_H) for _ in range(CLOSE_H - OPEN_H)), 0.0, scale)
        visits = behavior.day_visits(plan, individuals, day, seed, calib=c)
        if not visits:
            break
        mean_lines = sum(len(v.lines) for v in visits) / len(visits)
        if abs(mean_lines - real_lines_per_sale) / real_lines_per_sale < tolerance:
            break
        scale = min(1.5, max(0.3, scale * real_lines_per_sale / mean_lines))
    return round(scale, 3)
