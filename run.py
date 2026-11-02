import csv
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from types import SimpleNamespace

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

CSV_FILE = Path(__file__).with_name("animals.csv")
DAYS = np.arange(1, 29)
NONE = "(none)"

# ---- Game data / assumptions (edit freely) ----------------------------------
# building -> (kind, tier, capacity)
BUILDINGS = {
    "Coop":        ("coop", 1, 4),
    "Big Coop":    ("coop", 2, 8),
    "Deluxe Coop": ("coop", 3, 12),
    "Barn":        ("barn", 1, 4),
    "Big Barn":    ("barn", 2, 8),
    "Deluxe Barn": ("barn", 3, 12),
}
# animal -> (product, days between products, building kind, lowest building tier)
# A building can hold an animal if it is the right kind and at least that tier.
ANIMALS = {
    "Chicken":      ("Egg",          1, "coop", 1),
    "Void Chicken": ("Void Egg",     1, "coop", 2),
    "Duck":         ("Duck Egg",     2, "coop", 2),
    "Dinosaur":     ("Dinosaur Egg", 7, "coop", 2),
    "Rabbit":       ("Wool",         4, "coop", 3),
    "Cow":          ("Milk",         1, "barn", 1),
    "Ostrich":      ("Ostrich Egg",  7, "barn", 1),
    "Goat":         ("Goat Milk",    2, "barn", 2),
    "Sheep":        ("Wool",         3, "barn", 3),
    "Pig":          ("Truffle",      1, "barn", 3),  # pigs use their own truffle model
}
FRIENDSHIP_GAIN_PER_DAY = 15   # friendship points gained each day
# Chance wool gives 2 cloth (from the wiki page)
WOOL_TWO_CLOTH = {"Regular": 0.0, "Silver": 0.1, "Gold": 0.5, "Iridium": 1.0}

SEASONS = ("Spring", "Summer", "Fall", "Winter")
# crop -> (category, sell price, seed cost, days to first harvest, days
# between regrowths or None if it's a one-and-done harvest, seasons it grows
# in). Category is "Vegetable", "Fruit", "Flower", or "Seed" (a purchasable
# seed packet that's itself a machine ingredient, e.g. Sunflower Seeds).
# Assumes 1 unit sold per harvest (ignores per-harvest extra-yield mechanics
# like Blueberry's 3-per-harvest). Winter has no standard outdoor crops.
# Broccoli/Carrot aren't real Stardew Valley items, so they're not included;
# Powdermelon (a Fair prize, no gold seed cost) covers that spirit instead.
CROPS = {
    "Parsnip":         ("Vegetable", 35, 20, 4, None, ("Spring",)),
    "Green Bean":      ("Vegetable", 40, 60, 10, 3, ("Spring",)),
    "Cauliflower":     ("Vegetable", 175, 80, 12, None, ("Spring",)),
    "Potato":          ("Vegetable", 80, 50, 6, None, ("Spring",)),
    "Garlic":          ("Vegetable", 60, 40, 4, None, ("Spring",)),
    "Kale":            ("Vegetable", 110, 70, 6, None, ("Spring",)),
    "Rhubarb":         ("Fruit", 220, 100, 13, None, ("Spring",)),
    "Strawberry":      ("Fruit", 120, 100, 8, 4, ("Spring",)),
    "Tulip":           ("Flower", 30, 20, 6, None, ("Spring",)),
    "Blue Jazz":       ("Flower", 50, 30, 7, None, ("Spring",)),
    "Blueberry":       ("Fruit", 50, 80, 13, 4, ("Summer",)),
    "Corn":            ("Vegetable", 50, 150, 14, 4, ("Summer", "Fall")),
    "Hops":            ("Vegetable", 25, 60, 11, 1, ("Summer",)),
    "Hot Pepper":      ("Fruit", 40, 40, 5, 3, ("Summer",)),
    "Melon":           ("Fruit", 250, 80, 12, None, ("Summer",)),
    "Powdermelon":     ("Fruit", 250, 0, 12, None, ("Summer",)),  # Fair prize, no gold cost
    "Radish":          ("Vegetable", 90, 40, 6, None, ("Summer",)),
    "Red Cabbage":     ("Vegetable", 260, 100, 9, None, ("Summer",)),
    "Starfruit":       ("Fruit", 750, 400, 13, None, ("Summer",)),
    "Wheat":           ("Vegetable", 25, 10, 4, None, ("Summer", "Fall")),
    "Poppy":           ("Flower", 140, 100, 7, None, ("Summer",)),
    "Summer Spangle":  ("Flower", 90, 50, 8, None, ("Summer",)),
    "Sunflower":       ("Flower", 80, 200, 8, None, ("Summer", "Fall")),
    "Amaranth":        ("Vegetable", 150, 70, 7, None, ("Fall",)),
    "Artichoke":       ("Vegetable", 160, 30, 8, None, ("Fall",)),
    "Bok Choy":        ("Vegetable", 80, 50, 4, None, ("Fall",)),
    "Cranberries":     ("Fruit", 75, 120, 7, 5, ("Fall",)),
    "Eggplant":        ("Vegetable", 60, 20, 5, 5, ("Fall",)),
    "Grape":           ("Fruit", 80, 60, 10, 3, ("Fall",)),
    "Pumpkin":         ("Vegetable", 320, 100, 13, None, ("Fall",)),
    "Sweet Gem Berry": ("Vegetable", 3000, 1000, 24, None, ("Fall",)),
    "Yam":             ("Vegetable", 160, 60, 10, None, ("Fall",)),
    "Fairy Rose":      ("Flower", 290, 100, 12, None, ("Fall",)),
    # Ancient Fruit: from Ancient Seeds, not normally purchasable with gold
    # (Seed Maker / artifact spots) -- grows in any season outdoors but Winter.
    "Ancient Fruit":   ("Fruit", 550, 0, 28, 7, ("Spring", "Summer", "Fall")),
    # Not grown -- an already-purchased seed packet fed straight into an Oil
    # Maker (or resold). Modeled as an instant "harvest" so Replace lets you
    # keep buying and pressing a fresh packet every day.
    "Sunflower Seeds": ("Seed", 20, 20, 1, None, ("Spring", "Summer", "Fall", "Winter")),
}
# Crops classified "Fruit" turn into Wine (Keg) / Jam (Preserves Jar) and can
# use the Dehydrator; "Vegetable" turns into Juice (Keg) / Pickles (Jar); "Flower"
# and "Seed" get neither by default (see OIL_MAKER_PRICE for the exceptions).
# Wheat and Hops have their own fixed-price Keg recipes (Beer, Pale Ale)
# instead of the generic Wine/Juice formula, and have no Preserves Jar recipe.
KEG_FIXED_PRICE = {"Wheat": 200, "Hops": 300}
NO_PRESERVES_JAR = {"Wheat", "Hops"}
# Oil Maker only accepts these specific crops, regardless of category, and
# they all produce plain Oil at the same price.
OIL_MAKER_PRICE = {"Corn": 100, "Sunflower": 100, "Sunflower Seeds": 100}

