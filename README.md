# Clash Royale 1v1 Autonomous Arena

A deterministic simulation framework and competitive tournament arena inspired by *Clash Royale*. Teams program tactical heuristic logic and autonomous commander strategies to compete in head-to-head matches across a two-lane river battlefield.

---

## Table of Contents
1. [Hackathon Format & 1.5-Hour Tournament Protocol](#1-hackathon-format--15-hour-tournament-protocol)
2. [Architectural Overview & Battle Arena Engine](#2-architectural-overview--battle-arena-engine)
3. [Troop AI vs. Commander AI Hierarchy: Design Evaluation](#3-troop-ai-vs-commander-ai-hierarchy-design-evaluation)
4. [Skill File Specification & Syntax Reference](#4-skill-file-specification--syntax-reference)
5. [Core Combat Systems & Simulation Mechanics](#5-core-combat-systems--simulation-mechanics)
6. [Card Catalog & Combat Roster](#6-card-catalog--combat-roster)
7. [Participant Quick-Start & Local Testing Guide](#7-participant-quick-start--local-testing-guide)
8. [Tournament Bracket & Evaluation Rubric](#8-tournament-bracket--evaluation-rubric)

---

## 1. Hackathon Format & 1.5-Hour Tournament Protocol

### 1.1 Strict 90-Minute Development Lifecycle
To ensure maximum competitive intensity, creative problem-solving, and clean software architecture under pressure, each team is bound to a strict **90-minute (1.5-hour)** development window:

| Time Interval | Hackathon Phase | Team Objectives & Deliverables |
| :--- | :--- | :--- |
| **0:00 – 0:15** | **Phase 0: Discovery & Deck Drafting** | Clone repo, verify local environment via `./start_game.sh` and `unittest`. Select an archetype (Cycle, Beatdown, Bait, Control, Bridge Spam) and pick 8 cards totaling 100% deck weight. |
| **0:15 – 0:45** | **Phase 1: Heuristic & Rule Formulation** | Draft custom tactical triggers in `skills/<team_name>.md`. Program defensive reactions to heavy tanks, counter-attack timings, elixir thresholds, and lethal spell finishers. |
| **0:45 – 1:15** | **Phase 2: Sparring & Local Benchmarking** | Run local head-to-head scrimmages against benchmark bots (`hog_cycle.md`, `giant_beatdown.md`, `pekka_control.md`). Fine-tune card weights and trigger priorities. |
| **1:15 – 1:30** | **Phase 3: Code Freeze & Submission** | Run the verification test suite (`python -m unittest discover tests -v`). Validate skill schema via API/CLI. Submit the finalized `.md` dossier to the tournament coordinator. |

### 1.2 Rules of Engagement
1. **Zero Engine Modifications**: Participants are evaluated strictly on their tactical skill file (`skills/<team_name>.md`). Tampering with `engine/` or `server/` files disqualifies a team.
2. **Symmetric Execution**: Both Red and Blue commanders execute on the exact same deterministic simulation engine. Red and Blue battlefield coordinates are perfectly mirrored.
3. **No Direct Micro-Control**: All card deployments consume simulated Elixir. Troops operate autonomously once spawned.
4. **Execution Time Budget**: The Commander decision cycle executes on every 1.0-second macro tick. Commands must resolve synchronously or within 60ms to maintain real-time 60 FPS spectator rendering.

---

## 2. Architectural Overview & Battle Arena Engine

The arena employs a decoupled, three-tier architecture ensuring deterministic execution, high-concurrency match coordination, and fluid 60 FPS client visualization.

```
                                      +-------------------------------+
                                      |   Spectator Broadcast Client  |
                                      |  (HTML5 / Canvas 2D / WebAudio) |
                                      +---------------+---------------+
                                                      ^
                                                      | WebSocket Broadcast (JSON Delta Events)
                                                      v
                                      +---------------+---------------+
                                      |   FastAPI Match Orchestrator  |
                                      |  - Tick Scheduler (1.0s / 60Hz)|
                                      |  - Tournament Knockout State  |
                                      +-------+---------------+-------+
                                              |               |
                      +-----------------------+               +----------------------+
                      |                                                              |
                      v                                                              v
+---------------------+---------------------+          +---------------------+---------------------+
|        Red Autonomous Commander           |          |       Blue Autonomous Commander           |
|  - Skill Dossier (`skills/red.md`)        |          |  - Skill Dossier (`skills/blue.md`)       |
|  - Heuristic Priority Trigger Engine      |          |  - Heuristic Priority Trigger Engine      |
|  - (Optional) Local LLM qwen2.5:0.5b      |          |  - (Optional) Local LLM qwen2.5:0.5b      |
+---------------------+---------------------+          +---------------------+---------------------+
                      |                                                              |
                      +-----------------------+               +----------------------+
                                              |               | Macro Order {card, lane, thought}
                                              v               v
                                      +---------------+---------------+
                                      |    Deterministic Simulator    |
                                      |  - Elixir Economy (0-10, 2x)  |
                                      |  - Sub-tick Troop FSM Movement|
                                      |  - Targeting & Splash Damage  |
                                      |  - Princess & King Forts      |
                                      |  - 3-Crown Knockout Detector  |
                                      +-------------------------------+
```

### Core Subsystems:
1. **Deterministic Simulator (`engine/battle_simulator.py`)**:
   - Maintains authoritative game state $S_t$.
   - Executes pure state transitions: $S_{t+1} = f(S_t, \text{Order}_{\text{red}}, \text{Order}_{\text{blue}}, \Delta t)$.
   - Resolves troop marching, projectile travel, collision distances, tower aggro, and crown destructions.
2. **Unified Commander AI Engine (`engine/llm_commander.py` & `engine/skill_loader.py`)**:
   - Both teams interface with the exact same AI harness.
   - Evaluates natural-language and rule-based triggers in priority sequence.
   - Supports dual-mode operation: ultra-fast zero-dependency heuristic evaluation (<1ms) or local LLM inference via Ollama (`qwen2.5:0.5b`).
3. **Spectator & Broadcast Server (`server/app.py`)**:
   - FastAPI server streaming 60Hz tick payloads over WebSockets.
   - Zero external frontend dependencies: self-contained Canvas 2D renderer with directional particle systems, floating damage counters, dynamic health bars, sound synthesis, and real-time caster play-by-play.

---

## 3. Troop AI vs. Commander AI Hierarchy: Design Evaluation

A central architectural decision in designing this hackathon challenge is establishing the separation of concerns between the **Commander AI** and individual **Troop AI**.

### 3.1 Architectural Trade-Off Analysis

| Evaluation Vector | Option A: Micro-Steering Commander (Troops receive frame-by-frame direct orders) | Option B: Macro Commander + Autonomous Troop FSM (Troops run local deterministic state machines) |
| :--- | :--- | :--- |
| **Hackathon Feasibility (90-min limit)** | **Unviable**: Teams spend 80+ minutes wrestling with steering math, obstacle avoidance, collision jitter, and edge-case exceptions. | **Optimal**: Teams focus 100% on high-level strategy, card synergy, elixir trades, and macro counter-play. |
| **Compute & Latency Budget** | Scales as $O(N)$ with active unit count. Massive tick latency, desyncs, and frame stutter. | Constant $O(1)$ macro decision per tick. Sub-millisecond execution ensures seamless 60 FPS broadcast. |
| **Game Balance & Rock-Paper-Scissors** | **Broken**: Micro-steering enables artificial kiting where slow tanks or swarms exploit pathing flaws to avoid towers or splash. | **Preserved**: Authentic *Clash Royale* mechanics: Giants strictly target buildings; Pekkas attack nearest threats; Dragon deals splash. |
| **Simulation Determinism** | High risk of asynchronous race conditions and non-deterministic pathing divergence. | 100% deterministic state progression. Matches can be accurately replayed and verified. |

### 3.2 Formal Design Decision: Autonomous Troop Finite State Machine
**We decisively adopt Option B.** The Commander AI acts strictly as the macro battlefield general (handling resource management, card selection, lane assignment, and timing), while each deployed troop executes an autonomous, rigid, local Finite State Machine:

```
                  +-------------------------+
                  |         SPAWN           |  (Deployed at lane bridgehead / base)
                  +------------+------------+
                               |
                               v
                  +-------------------------+
    +------------>|         MARCH           |<-----------+
    |             | (Move down lane Y-axis) |            |
    |             +------------+------------+            |
    |                          |                         |
    |    Target moves/dies     | Enemy in range          | Target dies
    |                          v                         |
    |             +-------------------------+            |
    +-------------+         ACQUIRE         |            |
                  |  - Siege: Towers Only   |            |
                  |  - Combat: Nearest Unit |            |
                  +------------+------------+            |
                               |                         |
                               v                         |
                  +-------------------------+            |
                  |         ATTACK          |------------+
                  | (Inflict Dmg / Splash)  |
                  +------------+------------+
                               |
                               | HP <= 0
                               v
                  +-------------------------+
                  |          DEATH          |  (Triggers particle event & award kill stat)
                  +-------------------------+
```

* **Troop Scope**: Local awareness only. Measures distance along the assigned lane axis to enemies and fortifications.
* **Commander Scope**: Global battlefield awareness. Reads elixir differential, active lane threat balance, tower health levels, and opponent card rotation.

---

## 4. Skill File Specification & Syntax Reference

Participants configure their Autonomous Commander by creating a clean Markdown file in the `skills/` directory (e.g., `skills/my_team.md`).

### 4.1 Schema Definition

A valid skill file must contain the following sections:

```markdown
# Deck Name: <Kingdom / Commander Title>
# Player / Author: <Team Name>
# War Cry: "<Short Custom Battle Cry>"

## Archetype & Playstyle
<Brief description of strategic doctrine: cycle, beatdown, spell_bait, pekka_control, or bridge_spam>

## 8-Card Battle Deck
- <card_id_1>: <weight_percentage>%
- <card_id_2>: <weight_percentage>%
- <card_id_3>: <weight_percentage>%
- <card_id_4>: <weight_percentage>%
- <card_id_5>: <weight_percentage>%
- <card_id_6>: <weight_percentage>%
- <card_id_7>: <weight_percentage>%
- <card_id_8>: <weight_percentage>%

## Preferred Lane
<"left", "right", or "balanced">

## Tactical Triggers (If-Then Rules)
1. IF <Condition> -> <Action>!
2. IF <Condition> -> <Action>!
3. IF <Condition> -> <Action>!
4. IF <Condition> -> <Action>!
```

### 4.2 Tactical Trigger Syntax & Grammar

Tactical triggers are evaluated in top-to-bottom priority order every simulation tick. If a trigger's condition matches and the commander has sufficient elixir, the action fires immediately.

#### Supported Conditions:
* **Resource Thresholds**: `Elixir >= <N>` (e.g., `Elixir >= 7`, `Elixir is at least 4`)
* **Enemy Threat Detection**:
  * `enemy deploys <card>` / `enemy drops <card>` (e.g., `Giant`, `Pekka`, `Hog`, `Skeletons`)
  * `enemy tank` / `heavy tank` (detects Giant, Pekka, or Hog Rider)
  * `enemy swarm` (detects Skeleton Army or Archers)
* **Tower Health Triggers**: `enemy Princess Tower HP < <N>` (e.g., `enemy Princess Tower HP < 380`)
* **Lane Dynamics**:
  * `lane is clear` / `open lane` (no defending enemy troops present)
  * `enemy attacks left lane` / `enemy on right lane`

#### Supported Actions:
* **Card Deployment**: `Deploy <Card_Name>` / `Drop <Card_Name>` (e.g., `Drop P.E.K.K.A immediately!`, `Deploy Hog Rider`)
* **Lane Routing**:
  * `on left lane` / `on right lane`
  * `on the bridge`
  * `on opposite lane` / `counter opposite` (punishes the uncommitted flank)

---

### 4.3 Reference Implementation: Tournament Skill Dossier

```markdown
# Deck Name: Thunder Peak Control
# Player / Author: Team Apex
# War Cry: "Lightning striking twice!"

## Archetype & Playstyle
Defensive control transition. Absorb enemy tanks with heavy single-target counters, then counter-attack with support units down the opposite lane.

## 8-Card Battle Deck
- pekka: 30%
- musketeer: 20%
- knight: 15%
- fireball: 10%
- skeletons: 10%
- archers: 10%
- baby_dragon: 5%
- goblin_barrel: 0%

## Preferred Lane
balanced

## Tactical Triggers (If-Then Rules)
1. IF enemy deploys Giant or Hog -> Drop P.E.K.K.A immediately!
2. IF enemy Princess Tower HP < 380 -> Cast Fireball directly onto tower for Crown!
3. IF enemy drops swarm -> Deploy Baby Dragon on that lane!
4. IF Elixir >= 8 and lane is clear -> Deploy Knight with Musketeer behind!
```

---

## 5. Core Combat Systems & Simulation Mechanics

### 5.1 Battlefield Geometry & Coordinate System
* **Dimensions**: 2D coordinate space normalized from $X=0.0$ to $100.0$, and $Y=0.0$ to $100.0$.
* **River & Bridges**:
  * Central River spans across $Y = 50.0$.
  * Left Bridge is centered at $X = 25.0$.
  * Right Bridge is centered at $X = 75.0$.
* **Fortifications**:
  * **Red King Tower**: Centered at $(50.0, 10.0)$.
  * **Red Left Princess Tower**: Located at $(25.0, 20.0)$.
  * **Red Right Princess Tower**: Located at $(75.0, 20.0)$.
  * **Blue King Tower**: Centered at $(50.0, 90.0)$.
  * **Blue Left Princess Tower**: Located at $(25.0, 80.0)$.
  * **Blue Right Princess Tower**: Located at $(75.0, 80.0)$.

### 5.2 Deployment Zones & Territory Expansion
* **Standard Territory**:
  * Red may spawn units between $Y = 15.0$ and $Y = 48.0$.
  * Blue may spawn units between $Y = 52.0$ and $Y = 85.0$.
* **Deep Flank Breakthrough**: Destroying an enemy Princess Tower unlocks forward bridgehead deployment:
  * If Red destroys Blue's Left Princess Tower, Red can deploy units forward up to $Y = 52.0$ on that lane.
  * If Blue destroys Red's Princess Tower, Blue can deploy units forward up to $Y = 48.0$.

### 5.3 Elixir Economy
* **Capacity**: $0.0$ to $10.0$ Elixir (starting at $5.0$).
* **Standard Generation Rate**: $+0.5$ Elixir/second ($+1.0$ Elixir every 2.0s).
* **Double Elixir Phase**: Activates automatically when the match clock reaches $120$ seconds (final 60s of regulation) or during sudden-death overtime ($+1.0$ Elixir/second).

### 5.4 Combat & Targeting Mechanics
* **Target Categories**:
  * `all`: Engages the nearest enemy troop in the active lane within range; if no troops are present, attacks the nearest enemy fortification.
  * `buildings`: Ignores all enemy troops and marches directly toward the lane's Crown Tower or King Tower (e.g., Giant, Hog Rider).
* **Tower Aggro & King Activation**:
  * Princess Towers automatically engage the closest enemy unit in their lane sector (Range: $18.0$ units, Damage: $85$).
  * The King Tower (Range: $16.0$ units, Damage: $110$) remains **dormant** at match start. It activates and opens fire only when damaged directly or when an allied Princess Tower collapses.
* **Spell Resolution**:
  * **Fireball**: Deals instant $380$ damage to troops in radius, and reduced $130$ damage against Crown Towers (preventing cheap spell turtling).
  * **Goblin Barrel**: Flings 3 Dagger Goblins directly onto the enemy Crown Tower.

### 5.5 Determinism & Replayability
* The simulation engine avoids unseeded random calls during combat resolution.
* Troop movement, collision boundaries, and projectile flights are calculated using fixed time steps ($\Delta t = 1.0\text{s}$).
* Every match produces a signed, sequential event stream log, enabling exact offline replay and auditability.

---

## 6. Card Catalog & Combat Roster

Each team drafts exactly 8 cards from the catalog of 10 iconic archetypes:

| Card Key | Name | Elixir | Type | HP | Dmg | Speed | Range | Target | Tactical Role |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `knight` | **Knight** | 3 | Troop | 850 | 95 | 8.0 | 3.0 (Melee) | All | Resilient frontline brawler. Anchors defense and transitions into counter-pushes. |
| `archers` | **Archers** | 3 | Troop (x2) | 280 | 55 | 8.0 | 16.0 (Ranged)| All | Dual sharpshooters. 110 combined DPS from safe distance behind tanks. |
| `giant` | **Giant** | 5 | Siege Tank | 2200 | 110 | 5.0 | 3.5 (Melee) | Buildings | Colossal health pool. Absorbs tower fire while marching straight for crowns. |
| `musketeer`| **Musketeer** | 4 | Sniper | 420 | 120 | 7.5 | 18.0 (Sniper)| All | Long-range boomstick. Shreds incoming tanks from behind friendly bridges. |
| `hog_rider`| **Hog Rider** | 4 | Rusher | 750 | 120 | 13.0 | 3.0 (Melee) | Buildings | Fast hammer rusher. Deals burst chip damage to towers; punished by swarms. |
| `skeletons`| **Skeleton Army**| 2 | Swarm (x4)| 65 | 50 | 11.0 | 2.5 (Melee) | All | Bony distraction swarm (200 DPS). Overwhelms heavy single-target tanks. |
| `baby_dragon`| **Baby Dragon**| 4 | Splash | 800 | 85 | 9.5 | 12.0 (Splash)| All | Flying unit. Spits area-of-effect fireballs that vaporize enemy swarms. |
| `pekka` | **P.E.K.K.A** | 7 | Heavy Armor| 2600 | 420 | 4.5 | 3.0 (Melee) | All | Colossal single-strike tank destroyer (2-shots Hog). Devastates bridge pushes. |
| `fireball` | **Fireball** | 4 | Direct Spell| - | 360 | Instant| 15.0 Radius | Direct | Area spell strike (120 tower damage). Eliminates troop clusters. |
| `goblin_barrel`| **Goblin Barrel**| 3 | Flank Spell | 100 | 60 | Instant| Tower Spawn | Surprise | Direct assault (3 goblins). Launches 3 dagger goblins onto enemy Princess Tower. |

### 6.1 Card ID Quick Reference (Copy-Paste for Skill Files)
Use these exact card IDs when building your 8-card roster in your `skills/<team>.md` file:

```markdown
- knight          # Knight (3 Elixir)
- archers         # Archers (3 Elixir)
- giant           # Giant (5 Elixir)
- musketeer       # Musketeer (4 Elixir)
- hog_rider       # Hog Rider (4 Elixir)
- skeletons       # Skeleton Army (2 Elixir)
- baby_dragon     # Baby Dragon (4 Elixir)
- pekka           # P.E.K.K.A (7 Elixir)
- fireball        # Fireball (4 Elixir)
- goblin_barrel   # Goblin Barrel (3 Elixir)
```

---

## 7. Participant Quick-Start & Local Testing Guide

### 7.1 Installation & Launch

#### GitHub Codespaces (In-Browser):
1. On GitHub, click **Code** -> **Codespaces** -> **Create codespace on main**.
2. Run the startup script in the terminal:
   ```bash
   ./start_codespace.sh
   ```
3. In the **Ports** panel, right-click port `8000` and set **Port Visibility** to **Public**, then open the link in your browser.

#### Linux / macOS:
```bash
# 1. Clone repository and navigate to directory
git clone <repo-url> clash-hackathon && cd clash-hackathon

# 2. Launch arena
./start_game.sh
```

#### Windows:
```cmd
start_game.bat
```

The web dashboard is hosted at: **`http://localhost:8000`**

---

### 7.2 Running the Automated Verification Suite
Verify your engine and skill parsing with the 16-point automated test suite:

```bash
.venv/bin/python -m unittest discover tests -v
```

Expected output:
```
test_01_initial_arena_state ... ok
test_02_elixir_and_card_deployment ... ok
test_03_troop_movement_across_bridges ... ok
test_04_tower_attacks_and_princess_fall ... ok
test_05_instant_3_crown_ko ... ok
test_06_fireball_spell_direct_strike ... ok
test_07_double_elixir_activation ... ok
test_08_deck_and_skill_parsing ... ok
test_09_tournament_bracket_progression ... ok
test_10_server_api_health_and_skills ... ok
test_11_skill_file_custom_trigger_execution ... ok
test_12_deck_roster_adherence ... ok
test_13_diagonal_king_pathing ... ok
test_14_tower_physical_collision_buffer ... ok
test_15_naked_hog_balance_cannot_solo_kill_tower ... ok
test_16_defending_troops_intercept_combat_attackers ... ok

----------------------------------------------------------------------
Ran 16 tests in 0.015s

OK
```

---

### 7.3 Step-by-Step Guide to Creating Your Custom Skill

1. Duplicate the starter template:
   ```bash
   cp skills/template_skill.md skills/my_team.md
   ```
2. Edit `skills/my_team.md`:
   - Set your **Deck Name**, **Player/Author**, and **War Cry**.
   - Configure your 8-card roster and adjust weights so they sum to **100%**.
   - Write your **Tactical Triggers** using the syntax defined in Section 4.
3. Validate your file via the local API:
   ```bash
   curl -X POST http://localhost:8000/api/skills/validate \
     -H "Content-Type: application/json" \
     -d "{\"content\": \"$(cat skills/my_team.md | sed 's/"/\\"/g' | awk '{printf "%s\\n", $0}')\"}"
   ```
4. Test your commander in a live scrimmage against a benchmark deck in the Web UI:
   - Navigate to `http://localhost:8000`
   - In **Match Setup**, select `my_team.md` as **Blue** and `hog_cycle.md` as **Red**.
   - Click **Start Match** and inspect the Caster Play-by-Play log!

---

## 8. Tournament Bracket & Evaluation Rubric

### 8.1 Single-Elimination Tournament Format
Matches are conducted under official tournament conditions:
* **Regulation Time**: 180 seconds (3 minutes).
* **Double Elixir Phase**: Begins at $T = 120\text{s}$ (60s remaining).
* **Sudden Death Overtime**: If crowns are tied at $180$ seconds, a 60-second overtime begins. The first kingdom to take down any enemy tower wins immediately.
* **Tiebreaker**: If overtime expires with equal crowns, the player whose lowest-HP tower has more health remaining is awarded victory.
* **3-Crown Knockout**: Shattering the enemy King Tower results in an instant 3-0 knockout finish.

### 8.2 Evaluation & Scoring Rubric

Each team is scored across four key pillars:

```
+--------------------------------------------------------------------------+
|                        HACKATHON EVALUATION RUBRIC                       |
+------------------------------------+-------------------------------------+
| Criterion                          | Weight | Key Assessment Points      |
+------------------------------------+-------------------------------------+
| 1. Win Rate & Crown Differential   |  40%   | - Tournament match wins    |
|                                    |        | - Towers destroyed vs lost |
|                                    |        | - 3-Crown KO finishes      |
+------------------------------------+-------------------------------------+
| 2. Elixir Economics & Counter-Play |  25%   | - Positive elixir trades   |
|                                    |        | - Tank counters (PEKKA/Skel)|
|                                    |        | - Anti-swarm splash timing |
+------------------------------------+-------------------------------------+
| 3. Trigger Robustness & Logic Edge |  20%   | - Zero wasted deployments  |
|                                    |        | - Defensive lane awareness |
|                                    |        | - Decisive lethal finishers|
+------------------------------------+-------------------------------------+
| 4. Strategic Dossier & Presentation|  15%   | - Well-crafted skill .md   |
|                                    |        | - Clear doctrine & war cry |
|                                    |        | - Cohesive deck identity   |
+------------------------------------+-------------------------------------+
```

---

## License & Credits
Built for competitive autonomous AI esports tournaments. Inspired by Supercell's *Clash Royale*.
Licensed under the MIT License.
