"""
Configuration parameters for AI Clash Royale: 1v1 Autonomous Tower Arena.
Includes 2-lane bridge arena layout, King and Princess towers, 0-10 Elixir economy,
and full Card Catalog (troops, tanks, swarms, and spells).
"""
from typing import Dict, Any

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:0.5b"
DEFAULT_MATCH_DURATION_SECONDS = 180  # 3 minutes standard match
DEFAULT_TICK_INTERVAL_SECONDS = 1.0   # 1 second simulation ticks

# Arena Dimensions
LANE_LENGTH = 100.0  # Normalized 0 (Red King) to 100 (Blue King)
RIVER_Y = 50.0       # River divides the arena at 50%
LEFT_LANE_X = 25.0   # Left Bridge X coordinate
RIGHT_LANE_X = 75.0  # Right Bridge X coordinate

# Elixir Economy
MAX_ELIXIR = 10.0
STARTING_ELIXIR = 5.0
NORMAL_ELIXIR_RATE = 0.5  # 1 elixir every 2.0s
DOUBLE_ELIXIR_RATE = 1.0  # 1 elixir every 1.0s (during last 60s & overtime)
DOUBLE_ELIXIR_THRESHOLD_SECONDS = 120.0  # Triggers at 2 minutes elapsed

# Tower Stats
PRINCESS_TOWER_MAX_HP = 1400
KING_TOWER_MAX_HP = 2400
PRINCESS_TOWER_DAMAGE = 115   # Balanced from 85 to command bridge approach
KING_TOWER_DAMAGE = 145       # Balanced from 110 to punish naked tower rushes
PRINCESS_TOWER_RANGE = 26.0   # Covers river crossing from bridgehead
KING_TOWER_RANGE = 22.0       # Commands inner court
PRINCESS_TOWER_RADIUS = 4.5   # Physical collision radius to prevent clipping inside tower
KING_TOWER_RADIUS = 7.0       # Physical collision radius for King Keep fortress

# Card Catalog (Iconic Clash Royale Archetypes)
CARD_CATALOG: Dict[str, Dict[str, Any]] = {
    "knight": {
        "id": "knight",
        "name": "Knight",
        "elixir": 3,
        "type": "troop",
        "hp": 850,
        "damage": 95,
        "speed": 8.0,        # Lane distance per tick
        "range": 3.0,        # Melee
        "target": "all",     # Targets nearest enemy troop or tower
        "icon": "🗡️",
        "description": "Tough melee brawler. Excellent all-around defense and counter-push."
    },
    "archers": {
        "id": "archers",
        "name": "Archers",
        "elixir": 3,
        "type": "troop",
        "hp": 280,
        "damage": 55,
        "speed": 8.0,
        "range": 16.0,       # Ranged
        "target": "all",
        "count": 2,          # Spawns a pair (110 combined DPS)
        "icon": "🏹",
        "description": "Pair of sharpshooters. Snipes ground and air threats from safe distance."
    },
    "giant": {
        "id": "giant",
        "name": "Giant",
        "elixir": 5,
        "type": "troop",
        "hp": 2200,
        "damage": 110,
        "speed": 5.0,        # Slow steady march
        "range": 3.5,
        "target": "buildings",  # ONLY targets Towers! Ignores troops!
        "icon": "🗿",
        "description": "Colossal siege tank that marches straight for enemy towers, ignoring distractions."
    },
    "musketeer": {
        "id": "musketeer",
        "name": "Musketeer",
        "elixir": 4,
        "type": "troop",
        "hp": 420,
        "damage": 120,
        "speed": 7.5,
        "range": 18.0,       # Extreme range
        "target": "all",
        "icon": "🔫",
        "description": "Long-range boomstick specialist. Shreds incoming tanks from behind friendly lines."
    },
    "hog_rider": {
        "id": "hog_rider",
        "name": "Hog Rider",
        "elixir": 4,
        "type": "troop",
        "hp": 750,           # Rebalanced from 1100 to prevent solo-killing towers
        "damage": 120,       # Rebalanced from 170 to match 4-elixir investment
        "speed": 13.0,       # Fast bridge pressure, balanced from 18.0
        "range": 3.0,
        "target": "buildings",  # ONLY targets Towers!
        "icon": "🐗",
        "description": "Fast hammer-wielding tower rusher. Charges the crown tower for burst chip damage!"
    },
    "skeletons": {
        "id": "skeletons",
        "name": "Skeleton Army",
        "elixir": 2,
        "type": "troop",
        "hp": 65,
        "damage": 50,
        "speed": 11.0,
        "range": 2.5,
        "target": "all",
        "count": 4,          # Swarm of 4 (200 combined DPS, hard-counters single tanks)
        "icon": "💀",
        "description": "Bony distraction swarm. Overwhelms single-target tanks like Giant and Hog Rider."
    },
    "baby_dragon": {
        "id": "baby_dragon",
        "name": "Baby Dragon",
        "elixir": 4,
        "type": "troop",
        "hp": 800,
        "damage": 85,
        "speed": 9.5,
        "range": 12.0,
        "splash": True,      # Hits all targets in radius, hard-counters swarm
        "target": "all",
        "icon": "🐲",
        "description": "Flying splash-damage dragon. Spits fireballs that vaporize swarms."
    },
    "pekka": {
        "id": "pekka",
        "name": "P.E.K.K.A",
        "elixir": 7,
        "type": "troop",
        "hp": 2600,
        "damage": 420,       # 2-shots Hog Rider, 6-shots Giant
        "speed": 4.5,
        "range": 3.0,
        "target": "all",
        "icon": "🤖",
        "description": "Heavily armored mechanical beast. Obliterates tanks with catastrophic sword strikes."
    },
    "fireball": {
        "id": "fireball",
        "name": "Fireball",
        "elixir": 4,
        "type": "spell",
        "damage": 360,       # Eliminates clustered support troops
        "tower_damage": 120, # Reduced crown tower damage
        "radius": 15.0,
        "icon": "🔥",
        "description": "Incinerates enemy troop clusters or finishes off damaged Crown Towers."
    },
    "goblin_barrel": {
        "id": "goblin_barrel",
        "name": "Goblin Barrel",
        "elixir": 3,
        "type": "spell",
        "hp": 100,
        "damage": 60,
        "speed": 11.0,
        "range": 3.0,
        "target": "all",
        "count": 3,
        "icon": "🪵",
        "description": "Direct tower assault. Launches 3 dagger goblins right onto the enemy Princess Tower!"
    }
}
