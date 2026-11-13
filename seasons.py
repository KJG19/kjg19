"""Seasonal ASCII animations for the bottom strip of the profile card.

Each scene returns (static, frames):
  static  - cells drawn once (ground, tree, snowman...)
  frames  - list of cell dicts that change every frame (snow, lights, ball...)
A cell dict maps (row, col) -> (char, colour_class). Dynamic cells never land on
a static cell, so the static layer only has to be stored once in the SVG.
"""
import math
import random

COLS, ROWS = 96, 9
GROUND = ROWS - 1

# month -> scene name
SEASON_BY_MONTH = {
    1: "snowman", 2: "snowman", 3: "snowman",
    4: "spring", 5: "spring",
    6: "golf", 7: "golf", 8: "golf",
    9: "fall", 10: "fall",
    11: "christmas", 12: "christmas",
}

COLOURS = {
    "dark": {
        "snow": "#e6edf3", "green": "#3fb950", "dkgreen": "#238636", "brown": "#a0703c",
        "red": "#f85149", "gold": "#e3b341", "blue": "#58a6ff", "pink": "#f778ba",
        "orange": "#ff8c42", "white": "#f0f6fc", "gray": "#8b949e", "rain": "#79c0ff",
    },
    "light": {
        "snow": "#8fb8de", "green": "#1a7f37", "dkgreen": "#116329", "brown": "#7a4e1d",
        "red": "#cf222e", "gold": "#bf8700", "blue": "#0969da", "pink": "#bf3989",
        "orange": "#d4580a", "white": "#6e7781", "gray": "#57606a", "rain": "#0969da",
    },
}

# ------------------------------------------------------------------ helpers


def put(grid, row, col, text, cls):
    for i, ch in enumerate(text):
        c = col + i
        if ch != " " and 0 <= row < ROWS and 0 <= c < COLS:
            grid[(row, c)] = (ch, cls)