# tree -> (fruit sell price, sapling cost, seasons it fruits in). All fruit
# trees take the same ~28 days to mature from a sapling, then fruit once a
# day during their season(s) thereafter (a tree planted fresh this month
# barely matures by day 28, so it nets mostly the sapling cost this month --
# an accurate reflection of fruit trees being a long-term investment).
FRUIT_TREES = {
    "Apricot":     (50, 2000, ("Spring",)),
    "Cherry":      (80, 3400, ("Spring",)),
    "Orange":      (100, 4000, ("Summer",)),
    "Peach":       (140, 6000, ("Summer",)),
    "Apple":       (100, 4000, ("Fall",)),
    "Pomegranate": (140, 6000, ("Fall",)),
}
TREE_MATURITY_DAYS = 28
TREE_REGROW_DAYS = 1
TREE_TILES = 9              # tiles reserved per tree planted outdoors
GREENHOUSE_TREE_SLOTS = 18  # the greenhouse's dedicated tree ring

FARM_CROP_CAPACITY = 3427   # tillable squares on the standard farm map
GREENHOUSE_CAPACITY = 120   # tillable squares inside the greenhouse
# -----------------------------------------------------------------------------

# skill -> {level 5 profession: [level 10 options for that profession]}
PROFESSIONS = {
    "Farming":  {"Rancher": ["Coopmaster", "Shepherd"],
                 "Tiller": ["Artisan", "Agriculturist"]},
    "Foraging": {"Forester": ["Lumberjack", "Tapper"],
                 "Gatherer": ["Botanist", "Tracker"]},
}


@dataclass
class Settings:
    profession: str = "None"       # Farming profession that matters: None / Rancher / Artisan
    process: bool = True           # sell processed goods (True) or raw products (False)
    foraging_level: int = 0
    gatherer: bool = False         # 20% chance of a double truffle
    botanist: bool = False         # all truffles are iridium quality
    tiller: bool = False           # +10% crop sell price
    agriculturist: bool = False    # -10% crop growth/regrowth time
    winter: bool = False           # outdoor pigs can't dig for truffles in winter


def read_int(var, default=0):
    """Read an IntVar, tolerating empty/invalid text in an entry box."""
    try:
        return var.get()
    except tk.TclError:
        return default


