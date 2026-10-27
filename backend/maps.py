"""Server-owned arena layouts, collision areas, and spawn points."""

from dataclasses import dataclass


ARENA_WIDTH = 960
ARENA_HEIGHT = 540


@dataclass(frozen=True)
class Area:
    """A rectangular map feature measured in arena coordinates."""

    id: str
    x: float
    y: float
    width: float
    height: float
    kind: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class ArenaMap:
    """All data needed to load, simulate, and draw one arena."""

    id: str
    name: str
    description: str
    theme: str
    ground: str
    grid: str
    wall: str
    wall_highlight: str
    hazard_color: str
    danger_color: str
    obstacles: tuple[Area, ...]
    hazards: tuple[Area, ...]
    danger_zones: tuple[Area, ...]
    coin_spawns: tuple[tuple[float, float], ...]
    player_spawns: tuple[tuple[float, float], ...]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "theme": self.theme,
            "width": ARENA_WIDTH,
            "height": ARENA_HEIGHT,
            "ground": self.ground,
            "grid": self.grid,
            "wall": self.wall,
            "wallHighlight": self.wall_highlight,
            "hazardColor": self.hazard_color,
            "dangerColor": self.danger_color,
            "obstacles": [area.to_dict() for area in self.obstacles],
            "hazards": [area.to_dict() for area in self.hazards],
            "dangerZones": [area.to_dict() for area in self.danger_zones],
            "coinSpawns": [{"x": x, "y": y} for x, y in self.coin_spawns],
            "playerSpawns": [{"x": x, "y": y} for x, y in self.player_spawns],
        }


