"""Find the optimal farm: how many buildings, of which type, filled with which
animals.

Reuses run.py's game-data model (ANIMALS, BUILDINGS, profit_events) but instead
of plotting profit curves, scores each animal's expected profit and solves
linear programs that (a) fill a building to capacity with the best animal mix
and (b) choose which building types to build, up to a total building count.
"""

import numpy as np
from scipy.optimize import linprog
from scipy.stats import norm

import run

# Starting friendship is modeled as Gaussian(mean=500, std=250), clipped to [0, 1000].
FRIENDSHIP_MEAN = 500
FRIENDSHIP_STD = 250
FRIENDSHIP_GRID = np.linspace(0, 1000, 1001)

# Farmer level (skills/foraging) is ignored; profession is chosen by the optimizer.
PROFESSIONS = ("None", "Rancher", "Artisan")

# At most this many buildings total. Which type/tier to build is chosen by ROI
# (profit per gold spent), not raw profit -- see choose_building_counts.
MAX_BUILDINGS = 4

# Approximate wiki construction costs: (gold, wood) to upgrade TO this tier
# from the previous one (a Deluxe Coop requires owning a Coop, then a Big Coop).
BUILD_STEPS = {
    "Coop": (4000, 300),
    "Big Coop": (10000, 400),
    "Deluxe Coop": (20000, 500),
    "Barn": (6000, 350),
    "Big Barn": (12000, 400),
    "Deluxe Barn": (25000, 550),
}
UPGRADE_CHAIN = {
    "Coop": ["Coop"],
    "Big Coop": ["Coop", "Big Coop"],
    "Deluxe Coop": ["Coop", "Big Coop", "Deluxe Coop"],
    "Barn": ["Barn"],
    "Big Barn": ["Barn", "Big Barn"],
    "Deluxe Barn": ["Barn", "Big Barn", "Deluxe Barn"],
}


def building_cost(building):
    """Cumulative (gold, wood) to build `building` from scratch, including the
    cheaper tiers that must be bought first since upgrades are sequential."""
    steps = [BUILD_STEPS[t] for t in UPGRADE_CHAIN[building]]
    return sum(g for g, _ in steps), sum(w for _, w in steps)


def settings_for(profession):
    return run.Settings(profession=profession, process=True, foraging_level=0,
                        gatherer=False, botanist=False)


def friendship_weights():
    """Probability weight for each point in FRIENDSHIP_GRID under a Gaussian
    (500, 250) clipped to [0, 1000] (mass outside the range piles up at the
    nearest boundary)."""
    step = FRIENDSHIP_GRID[1] - FRIENDSHIP_GRID[0]
    weights = norm.pdf(FRIENDSHIP_GRID, FRIENDSHIP_MEAN, FRIENDSHIP_STD) * step
    weights[0] += norm.cdf(0, FRIENDSHIP_MEAN, FRIENDSHIP_STD)
    weights[-1] += norm.sf(1000, FRIENDSHIP_MEAN, FRIENDSHIP_STD)
    return weights / weights.sum()


def expected_monthly_profit(animal, weights, settings):
    """Expected total profit over a 28-day month, averaged over the Gaussian
    starting-friendship distribution."""
    totals = np.array([run.profit_events(animal, f, settings)[1].sum()
                       for f in FRIENDSHIP_GRID])
    return float(totals @ weights)


def optimize_building(building, animals, profits):
    """Fill `building` to capacity with whichever animal counts maximize total
    profit: a linear program maximizing profit (linear in animal counts)
    subject to the capacity constraint."""
    capacity = run.BUILDINGS[building][2]
    c = [-profits[a] for a in animals]  # linprog minimizes, so negate profit
    result = linprog(c, A_eq=[[1] * len(animals)], b_eq=[capacity], bounds=(0, None))
    counts = {a: round(n) for a, n in zip(animals, result.x) if round(n) > 0}
    return counts, -result.fun


def choose_building_counts(building_totals, costs):
    """Which building type to build, chosen by ROI (profit per gold spent)
    rather than raw total profit. A building's profit and cost both scale
    linearly with how many copies you build, so ROI is constant per type --
    mixing types only averages two ratios together, which can't beat the
    single best one. All MAX_BUILDINGS slots go to that best-ROI type."""
    best = max(building_totals, key=lambda t: building_totals[t] / costs[t][0])
    return {best: MAX_BUILDINGS}


def best_farm(profession, weights):
    """Optimal building type/count and animal fill under a given profession,
    plus the total monthly farm profit it achieves, the gold/wood to build it,
    and the resulting ROI (profit per gold spent)."""
    settings = settings_for(profession)
    profits = {a: expected_monthly_profit(a, weights, settings) for a in run.ANIMALS}

    building_picks, building_totals = {}, {}
    for building in run.BUILDINGS:
        animals = run.allowed_animals(building)
        counts, total = optimize_building(building, animals, profits)
        building_picks[building] = counts
        building_totals[building] = total

    costs = {t: building_cost(t) for t in run.BUILDINGS}
    building_counts = choose_building_counts(building_totals, costs)
    farm_total = sum(n * building_totals[t] for t, n in building_counts.items())
    gold = sum(n * costs[t][0] for t, n in building_counts.items())
    wood = sum(n * costs[t][1] for t, n in building_counts.items())
    return farm_total, building_counts, building_picks, profits, gold, wood, farm_total / gold


def main():
    run.TABLE = run.load_table()
    weights = friendship_weights()

    results = {p: best_farm(p, weights) for p in PROFESSIONS}
    best = max(results, key=lambda p: results[p][0])

    print(f"Up to {MAX_BUILDINGS} buildings total, type chosen by ROI "
         "(profit per gold spent).\n")
    print("Total farm profit per month by profession:\n")
    for p, (total, *_rest) in sorted(results.items(), key=lambda kv: -kv[1][0]):
        print(f"  {p:<8} {total:10.1f}g" + ("  <- best" if p == best else ""))

    for p in PROFESSIONS:
        total, building_counts, building_picks, profits, gold, wood, roi = results[p]
        print(f"\n=== {p} ({total:.1f}g/month, build cost {gold:,}g + {wood:,} wood, "
             f"ROI {roi:.2f}g/month per g) ===")
        for building, n in building_counts.items():
            print(f"  {n} x {building} (capacity {run.BUILDINGS[building][2]} each):")
            for a, count in building_picks[building].items():
                print(f"    {count} x {a}  ({profits[a]:.1f}g each/month)")


if __name__ == "__main__":
    main()