def allowed_animals(building_type):
    """Animals that may live in this building type."""
    kind, tier, _ = BUILDINGS[building_type]
    return [a for a, info in ANIMALS.items() if info[2] == kind and info[3] <= tier]


def clamp_counts(counts, capacity, edited=None):
    """Keep the building's total at or under capacity. The row the user just
    edited (index `edited`) is clamped first so other rows keep their numbers."""
    counts = list(counts)
    order = ([] if edited is None else [edited]) + [i for i in range(len(counts)) if i != edited]
    for i in order:
        others = sum(counts) - counts[i]
        counts[i] = max(0, min(counts[i], capacity - others))
    return counts


def clamp_tile_counts(counts, tile_costs, capacity, edited=None):
    """Like clamp_counts, but each row may consume more than 1 tile per unit
    (e.g. a fruit tree takes 9 tiles). Returns the clamped *unit* count per
    row -- clamping happens in tile-space, then converts back by floor
    division so a row never ends up owning a fractional tree."""
    tiles = clamp_counts([n * c for n, c in zip(counts, tile_costs)], capacity, edited)
    return [t // c if c else 0 for t, c in zip(tiles, tile_costs)]


def load_table():
    """(profession, item, quality) -> (raw sell price, expected processed price).
    Profession is 'None', 'Rancher' or 'Artisan' (rows from the wiki CSV)."""
    table = {}
    with open(CSV_FILE, newline="") as f:
        for row in csv.DictReader(f):
            if row["Profession"] not in ("None", "Rancher", "Artisan"):
                continue
            item, quality = row["Item"], row["Quality"]
            # Normal milk always makes normal-quality cheese
            if item in ("Milk", "Goat Milk") and row["Processed Item Quality"] != "Regular":
                continue
            weight = 1.0
            if item == "Wool":
                p2 = WOOL_TWO_CLOTH[quality]
                weight = p2 if row["Processed Quantity"] == "2" else 1 - p2
            key = (row["Profession"], item, quality)
            raw = int(row["Sell Price"])
            processed = table.get(key, (raw, 0))[1]
            processed += weight * int(row["Processed Item Sell Price"])
            table[key] = (raw, processed)
    return table


TABLE = None  # loaded in main()


def value(profession, product, quality, process):
    raw, processed = TABLE[(profession, product, quality)]
    return processed if process else raw


def forage_quality_probs(level, botanist):
    """Foraged item quality odds (wiki Foraging page)."""
    if botanist:
        return {"Iridium": 1.0}
    gold = level / 30
    silver = (1 - gold) * level / 15
    return {"Regular": 1 - gold - silver, "Silver": silver, "Gold": gold}


def profit_events(animal, start_friendship, s):
    """Days (within DAYS) this animal actually produces, and the expected profit
    on each of those days specifically (not averaged across the production
    interval, e.g. a duck's full expected egg value lands only every other day)."""
    product, interval, _, _ = ANIMALS[animal]
    friendship = np.minimum(1000, start_friendship + FRIENDSHIP_GAIN_PER_DAY * (DAYS - 1))

    if animal == "Pig":
        if s.winter:
            return DAYS, np.zeros_like(friendship)  # no grass to dig truffles from
        # Truffle quality comes from Foraging level/Botanist, not friendship.
        # First truffle is ~certain each day; each extra has chance friendship/1500
        # (expected 1/(1-p) truffles). Gatherer adds a 20% double-harvest chance.
        p_extra = friendship / 1500
        truffles = 1 / (1 - p_extra) * (1.2 if s.gatherer else 1.0)
        per_truffle = sum(
            prob * value(s.profession, product, q, s.process)
            for q, prob in forage_quality_probs(s.foraging_level, s.botanist).items()
        )
        return DAYS, truffles * per_truffle  # pigs can produce truffles every day

    chance = friendship / 1000
    p_gold = chance / 2
    p_silver = (1 - p_gold) * chance
    p_regular = 1 - p_gold - p_silver
    per_product = (
        p_regular * value(s.profession, product, "Regular", s.process)
        + p_silver * value(s.profession, product, "Silver", s.process)
        + p_gold * value(s.profession, product, "Gold", s.process)
    )
    mask = DAYS % interval == 0
    return DAYS[mask], per_product[mask]


def grow_time(days, s):
    """Agriculturist speeds up growth and regrowth by ~10%."""
    return max(1, round(days * 0.9)) if s.agriculturist else days


def is_tree(name):
    return name in FRUIT_TREES


def crop_info(name):
    """Normalized (category, sell price, seed/sapling cost, growth days,
    regrow days or None, seasons) for anything plantable -- a regular crop,
    flower, or seed, or a fruit tree (always "Fruit", always the same
    maturity/regrow timing)."""
    if is_tree(name):
        sell_price, seed_cost, seasons = FRUIT_TREES[name]
        return ("Fruit", sell_price, seed_cost, TREE_MATURITY_DAYS, TREE_REGROW_DAYS, seasons)
    return CROPS[name]


def harvestable_crops(season):
    """Crops (not trees) that grow in `season` and can produce at least one
    harvest within a 28-day month."""
    return [c for c, info in CROPS.items() if season in info[5] and info[3] <= len(DAYS)]


def harvestable_crops_any_season():
    """Crops (not trees) that can produce at least one harvest within a
    28-day month, regardless of season -- the greenhouse grows year-round."""
    return [c for c, info in CROPS.items() if info[3] <= len(DAYS)]


def harvestable_trees(season):
    """Fruit trees that fruit in `season`."""
    return [t for t, info in FRUIT_TREES.items() if season in info[2]]


def harvestable_trees_any_season():
    """All fruit trees -- the greenhouse's dedicated tree ring fruits them
    in any season."""
    return list(FRUIT_TREES)


def processing_methods(name):
    """Ways to sell this crop/tree: always Raw, plus Keg and Preserves Jar
    for Vegetables/Fruits (unless excluded), plus Dehydrator for Fruits, plus
    Oil Maker for the handful of crops that specifically support it."""
    category = crop_info(name)[0]
    methods = ["Raw"]
    if category in ("Vegetable", "Fruit"):
        methods.append("Keg")
        if name not in NO_PRESERVES_JAR:
            methods.append("Preserves Jar")
    if category == "Fruit":
        methods.append("Dehydrator")
    if name in OIL_MAKER_PRICE:
        methods.append("Oil Maker")
    return methods


def processing_price(name, method, s):
    """Sell price for one unit of `name` through the given method. Tiller's
    +10% applies only to raw crops; Artisan's +40% applies only to goods made
    in a machine -- they never both apply to the same item, just like the
    equivalent Rancher/Artisan split for animal products."""
    category, raw_price, *_ = crop_info(name)
    if method == "Raw":
        return raw_price * (1.1 if s.tiller else 1.0)

    artisan_mult = 1.4 if s.profession == "Artisan" else 1.0
    if method == "Keg":
        if name in KEG_FIXED_PRICE:
            return KEG_FIXED_PRICE[name] * artisan_mult
        return raw_price * (3.0 if category == "Fruit" else 2.25) * artisan_mult
    if method == "Preserves Jar":
        return (raw_price * 2 + 50) * artisan_mult  # Jam/Pickles
    if method == "Oil Maker":
        return OIL_MAKER_PRICE[name] * artisan_mult
    return raw_price * 1.5 * artisan_mult  # Dehydrator: Dried Fruit/Raisins (5 fruit -> 1, averaged per unit)


def processing_days(name, method):
    """Approximate in-game days for a machine to finish the job (actual times
    vary per item in the real game; these are rounded wiki-average assumptions,
    edit freely). Raw crops sell instantly."""
    if method == "Raw":
        return 0
    if method == "Keg":
        if name in KEG_FIXED_PRICE:
            return 2   # Beer / Pale Ale
        return 8 if crop_info(name)[0] == "Fruit" else 5  # Wine vs Juice
    if method == "Preserves Jar":
        return 3
    return 1  # Oil Maker / Dehydrator


def crop_events(name, replace, method, s):
    """Days (within DAYS) one planted crop/tree's goods actually sell on --
    harvest day plus however long the chosen processing method takes -- and
    the net value (sell price minus any seed/sapling cost) on each of those
    days. Regrowable plants (and fruit trees, once mature) keep producing
    every regrow_days off a single seed/sapling purchase; non-regrowable
    crops are harvested once unless `replace` re-plants them immediately (a
    fresh seed purchase each cycle), repeating the full growth cycle for the
    rest of the month. A harvest whose processing wouldn't finish by day 28
    earns no profit this month (it wasn't sold yet)."""
    _category, _sell_price, seed_cost, growth_days, regrow_days, _seasons = crop_info(name)
    growth_days = grow_time(growth_days, s)
    unit_price = processing_price(name, method, s)
    delay = processing_days(name, method)

    if regrow_days is not None:
        harvest_days = np.arange(growth_days, len(DAYS) + 1, grow_time(regrow_days, s))
        prices = np.full(len(harvest_days), unit_price)
        if len(prices):
            prices[0] -= seed_cost  # one seed/sapling bought up front
    elif replace:
        harvest_days = np.arange(growth_days, len(DAYS) + 1, growth_days)
        prices = np.full(len(harvest_days), unit_price - seed_cost)  # a fresh seed each cycle
    else:
        harvest_days = (np.array([growth_days]) if growth_days <= len(DAYS)
                        else np.array([], dtype=int))
        prices = np.full(len(harvest_days), unit_price - seed_cost)

    sale_days = harvest_days + delay
    prices = prices[sale_days <= len(DAYS)]
    sale_days = sale_days[sale_days <= len(DAYS)]
    return sale_days, prices


class ScrollFrame(ttk.Frame):
    """A vertically scrollable area; put widgets in .inner"""

    def __init__(self, parent, width=450):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, width=width, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        # Mouse wheel scrolling while the pointer is over this area
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


class SkillRow:
    """One skill: level 5 and level 10 profession choice."""

    def __init__(self, parent, name, row, on_change):
        self.tree = PROFESSIONS[name]
        self.on_change = on_change
        self.p5 = tk.StringVar(value=NONE)
        self.p10 = tk.StringVar(value=NONE)

        ttk.Label(parent, text=name).grid(row=row, column=0, sticky="w", padx=(0, 6))

        self.box5 = ttk.Combobox(parent, textvariable=self.p5, state="readonly", width=11,
                                 values=[NONE] + list(self.tree))
        self.box5.grid(row=row, column=1, padx=4)
        self.box5.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        self.box10 = ttk.Combobox(parent, textvariable=self.p10, state="disabled", width=11,
                                  values=[NONE])
        self.box10.grid(row=row, column=2)
        self.box10.bind("<<ComboboxSelected>>", lambda e: self.on_change())

    def refresh(self):
        # Level 10 options depend on the level 5 choice
        options = self.tree.get(self.p5.get(), [])
        self.box10.config(values=[NONE] + options)
        if self.p10.get() not in options:
            self.p10.set(NONE)
        self.box10.config(state="readonly" if options else "disabled")
        self.on_change()


class BuildingCard:
    """One building: type dropdown, capacity counter, and its own animal rows."""

    def __init__(self, app, parent):
        self.app = app
        self.type = tk.StringVar(value="Coop")
        self.rows = []  # SimpleNamespace(frame, animal, friendship, number, spin, combo)

        self.frame = ttk.Frame(parent, relief="groove", borderwidth=2, padding=6)
        self.frame.pack(fill="x", pady=4, padx=(0, 4))

        top = ttk.Frame(self.frame)
        top.pack(fill="x")
        combo = ttk.Combobox(top, textvariable=self.type, values=list(BUILDINGS),
                             state="readonly", width=12)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda e: self.on_type_change())
        self.count_label = ttk.Label(top, width=14)
        self.count_label.pack(side="left", padx=6)
        self.add_btn = ttk.Button(top, text="+  Add animal", command=self.add_animal)
        self.add_btn.pack(side="left")
        ttk.Button(top, text="\u2715", width=3,
                   command=lambda: app.remove_building(self)).pack(side="right")

        self.animal_frame = ttk.Frame(self.frame)
        self.animal_frame.pack(fill="x", pady=(4, 0))
        self.refresh()

    def capacity(self):
        return BUILDINGS[self.type.get()][2]

    def counts(self):
        return [max(0, read_int(r.number)) for r in self.rows]

    def total(self):
        return sum(self.counts())

    def refresh(self, edited=None):
        """Enforce the capacity cap and update the counter / Add button."""
        cap = self.capacity()
        index = self.rows.index(edited) if edited in self.rows else None
        counts = clamp_counts(self.counts(), cap, index)
        for r, n in zip(self.rows, counts):
            if read_int(r.number) != n:
                r.number.set(n)
        total = sum(counts)
        for r, n in zip(self.rows, counts):
            r.spin.config(to=max(1, cap - (total - n)))
        self.count_label.config(text=f"{total}/{cap} animals")
        self.add_btn.config(state="normal" if total < cap else "disabled")

    def on_numbers_change(self, row):
        self.refresh(edited=row)
        self.app.update_plot()

    def on_type_change(self):
        """Switching type may make some housed animals invalid for it (e.g. a
        Deluxe Barn's Pig moved to a plain Coop) -- just drop those rows
        rather than blocking the change; anything still valid is kept and
        clamped to the new capacity."""
        new = self.type.get()
        allowed = allowed_animals(new)
        for row in [r for r in self.rows if r.animal.get() not in allowed]:
            row.frame.destroy()
            self.rows.remove(row)
        for r in self.rows:
            r.combo.config(values=allowed)
        self.refresh()
        self.app.update_plot()

    def add_animal(self):
        if self.total() >= self.capacity():
            return
        allowed = allowed_animals(self.type.get())
        frame = ttk.Frame(self.animal_frame)
        frame.pack(fill="x", pady=2)
        animal = tk.StringVar(value=allowed[0])
        friendship = tk.IntVar(value=500)
        number = tk.IntVar(value=1)

        spin = tk.Spinbox(frame, textvariable=number, from_=1, to=self.capacity(), width=4,
                          command=lambda: self.on_numbers_change(row))
        spin.pack(side="left")
        spin.bind("<KeyRelease>", lambda e: self.on_numbers_change(row))
        ttk.Label(frame, text="\u00d7").pack(side="left", padx=2)

        combo = ttk.Combobox(frame, textvariable=animal, values=allowed,
                             state="readonly", width=12)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda e: self.app.update_plot())

        tk.Scale(frame, variable=friendship, from_=0, to=1000, orient="horizontal",
                 length=130, command=lambda v: self.app.update_plot()).pack(side="left", padx=4)

        row = SimpleNamespace(frame=frame, animal=animal, friendship=friendship,
                              number=number, spin=spin, combo=combo)
        ttk.Button(frame, text="\u2715", width=3,
                   command=lambda: self.remove_animal(row)).pack(side="left")
        self.rows.append(row)
        self.refresh()
        self.app.update_plot()

    def remove_animal(self, row):
        row.frame.destroy()
        self.rows.remove(row)
        self.refresh()
        self.app.update_plot()