MAPS: dict[str, ArenaMap] = {
    "grasslands": ArenaMap(
        id="grasslands",
        name="Grasslands Arena",
        description="Open fields, old stone and muddy patches.",
        theme="grasslands",
        ground="#315d43",
        grid="#8eb46b20",
        wall="#805b38",
        wall_highlight="#c69a5d",
        hazard_color="#3b88a5",
        danger_color="#d4a440",
        obstacles=(
            Area("oak-west", 245, 150, 72, 56, "tree"),
            Area("oak-east", 650, 324, 72, 56, "tree"),
            Area("stone-north", 476, 92, 82, 42, "stone"),
            Area("stone-south", 390, 402, 82, 42, "stone"),
        ),
        hazards=(Area("pond", 74, 342, 122, 78, "water"),),
        danger_zones=(Area("brambles", 760, 128, 96, 62, "bramble"),),
        coin_spawns=(
            (90, 95), (190, 275), (360, 115), (440, 275),
            (575, 215), (785, 258), (845, 430), (280, 455),
            (620, 455), (510, 485), (70, 225), (870, 82),
        ),
        player_spawns=(
            (64, 64), (844, 64), (64, 444), (844, 444),
            (350, 214), (590, 214), (350, 334), (590, 334),
        ),
    ),
    "desert": ArenaMap(
        id="desert",
        name="Desert Ruins",
        description="Sun-baked ruins with broken pillars and shifting sand.",
        theme="desert",
        ground="#8b6638",
        grid="#f4d28c25",
        wall="#ad7741",
        wall_highlight="#e5bd71",
        hazard_color="#c65b36",
        danger_color="#d4a440",
        obstacles=(
            Area("pillar-west", 220, 115, 56, 76, "pillar"),
            Area("ruin-north", 432, 95, 104, 48, "ruin"),
            Area("pillar-east", 686, 145, 56, 76, "pillar"),
            Area("ruin-southwest", 350, 352, 104, 48, "ruin"),
            Area("pillar-south", 610, 370, 56, 76, "pillar"),
        ),
        hazards=(Area("hot-sands", 70, 325, 126, 76, "quicksand"),),
        danger_zones=(Area("cactus-patch", 780, 328, 100, 72, "cactus"),),
        coin_spawns=(
            (90, 90), (185, 245), (350, 92), (350, 260),
            (520, 205), (555, 295), (770, 95), (860, 260),
            (280, 455), (500, 460), (750, 460), (875, 455),
        ),
        player_spawns=(
            (66, 68), (850, 68), (66, 440), (850, 440),
            (320, 205), (610, 205), (320, 320), (610, 320),
        ),
    ),
    "neon": ArenaMap(
        id="neon",
        name="Neon Cyber Arena",
        description="A glowing grid of energy gates and unstable data fields.",
        theme="neon",
        ground="#142345",
        grid="#3aebf444",
        wall="#344d84",
        wall_highlight="#55e9ec",
        hazard_color="#f044b7",
        danger_color="#8c5cf6",
        obstacles=(
            Area("gate-nw", 250, 92, 96, 46, "gate"),
            Area("gate-ne", 614, 92, 96, 46, "gate"),
            Area("core-west", 160, 250, 64, 64, "core"),
            Area("core-east", 736, 250, 64, 64, "core"),
            Area("gate-sw", 250, 402, 96, 46, "gate"),
            Area("gate-se", 614, 402, 96, 46, "gate"),
        ),
        hazards=(Area("pulse-field", 423, 192, 114, 58, "energy"),),
        danger_zones=(Area("glitch-zone", 423, 302, 114, 58, "glitch"),),
        coin_spawns=(
            (90, 90), (190, 180), (390, 90), (560, 90),
            (850, 90), (285, 245), (480, 270), (675, 245),
            (90, 450), (390, 450), (560, 450), (850, 450),
        ),
        player_spawns=(
            (64, 64), (844, 64), (64, 444), (844, 444),
            (350, 180), (590, 180), (350, 354), (590, 354),
        ),
    ),
    "frozen": ArenaMap(
        id="frozen",
        name="Frozen Labyrinth",
        description="Icy corridors weave between crystal walls and cold vents.",
        theme="frozen",
        ground="#31556a",
        grid="#c4f3ff28",
        wall="#8ebaca",
        wall_highlight="#e0faff",
        hazard_color="#71d9ef",
        danger_color="#ad86f5",
        obstacles=(
            Area("ice-nw", 180, 96, 138, 42, "ice-wall"),
            Area("ice-ne", 642, 96, 138, 42, "ice-wall"),
            Area("ice-mid-west", 300, 205, 42, 128, "ice-wall"),
            Area("ice-mid-east", 618, 205, 42, 128, "ice-wall"),
            Area("ice-sw", 180, 402, 138, 42, "ice-wall"),
            Area("ice-se", 642, 402, 138, 42, "ice-wall"),
        ),
        hazards=(Area("frost-vent", 438, 78, 84, 62, "frost"),),
        danger_zones=(Area("thin-ice", 438, 400, 84, 60, "thin-ice"),),
        coin_spawns=(
            (90, 90), (380, 90), (580, 90), (850, 90),
            (90, 250), (250, 265), (480, 265), (710, 265),
            (870, 265), (90, 460), (380, 460), (850, 460),
        ),
        player_spawns=(
            (64, 64), (844, 64), (64, 444), (844, 444),
            (370, 160), (580, 160), (370, 350), (580, 350),
        ),
    ),
}


def get_map(map_id: str) -> ArenaMap | None:
    """Return a known map or None when the ID is invalid."""
    return MAPS.get(map_id)


def map_summaries() -> list[dict]:
    """Return the small list of choices needed by the lobby."""
    return [
        {
            "id": arena_map.id,
            "name": arena_map.name,
            "description": arena_map.description,
            "theme": arena_map.theme,
        }
        for arena_map in MAPS.values()
    ]


def rectangles_overlap(
    ax: float,
    ay: float,
    aw: float,
    ah: float,
    bx: float,
    by: float,
    bw: float,
    bh: float,
) -> bool:
    """Return whether two axis-aligned rectangles overlap."""
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def valid_spawn(arena_map: ArenaMap, x: float, y: float, player_size: float) -> bool:
    """Check arena bounds and keep a player spawn outside solid objects."""
    if x < 0 or y < 0 or x + player_size > ARENA_WIDTH or y + player_size > ARENA_HEIGHT:
        return False
    return not any(
        rectangles_overlap(
            x, y, player_size, player_size,
            area.x, area.y, area.width, area.height,
        )
        for area in arena_map.obstacles
    )