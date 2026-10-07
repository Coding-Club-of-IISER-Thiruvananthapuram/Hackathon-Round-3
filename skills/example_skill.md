# Deck Name: Royal Vanguard
# Player / Author: Team Champion
# War Cry: "Victory for the Crown!"

## Archetype & Playstyle
Fast-paced tempo and counter-assault. Control the bridges with disciplined defense, then launch decisive counter-pushes down the exposed flank.

## 8-Card Battle Deck
# Select exactly 8 cards from the catalog with percentage weights (must total 100%):
# Available Cards: Knight (3e), Archers (3e), Giant (5e), Musketeer (4e), Hog Rider (4e),
#                  Skeletons (2e), Baby Dragon (4e), P.E.K.K.A (7e), Fireball (4e), Goblin Barrel (3e)
- knight: 20%
- archers: 15%
- giant: 20%
- musketeer: 15%
- hog_rider: 15%
- skeletons: 5%
- baby_dragon: 5%
- fireball: 5%

## Preferred Lane
balanced (Options: "left", "right", or "balanced")

## Tactical Triggers (If-Then Rules)
# Define your autonomous commander's priority rules. These are evaluated in real-time each tick:
1. IF Elixir >= 7 -> Deploy primary tank (Giant or Hog Rider) to begin a push!
2. IF enemy drops a heavy tank -> Deploy Skeletons and Musketeer on that lane to defend!
3. IF enemy Princess Tower HP < 380 -> Cast Fireball directly onto the tower to claim the Crown!
4. IF enemy attacks left lane -> Counter-attack with Hog Rider on the opposite right lane!