def put_centered(grid, row, center, text, cls):
    put(grid, row, center - len(text) // 2, text, cls)


def free(cell, static, frame):
    return cell not in static and cell not in frame


def falling(static, frame, f, n_frames, count, chars, cls, seed, rows=(0, GROUND), loops=1, slant=0, sway=1.0):
    """Particles that fall `loops` times per animation cycle and wrap around, so the loop is seamless."""
    rng = random.Random(seed)
    top, bottom = rows
    height = bottom - top
    for _ in range(count):
        x0, y0 = rng.uniform(0, COLS), rng.uniform(0, height)
        phase, ch = rng.uniform(0, 2 * math.pi), rng.choice(chars)
        colour = rng.choice(cls) if isinstance(cls, list) else cls
        t = f / n_frames
        y_float = (y0 + loops * height * t) % height
        x = int(x0 + sway * math.sin(2 * math.pi * t * loops + phase) + slant * y_float) % COLS
        cell = (top + int(y_float), x)
        if free(cell, static, frame):
            frame[cell] = (ch, colour)


def fill_gaps(grid, rows, c1, c2):
    """Mark empty cells inside a shape as taken, so snow and leaves don't fall through it."""
    for r in rows:
        cols = [c for (rr, c) in grid if rr == r and c1 <= c <= c2]
        if cols:
            for c in range(min(cols), max(cols) + 1):
                grid.setdefault((r, c), (" ", None))


def snow_ground(grid, pattern="~-~--~-~-"):
    for c in range(COLS):
        grid[(GROUND, c)] = (pattern[c % len(pattern)], "snow")

# ------------------------------------------------------------------ scenes


def snowman():
    F = 40
    static = {}
    snow_ground(static)
    C = 70
    put_centered(static, 1, C, "_===_", "gray")
    put_centered(static, 2, C, "(   )", "white")
    put_centered(static, 2, C, ",", "orange")
    put_centered(static, 3, C, "{===}", "red")
    put_centered(static, 4, C, "(  :  )", "white")
    put(static, 4, C - 6, "\\_", "brown")
    put(static, 4, C + 4, "_/", "brown")
    put_centered(static, 5, C, "(    :    )", "white")
    put_centered(static, 6, C, "(     :     )", "white")
    put_centered(static, 7, C, "(___________)", "white")
    fill_gaps(static, range(1, 8), C - 7, C + 7)
    frames = []
    for f in range(F):
        fr = {}
        eyes = "-" if f in (18, 19) else "o"          # blink once per loop
        fr[(2, C - 1)] = (eyes, "gray")
        fr[(2, C + 1)] = (eyes, "gray")
        falling(static, fr, f, F, 70, "*..", "snow", seed=1)
        frames.append(fr)
    return static, frames, 5.0


def spring():
    F = 60
    static = {}
    grass = ",.'`,.,'"
    for c in range(COLS):
        static[(GROUND, c)] = (grass[c % len(grass)], "green")
    for x in (14, 44, 78):
        put(static, 0, x, " .--.", "gray")
        put(static, 1, x, "(____)", "gray")
    frames = []
    flowers = [(24, 0), (50, F // 3), (72, 2 * F // 3)]
    for f in range(F):
        fr = {}
        for col, offset in flowers:
            s = ((f + offset) % F) / F
            if s < 0.4:                                   # stem growing
                h = 1 + int(s / 0.4 * 4)
            else:
                h = 4
            top = GROUND - h
            for r in range(top, GROUND):
                fr[(r, col)] = ("|", "green")
            if h >= 3:
                fr[(GROUND - 2, col - 1)] = ("\\", "green")
            if h >= 4:
                fr[(GROUND - 3, col + 1)] = ("/", "green")
            if 0.4 <= s < 0.5:
                fr[(top - 1, col)] = ("o", "dkgreen")      # bud
            elif 0.5 <= s < 0.58:
                put(fr, top - 1, col - 1, "(o)", "pink")
                fr[(top - 1, col)] = ("o", "gold")
            elif s >= 0.58:                               # full bloom
                put(fr, top - 2, col - 1, ",@,", "pink")
                put(fr, top - 1, col - 2, "@( )@", "pink")
                fr[(top - 1, col)] = ("o", "gold")
                put(fr, top, col - 1, "'@'", "pink")
        falling(static, fr, f, F, 28, "/", "rain", seed=2, rows=(2, GROUND), loops=4, slant=-0.6, sway=0)
        frames.append(fr)
    return static, frames, 6.0


def golf():
    F = 56
    static = {}
    turf = ",',`',"
    for c in range(COLS):
        static[(GROUND, c)] = (turf[c % len(turf)], "green")
    HOLE, POLE = 81, 82
    for r in range(2, GROUND):
        static[(r, POLE)] = ("|", "gray")
    static[(GROUND, HOLE)] = ("U", "gray")
    put(static, GROUND - 1, 10, "_T_", "white")       # tee
    frames = []
    for f in range(F):
        fr = {}
        # sun with rays that flick between two poses
        put_centered(fr, 2, 5, "O", "gold")
        if (f // 4) % 2 == 0:
            put_centered(fr, 1, 5, "\\ | /", "gold"); put_centered(fr, 2, 5, "--   --", "gold")
            put_centered(fr, 3, 5, "/ | \\", "gold")
        else:
            put_centered(fr, 1, 5, ".  '  .", "gold"); put_centered(fr, 2, 5, "-     -", "gold")
            put_centered(fr, 3, 5, "'  .  '", "gold")
        # flag flutter
        flag = ("\\", "/") if (f // 3) % 2 == 0 else ("~\\", "~/")
        put(fr, 2, POLE + 1, flag[0], "red")
        put(fr, 3, POLE + 1, flag[1], "red")
        # ball: sit, fly in an arc, roll and slow down, drop in
        ball = None
        if f < 6:
            ball = (GROUND - 2, 11)
        elif f < 24:
            u = (f - 6) / 18
            ball = (GROUND - 1 - round(6 * 4 * u * (1 - u)), round(11 + u * (58 - 11)))
        elif f < 40:
            v = (f - 24) / 16
            ball = (GROUND - 1, round(58 + (HOLE - 58) * (1 - (1 - v) ** 2)))
        if ball and ball not in static:
            fr[ball] = ("o", "white")
        if 41 <= f < 54:
            put(fr, 0, HOLE - 4, "IN THE HOLE!", "gold")
        frames.append(fr)
    return static, frames, 5.6


def fall():
    F = 72
    static = {}
    rng = random.Random(4)
    leafy = ["orange", "red", "gold"]
    canopy = ["   .@%&@%.   ", " @%&@%&@%&@% ", "%&@%&@%&@%&@%", " &@%&@%&@%&@ ", "   '%&@%&'   "]
    for r, line in enumerate(canopy):
        for i, ch in enumerate(line):
            if ch != " ":
                static[(r, 4 + i)] = (ch, rng.choice(leafy))
    for r in range(5, GROUND):
        put(static, r, 9, "|  |", "brown")
    pile = ".,:;.,"
    for c in range(COLS):
        static[(GROUND, c)] = (pile[c % len(pile)], rng.choice(leafy + ["brown"]))
    frames = []
    for f in range(F):
        fr = {}
        rng2 = random.Random(5)
        t = f / F
        for _ in range(26):
            x0, y0, ph = rng2.uniform(0, COLS), rng2.uniform(0, GROUND), rng2.uniform(0, 6.3)
            ch, colour = rng2.choice("&%*@~"), rng2.choice(leafy)
            x = int(x0 + COLS * t) % COLS                         # wind carries them across
            y = int((y0 + GROUND * t + 1.2 * math.sin(2 * math.pi * 3 * t + ph)) % GROUND)
            if free((y, x), static, fr):
                fr[(y, x)] = (ch, colour)
        frames.append(fr)
    return static, frames, 7.2


def christmas():
    F = 36
    static = {}
    snow_ground(static)
    C = 48
    widths = [1, 3, 5, 7, 9, 11]
    lights = []
    rng = random.Random(6)
    for i, w in enumerate(widths):
        r = 1 + i
        left = C - w // 2
        static[(r, left - 1)] = ("/", "green")
        static[(r, left + w)] = ("\\", "green")
        for c in range(left, left + w):
            if w > 1 and rng.random() < 0.35:
                lights.append((r, c))
            else:
                static[(r, c)] = (".", "dkgreen")
    put_centered(static, 7, C, "[_]", "brown")
    put(static, 7, C - 7, "[#]", "red")
    put(static, 7, C + 5, "[#]", "blue")
    palette = ["red", "gold", "blue", "pink"]
    frames = []
    for f in range(F):
        fr = {}
        fr[(0, C)] = ("*", "gold") if (f // 3) % 2 == 0 else ("+", "gold")
        for i, cell in enumerate(lights):
            fr[cell] = ("o", palette[(i + f // 4) % len(palette)])
        falling(static, fr, f, F, 60, "*..", "snow", seed=7)
        frames.append(fr)
    return static, frames, 3.6


SCENES = {"snowman": snowman, "spring": spring, "golf": golf, "fall": fall, "christmas": christmas}


def scene_for(month):
    return SCENES[SEASON_BY_MONTH[month]]()
