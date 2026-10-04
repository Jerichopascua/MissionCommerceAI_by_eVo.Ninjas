"""Demand response learned from observed sales.

Model: units in a window ~ Poisson(base * ratio^beta), where ratio = price paid / list price and beta is a
category-level log-price slope (negative: a cheaper price sells more). beta is the maximum-likelihood slope under a
ridge prior, so with little data it stays near the prior and with price variation it moves toward the data.
An hour-of-day profile (learned from sales) says how much of a day's units are still to come."""
import math
from collections import defaultdict

OPEN_HOUR, CLOSE_HOUR = 6, 24
BETA_MIN, BETA_MAX = -6.0, 0.5


class DemandModel:
    def __init__(self, prior_beta: float = -1.3, prior_weight: float = 3.0):
        self.prior_beta = prior_beta
        self.prior_weight = prior_weight
        self._obs = defaultdict(list)            # category -> [(x, base, units)]
        self._hours = {h: 1.0 for h in range(OPEN_HOUR, CLOSE_HOUR)}

    def observe(self, category: str, base_rate: float, ratio: float, units: float) -> None:
        if base_rate <= 0 or ratio <= 0:
            return
        self._obs[category].append((math.log(ratio), float(base_rate), float(units)))

    def count(self, category: str) -> int:
        return len(self._obs[category])

    def beta(self, category: str) -> float:
        b = self.prior_beta
        data = [o for o in self._obs[category] if abs(o[0]) > 1e-9]
        if not data:
            return b
        for _ in range(50):
            g = -self.prior_weight * (b - self.prior_beta)
            h = -self.prior_weight
            for x, base, y in data:
                mu = base * math.exp(b * x)
                g += x * (y - mu)
                h -= x * x * mu
            step = g / h
            b = min(BETA_MAX, max(BETA_MIN, b - step))
            if abs(step) < 1e-9:
                break
        return b

    def fit_hours(self, hour_units: dict) -> None:
        total = sum(hour_units.values())
        if total <= 0:
            return
        smoothed = {h: hour_units.get(h, 0.0) + 0.02 * total / (CLOSE_HOUR - OPEN_HOUR) for h in range(OPEN_HOUR, CLOSE_HOUR)}
        self._hours = smoothed

    def share_left(self, hour: float) -> float:
        """Share of a day's units still to come at the start of `hour` (1 at open, 0 at or after close)."""
        if hour >= CLOSE_HOUR:
            return 0.0
        total = sum(self._hours.values())
        left = sum(v for h, v in self._hours.items() if h >= max(OPEN_HOUR, int(hour)))
        return left / total

    def expected_units(self, category: str, base_per_day: float, ratio: float, days_left: float, hour: float):
        """Mean and an ~80% interval of the units sold between now and the end of the horizon (days_left counts today)."""
        exposure = base_per_day * (self.share_left(hour) + max(0.0, days_left - 1.0))
        mean = exposure * max(ratio, 1e-6) ** self.beta(category)
        sd = math.sqrt(max(mean, 0.0))
        return mean, max(0.0, mean - 1.28 * sd), mean + 1.28 * sd
