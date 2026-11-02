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
# crop -> (sell price, days to first harvest, days between regrowths or None
# if it's a one-and-done harvest, season). Assumes 1 unit sold per harvest
# (ignores per-harvest extra-yield mechanics like Blueberry's 3-per-harvest).
# Winter has no standard outdoor crops, so it's left empty.
CROPS = {
    "Parsnip":     (35, 4, None, "Spring"),
    "Green Bean":  (40, 10, 3, "Spring"),
    "Cauliflower": (175, 12, None, "Spring"),
    "Potato":      (80, 6, None, "Spring"),
    "Garlic":      (60, 4, None, "Spring"),
    "Kale":        (110, 6, None, "Spring"),
    "Strawberry":  (120, 8, 4, "Spring"),
    "Blueberry":   (50, 13, 4, "Summer"),
    "Corn":        (50, 14, 4, "Summer"),
    "Hops":        (25, 11, 1, "Summer"),
    "Hot Pepper":  (40, 5, 3, "Summer"),
    "Melon":       (250, 12, None, "Summer"),
    "Radish":      (90, 6, None, "Summer"),
    "Wheat":       (25, 4, None, "Summer"),
    "Amaranth":    (150, 7, None, "Fall"),
    "Artichoke":   (160, 8, None, "Fall"),
    "Bok Choy":    (80, 4, None, "Fall"),
    "Cranberries": (75, 7, 5, "Fall"),
    "Eggplant":    (60, 5, 5, "Fall"),
    "Grape":       (80, 10, 3, "Fall"),
    "Pumpkin":     (320, 13, None, "Fall"),
    "Yam":         (160, 10, None, "Fall"),
}
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


def harvestable_crops(season):
    """Crops that grow in `season` and can produce at least one harvest
    within a 28-day month."""
    return [c for c, info in CROPS.items() if info[3] == season and info[1] <= len(DAYS)]


def crop_events(crop, replace, s):
    """Days (within DAYS) one planted crop produces, and the sell value on
    each of those days. Regrowable crops keep producing every regrow_days;
    non-regrowable crops are harvested once unless `replace` re-plants them
    immediately, repeating the full growth cycle for the rest of the month."""
    sell_price, growth_days, regrow_days, _season = CROPS[crop]
    growth_days = grow_time(growth_days, s)
    unit_price = sell_price * (1.1 if s.tiller else 1.0)

    if regrow_days is not None:
        days = np.arange(growth_days, len(DAYS) + 1, grow_time(regrow_days, s))
    elif replace:
        days = np.arange(growth_days, len(DAYS) + 1, growth_days)
    else:
        days = np.array([growth_days]) if growth_days <= len(DAYS) else np.array([], dtype=int)
    return days, np.full(len(days), unit_price)


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
        self.prev_type = "Coop"
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
        new = self.type.get()
        allowed = allowed_animals(new)
        cap = BUILDINGS[new][2]
        wrong = sorted({r.animal.get() for r in self.rows if r.animal.get() not in allowed})
        if wrong or self.total() > cap:
            reasons = []
            if wrong:
                reasons.append("can't house " + ", ".join(wrong))
            if self.total() > cap:
                reasons.append(f"only holds {cap} animals")
            messagebox.showinfo("Can't change building",
                                f"A {new} {' and '.join(reasons)}.\n"
                                "Remove those animals first.")
            self.type.set(self.prev_type)
            return
        self.prev_type = new
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


class App:
    def __init__(self, root):
        root.title("Stardew Animal Profit")
        root.geometry("1180x760")
        self.buildings = []
        self.crops = []

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

        # ---- left, below buildings: season and crops ----
        crop_box = ttk.LabelFrame(left, text="Crops", padding=6)
        crop_box.pack(fill="x", pady=(8, 0))
        season_row = ttk.Frame(crop_box)
        season_row.pack(fill="x")
        ttk.Label(season_row, text="Season:").pack(side="left")
        self.season = tk.StringVar(value="Spring")
        season_combo = ttk.Combobox(season_row, textvariable=self.season, values=SEASONS,
                                    state="readonly", width=10)
        season_combo.pack(side="left", padx=(4, 0))
        season_combo.bind("<<ComboboxSelected>>", lambda e: self.on_season_change())
        ttk.Button(crop_box, text="+  Add crop", command=self.add_crop).pack(anchor="w", pady=(6, 0))
        ttk.Label(crop_box, text="Rows: number \u00d7 crop; \u201cReplace\u201d replants "
                                 "one-and-done crops immediately after harvest").pack(
            anchor="w", pady=(6, 0))
        self.crop_frame = ttk.Frame(crop_box)
        self.crop_frame.pack(fill="x", pady=(4, 0))

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
        self.add_crop()

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

    def add_crop(self):
        options = harvestable_crops(self.season.get())
        if not options:
            messagebox.showinfo("No crops",
                                f"No crops can be harvested in {self.season.get()}.")
            return
        frame = ttk.Frame(self.crop_frame)
        frame.pack(fill="x", pady=2)
        crop = tk.StringVar(value=options[0])
        number = tk.IntVar(value=1)
        replace = tk.BooleanVar(value=False)

        spin = tk.Spinbox(frame, textvariable=number, from_=1, to=999, width=4,
                          command=self.update_plot)
        spin.pack(side="left")
        spin.bind("<KeyRelease>", lambda e: self.update_plot())
        ttk.Label(frame, text="\u00d7").pack(side="left", padx=2)

        combo = ttk.Combobox(frame, textvariable=crop, values=options, state="readonly", width=12)
        combo.pack(side="left")

        check = ttk.Checkbutton(frame, text="Replace", variable=replace, command=self.update_plot)
        check.pack(side="left", padx=(6, 0))

        row = SimpleNamespace(frame=frame, crop=crop, number=number, replace=replace,
                              spin=spin, combo=combo, check=check)
        combo.bind("<<ComboboxSelected>>", lambda e: (self.refresh_crop_row(row), self.update_plot()))
        ttk.Button(frame, text="\u2715", width=3,
                   command=lambda: self.remove_crop(row)).pack(side="left", padx=(6, 0))
        self.crops.append(row)
        self.refresh_crop_row(row)
        self.update_plot()

    def refresh_crop_row(self, row):
        """A regrowing crop keeps producing on its own, so "Replace" only
        applies to (and is only enabled for) one-and-done crops."""
        regrows = CROPS[row.crop.get()][2] is not None
        if regrows:
            row.replace.set(False)
        row.check.config(state="disabled" if regrows else "normal")

    def remove_crop(self, row):
        row.frame.destroy()
        self.crops.remove(row)
        self.update_plot()

    def on_season_change(self):
        for row in list(self.crops):
            row.frame.destroy()
        self.crops.clear()
        if harvestable_crops(self.season.get()):
            self.add_crop()
        self.update_plot()

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
        for row in self.crops:
            count = read_int(row.number, 0)
            crop = row.crop.get()
            days, per_event = crop_events(crop, row.replace.get(), s)
            y = count * per_event
            label = f"{count} × {crop}" + (" (replace)" if row.replace.get() else "")
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