class CropSection:
    """A tile-capacity-limited group of crop/tree rows: used for the outdoor
    farm (capacity = tillable squares, crops+trees limited to the current
    season), the greenhouse (120 tiles, any crop regardless of season), and
    the greenhouse's separate 18-slot tree ring. `tile_cost(name)` lets a
    single section mix items with different space requirements, e.g. a fruit
    tree taking 9 outdoor tiles per tree vs. 1 for a regular crop."""

    def __init__(self, app, parent, title, capacity, crop_options, tile_cost=None):
        self.app = app
        self.capacity = capacity
        self.crop_options = crop_options  # callable -> list of valid crop/tree names
        self.tile_cost = tile_cost or (lambda name: 1)
        self.rows = []  # SimpleNamespace(frame, crop, number, replace, method, spin, combo, ...)

        self.box = ttk.LabelFrame(parent, text=title, padding=6)
        self.box.pack(fill="x", pady=(8, 0))
        top = ttk.Frame(self.box)
        top.pack(fill="x")
        self.add_btn = ttk.Button(top, text="+  Add crop", command=self.add_crop)
        self.add_btn.pack(side="left")
        self.count_label = ttk.Label(top, width=16)
        self.count_label.pack(side="left", padx=6)
        self.crop_frame = ttk.Frame(self.box)
        self.crop_frame.pack(fill="x", pady=(4, 0))

    def counts(self):
        return [max(0, read_int(r.number)) for r in self.rows]

    def tile_costs(self):
        return [self.tile_cost(r.crop.get()) for r in self.rows]

    def total(self):
        """Tiles currently in use (not raw unit count)."""
        return sum(n * c for n, c in zip(self.counts(), self.tile_costs()))

    def refresh(self, edited=None):
        """Enforce the tile-capacity cap and update the counter / Add button."""
        index = self.rows.index(edited) if edited in self.rows else None
        costs = self.tile_costs()
        counts = clamp_tile_counts(self.counts(), costs, self.capacity, index)
        for r, n in zip(self.rows, counts):
            if read_int(r.number) != n:
                r.number.set(n)
        used = sum(n * c for n, c in zip(counts, costs))
        for r, n, c in zip(self.rows, counts, costs):
            r.spin.config(to=max(1, (self.capacity - (used - n * c)) // c))
        self.count_label.config(text=f"{used}/{self.capacity} tiles")
        self.add_btn.config(state="normal" if used < self.capacity else "disabled")

    def on_numbers_change(self, row):
        self.refresh(edited=row)
        self.app.update_plot()

    def add_crop(self):
        if self.total() >= self.capacity:
            return
        options = self.crop_options()
        if not options:
            messagebox.showinfo("No crops", "No crops are available here right now.")
            return
        frame = ttk.Frame(self.crop_frame)
        frame.pack(fill="x", pady=2)
        crop = tk.StringVar(value=options[0])
        number = tk.IntVar(value=1)
        replace = tk.BooleanVar(value=False)
        method = tk.StringVar(value="Raw")

        room = max(1, (self.capacity - self.total()) // self.tile_cost(options[0]))
        spin = tk.Spinbox(frame, textvariable=number, from_=1, to=room, width=5,
                          command=lambda: self.on_numbers_change(row))
        spin.pack(side="left")
        spin.bind("<KeyRelease>", lambda e: self.on_numbers_change(row))
        ttk.Label(frame, text="×").pack(side="left", padx=2)

        combo = ttk.Combobox(frame, textvariable=crop, values=options, state="readonly", width=12)
        combo.pack(side="left")

        method_combo = ttk.Combobox(frame, textvariable=method, state="readonly", width=12)
        method_combo.pack(side="left", padx=(4, 0))
        method_combo.bind("<<ComboboxSelected>>", lambda e: self.app.update_plot())

        check = ttk.Checkbutton(frame, text="Replace", variable=replace, command=self.app.update_plot)
        check.pack(side="left", padx=(6, 0))

        row = SimpleNamespace(frame=frame, crop=crop, number=number, replace=replace, method=method,
                              spin=spin, combo=combo, method_combo=method_combo, check=check)
        combo.bind("<<ComboboxSelected>>", lambda e: (self.refresh_crop_row(row), self.on_numbers_change(row)))
        ttk.Button(frame, text="✕", width=3,
                   command=lambda: self.remove_crop(row)).pack(side="left", padx=(6, 0))
        self.rows.append(row)
        self.refresh_crop_row(row)
        self.refresh()
        self.app.update_plot()

    def refresh_crop_row(self, row):
        """A regrowing crop (or a mature fruit tree) keeps producing on its
        own, so "Replace" only applies to (and is only enabled for)
        one-and-done crops. The processing dropdown's options depend on which
        methods this crop supports (e.g. Wheat/Hops have no Preserves Jar)."""
        regrows = crop_info(row.crop.get())[4] is not None
        if regrows:
            row.replace.set(False)
        row.check.config(state="disabled" if regrows else "normal")

        methods = processing_methods(row.crop.get())
        row.method_combo.config(values=methods)
        if row.method.get() not in methods:
            row.method.set("Raw")

    def remove_crop(self, row):
        row.frame.destroy()
        self.rows.remove(row)
        self.refresh()
        self.app.update_plot()

    def refresh_options(self):
        """Call when the valid crop list changes (e.g. a season switch): drop
        rows whose crop no longer qualifies, and refresh the rest's dropdown."""
        options = self.crop_options()
        for row in [r for r in self.rows if r.crop.get() not in options]:
            row.frame.destroy()
            self.rows.remove(row)
        for row in self.rows:
            row.combo.config(values=options)
        self.refresh()
        self.app.update_plot()


class App:
    def __init__(self, root):
        root.title("Stardew Animal Profit")
        root.geometry("1280x920")
        self.buildings = []

        # ---- left: buildings and their animals ----
        left = ttk.Frame(root, padding=8)
        left.pack(side="left", fill="y")
        ttk.Button(left, text="+  Add building", command=self.add_building).pack(anchor="w")
        self.process = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Process products (mayo, cheese, cloth...)",
                        variable=self.process, command=self.update_plot).pack(anchor="w", pady=(6, 0))
        ttk.Label(left, text="Rows: number \u00d7 animal, starting friendship (0-1000)").pack(
            anchor="w", pady=(8, 0))
        self.scroll = ScrollFrame(left, width=450)
        self.scroll.pack(fill="both", expand=True, pady=(4, 0))

        # ---- left, below buildings: season, outdoor crops, and greenhouse ----
        season_row = ttk.Frame(left)
        season_row.pack(fill="x", pady=(8, 0))
        ttk.Label(season_row, text="Season:").pack(side="left")
        self.season = tk.StringVar(value="Spring")
        season_combo = ttk.Combobox(season_row, textvariable=self.season, values=SEASONS,
                                    state="readonly", width=10)
        season_combo.pack(side="left", padx=(4, 0))
        season_combo.bind("<<ComboboxSelected>>", lambda e: self.on_season_change())

        # Fruit trees share the same 3427-tile farm budget as regular crops
        # outdoors (9 tiles each), so they're options within the one section.
        self.farm_crops = CropSection(
            self, left, "Crops (outdoor)", FARM_CROP_CAPACITY,
            lambda: harvestable_crops(self.season.get()) + harvestable_trees(self.season.get()),
            tile_cost=lambda name: TREE_TILES if is_tree(name) else 1)
        self.greenhouse = CropSection(
            self, left, "Greenhouse (any season)", GREENHOUSE_CAPACITY,
            lambda: harvestable_crops_any_season())
        # The greenhouse's fruit trees live in its own dedicated 18-slot ring,
        # entirely separate from its 120 regular crop tiles.
        self.greenhouse_trees = CropSection(
            self, left, "Greenhouse fruit trees", GREENHOUSE_TREE_SLOTS,
            lambda: harvestable_trees_any_season())
        ttk.Label(left, wraplength=430, text=(
            "Rows: number \u00d7 crop \u00d7 sell as Raw/Keg/Preserves Jar/Oil Maker/Dehydrator; "
            "\u201cReplace\u201d replants one-and-done crops immediately after harvest. "
            "Seed/sapling cost is already subtracted from profit.")
        ).pack(anchor="w", pady=(6, 0))

        # ---- right: graph on top, skills underneath ----
        right = ttk.Frame(root)
        right.pack(side="right", fill="both", expand=True)

        skills_box = ttk.LabelFrame(right, text="Skills & professions", padding=6)
        skills_box.pack(side="bottom", fill="x", padx=8, pady=8)
        ttk.Label(skills_box, wraplength=420, text=(
            "Farming: Rancher (+20% animal products) or Tiller (+10% crops); "
            "Tiller's level 10 options are Artisan (+40% artisan/processed goods) "
            "or Agriculturist (-10% crop growth/regrowth time).\n"
            "Foraging: only affects pigs' truffles (Gatherer = more truffles, "
            "Botanist = iridium quality).")
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        for col, text in enumerate(["Skill", "Level 5", "Level 10"]):
            ttk.Label(skills_box, text=text).grid(row=1, column=col, sticky="w")
        self.skills = {name: SkillRow(skills_box, name, i + 2, self.update_plot)
                       for i, name in enumerate(PROFESSIONS)}

        self.fig = Figure(figsize=(7, 4.5), tight_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        # Start with one Coop holding a chicken and one crop so the graph isn't empty
        self.add_building().add_animal()
        self.farm_crops.add_crop()

    def settings(self):
        farming, foraging = self.skills["Farming"], self.skills["Foraging"]
        if farming.p10.get() == "Artisan":
            profession = "Artisan"
        elif farming.p5.get() == "Rancher":
            profession = "Rancher"
        else:
            profession = "None"
        foraging_level = 10 if foraging.p10.get() != NONE else 5 if foraging.p5.get() != NONE else 0
        return Settings(
            profession=profession,
            process=self.process.get(),
            foraging_level=foraging_level,
            gatherer=foraging.p5.get() == "Gatherer",
            botanist=foraging.p10.get() == "Botanist",
            tiller=farming.p5.get() == "Tiller",
            agriculturist=farming.p10.get() == "Agriculturist",
            winter=self.season.get() == "Winter",
        )

    def add_building(self):
        card = BuildingCard(self, self.scroll.inner)
        self.buildings.append(card)
        self.update_plot()
        return card

    def remove_building(self, card):
        card.frame.destroy()
        self.buildings.remove(card)
        self.update_plot()

    def on_season_change(self):
        # Only the outdoor crops are season-locked; the greenhouse is unaffected.
        self.farm_crops.refresh_options()

    def update_plot(self):
        s = self.settings()
        self.ax.clear()
        seen = {}  # numbering for buildings of the same type: "Coop 1", "Coop 2"
        plotted = 0
        total = np.zeros(len(DAYS))
        for card in self.buildings:
            btype = card.type.get()
            seen[btype] = seen.get(btype, 0) + 1
            for row in card.rows:
                count = read_int(row.number, 0)
                days, per_event = profit_events(row.animal.get(), row.friendship.get(), s)
                y = count * per_event
                self.ax.scatter(days, y, s=18,
                                label=(f"{btype} {seen[btype]}: {count} \u00d7 "
                                       f"{row.animal.get()} (start {row.friendship.get()})"))
                total[days - 1] += y
                plotted += 1
        sections = (("", self.farm_crops), ("Greenhouse: ", self.greenhouse),
                   ("Greenhouse: ", self.greenhouse_trees))
        for section_label, section in sections:
            for row in section.rows:
                count = read_int(row.number, 0)
                crop, method = row.crop.get(), row.method.get()
                days, per_event = crop_events(crop, row.replace.get(), method, s)
                y = count * per_event
                label = (f"{section_label}{count} × {crop}"
                        + (f" ({method})" if method != "Raw" else "")
                        + (" (replace)" if row.replace.get() else ""))
                self.ax.scatter(days, y, s=18, label=label)
                total[days - 1] += y
                plotted += 1
        if plotted:
            self.ax.plot(DAYS, total, label="Total profit", color="black",
                        linewidth=2, marker="o", markersize=4, zorder=0)
        self.ax.set_xlim(0.5, 28.5)
        self.ax.set_xticks(DAYS)
        self.ax.tick_params(axis="x", labelsize=7)
        self.ax.set_ylim(bottom=0)
        self.ax.set_xlabel("Day")
        self.ax.set_ylabel("Profit per day (g)")
        self.ax.set_title("Expected profit per day"
                          + ("" if s.profession == "None" else f" ({s.profession})"))
        self.ax.grid(alpha=0.3)
        if plotted:
            self.ax.legend(fontsize=8)
        else:
            msg = "Add animals to a building" if self.buildings else "Click + to add a building"
            self.ax.text(0.5, 0.5, msg, ha="center", va="center", transform=self.ax.transAxes)
        self.canvas.draw_idle()


def main():
    global TABLE
    TABLE = load_table()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()