# 3D Voxel Sandbox — Python & OpenGL Minecraft Clone

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Pyglet](https://img.shields.io/badge/Pyglet-OpenGL%203.3%2B-success)
![GLSL](https://img.shields.io/badge/Shaders-GLSL%20330-orange)

A full-featured 3D voxel sandbox game inspired by **Minecraft Java Edition**, built from scratch in Python using **Pyglet** and modern **OpenGL 3.3+ / GLSL Shaders**. It features multi-threaded procedural terrain generation across three dimensions, dual lighting & shader pipelines, an 8-phase lunar cycle, 15 animated mob types including the Ender Dragon boss fight, generated structures, crafting, smelting, farming, enchanting, and an in-game command console.

---

## Table of Contents

- [Features](#features)
  - [Procedural World Generation & Biomes](#1-procedural-world-generation--biomes)
  - [Three Playable Dimensions](#2-three-playable-dimensions)
  - [Dual Graphics & Lighting Engine](#3-dual-graphics--lighting-engine)
  - [8-Phase Lunar Cycle & New Moon Mechanics](#4-8-phase-lunar-cycle--new-moon-mechanics)
  - [Entities, Mob AI & Boss Combat](#5-entities-mob-ai--boss-combat)
  - [Procedural Structures & Monster Spawners](#6-procedural-structures--monster-spawners)
  - [Survival, Crafting, Enchanting & Farming](#7-survival-crafting-enchanting--farming)
- [Installation & Quick Start](#installation--quick-start)
- [Controls & Keybindings](#controls--keybindings)
- [In-Game Command Reference](#in-game-command-reference)
- [Project Structure](#project-structure)

---

## Features

### 1. Procedural World Generation & Biomes
- **Continuous Climate Blending**: Uses 2D/3D Perlin noise temperature and moisture maps to smoothly blend terrain heights and surface blocks across **10 distinct biomes**:
  - *Plains, Forest, Birch Forest, Spruce Taiga, Jungle, Savanna, Desert, Snow Forest, Windswept Hills,* and *Extreme Mountains*.
- **Subterranean Generation**: Carves 3D cave tunnels, large underground chambers, and surface ravines, populated with water/lava aquifers and depth-stratified ore veins (*Coal, Iron, Gold, Diamond, Redstone, Lapis Lazuli, Emerald,* and *Nether Quartz*).
- **Six Complete Wood Families**: *Oak, Birch, Spruce, Jungle, Acacia,* and *Dark Oak* — each with matching logs, planks, leaves, saplings, slabs, stairs, doors, trapdoors, fences, and fence gates.
- **Multiprocess Chunk Streaming**: Asynchronous background chunk generation and section meshing keep frame rates smooth while exploring new terrain.

### 2. Three Playable Dimensions
- **The Overworld**: Features a 20-minute day/night cycle (`1200s`), dynamic weather/sky coloring, volumetric 3D clouds, villages, underground dungeons, and strongholds.
- **The Nether**: Accessible by building an **Obsidian Portal frame** and igniting it with **Flint and Steel**. Features Nether Wastes terrain, lava seas, Glowstone clusters, Soul Sand, Nether Quartz ore, and **Nether Fortresses**.
- **The End**: Accessible by locating an underground **Stronghold**, slotting **Eyes of Ender** into the End Portal frames, and jumping into the activated starfield portal. Features the main End island, Obsidian Pillars with caged and uncaged End Crystals, the **Ender Dragon** boss encounter, and the central Bedrock Exit Fountain.

### 3. Dual Graphics & Lighting Engine
Switch seamlessly at any time via **Pause Menu → Settings → Lighting Mode**:
- **Block Mode (Classic)**:
  - 3D Breadth-First Search (BFS) flood-fill sky light and block light propagation (`0–15`) with smooth per-vertex ambient occlusion.
  - Textured rotating Sun and 8-phase Moon quads with 3D volumetric clouds.
- **Shader Mode (Photorealistic GLSL)**:
  - Custom atmospheric Rayleigh/Mie scattering sky dome with procedural stars, realistic 8-phase lunar surface shading, and an End dimension deep-space nebula skybox.
  - Real-time **directional terrain shadow mapping** (cast by mountains, trees, and structures) and **entity ground shadows**.
  - Animated water waves with screen-space reflections/refractions, emissive lava & spawner glow, and wind-swaying foliage.

### 4. 8-Phase Lunar Cycle & New Moon Mechanics
- Each night advances the moon through **8 authentic lunar phases** in both **Block** and **Shader** modes:
  1. `Full Moon` (100% night illumination)
  2. `Waning Gibbous` (75%)
  3. `Third Quarter` (50%)
  4. `Waning Crescent` (25%)
  5. `New Moon` (5% night illumination)
  6. `Waxing Crescent` (25%)
  7. `First Quarter` (50%)
  8. `Waxing Gibbous` (75%)
- **New Moon Hostile Empowerment**: During a **New Moon** (`Phase 4`), Overworld hostile mobs spawn with a lunar buff granting **+25% max health**, **1.3× attack damage**, and **1.2× movement speed**.

### 5. Entities, Mob AI & Boss Combat
- **Passive Mobs**: *Cow, Pig, Sheep, Chicken* with wandering AI and resource drops.
- **Overworld Hostile Mobs**:
  - *Zombie* (melee pursuit & sunlight burning)
  - *Skeleton* (ranged bow & arrow combat)
  - *Spider* (wall climbing & leap attacks)
  - *Creeper* (proximity fuse hiss & terrain-destroying explosions)
  - *Enderman* (provoked by direct eye contact or attacks; teleports and dodges projectiles)
  - *Silverfish* (spawns from Stronghold spawners and broken Infested Stone blocks)
- **Nether Mobs**:
  - *Zombie Pigman* (neutral unless attacked; triggers group aggro)
  - *Blaze* (hovers and fires 3-round fireball volleys)
  - *Ghast* (aerial mob that shoots deflectable explosive fireballs)
  - *Magma Cube* (jumping slimes that split into smaller cubes upon death)
- **The Ender Dragon Boss**:
  - Full boss health bar, End Crystal healing beams, circling/strafing flight patterns, purple Dragon Fireball breath attacks, central fountain perching phase, and XP/exit portal activation upon defeat.

### 6. Procedural Structures & Monster Spawners
- **Villages**: Generate in Plains, Desert, and Savanna biomes with houses, blacksmiths (containing loot chests), wells, lamps, and crop farms.
- **Dungeons**: Underground mossy cobblestone rooms containing loot chests and active **Monster Spawners**.
- **Strongholds**: Multi-room underground stone-brick complexes with libraries, iron prison doors, chests, and the End Portal chamber.
- **Nether Fortresses**: Elevated Nether Brick bridges, corridors, loot chests, and Blaze spawner decks.
- **Interactive Monster Spawners**: Render a spinning miniature 3D mob and flame particles inside the cage, display a HUD tooltip when looked at, and can be reconfigured in Creative/Survival by right-clicking with mob drop items.

### 7. Survival, Crafting, Enchanting & Farming
- **Survival Systems**: Health & armor rating bar, hunger & saturation mechanics, XP levels & orbs, fall damage, drowning/oxygen bubbles, fire & lava damage, and status buffs (*Golden Apple* & *Enchanted Golden Apple*).
- **Crafting & Smelting**:
  - `2×2` Player Inventory crafting grid and `3×3` **Crafting Table** interface.
  - **Furnace** block with fuel consumption, smelting progress indicator, and persistent state per dimension.
- **Enchanting Table & Bookshelves**:
  - Surround an **Enchanting Table** with up to **15 Bookshelves** to unlock up to Level 30 enchantments using XP and Lapis Lazuli.
  - Supports **10 enchantments**: *Protection (I–IV), Sharpness (I–V), Efficiency (I–V), Power (I–V), Fire Aspect (I–II), Infinity (I), Fortune (I–III), Looting (I–III), Unbreaking (I–III),* and *Silk Touch (I)*.
- **Farming & Utility Blocks**:
  - Till dirt/grass with Hoes into **Farmland** (hydrates near water), plant *Wheat, Carrots, Potatoes, Pumpkins, Melons,* and *Sugar Cane*, and accelerate growth with **Bone Meal** (also grows all 6 sapling types into full trees).
  - **Beds** set your respawn point and skip the night in the Overworld (or detonate with a Power 5.0 explosion if used in the Nether or End).
  - **TNT** can be primed with Flint and Steel or caught in chain-reaction explosions.
  - **Projectiles**: Chargeable Bow & Arrows, throwable Ender Pearls (teleports on impact), Eyes of Ender (flies toward the nearest Stronghold), and Bottles o' Enchanting.

---

## Installation & Quick Start

### Prerequisites
- **Python 3.10+** (64-bit recommended)
- A graphics card supporting **OpenGL 3.3 Core Profile** or higher

### 1. Clone the Repository
```bash
git clone <repository-url>
cd tp
```

### 2. Install Dependencies
The game only requires `pyglet` (all noise generation, math, and shaders are self-contained):
```bash
pip install pyglet
```

### 3. Launch the Game
Run `main.py` directly with Python:
```bash
python main.py
```
*(On Windows, you can also run `start.bat`.)*

---

## Controls & Keybindings

| Key / Input | Action |
| :--- | :--- |
| **`W` `A` `S` `D`** | Move Forward, Strafe Left, Backward, Strafe Right |
| **`Space`** | Jump / Swim Up / Fly Up (in Creative Flight mode) |
| **`Left Shift`** | Sneak (prevents walking off block edges) / Fly Down |
| **`Left Ctrl`** | Sprint |
| **`Left Mouse Click`** | Attack Entity / Hold to Mine Block |
| **`Right Mouse Click`** | Place Block / Use Item (Eat, Draw Bow, Throw Pearl, Till, Open Chest/Table/Furnace/Door) |
| **`Middle Mouse Click`** | Pick Block (selects targeted block into hotbar) |
| **`1` – `9` / Scroll Wheel** | Select Hotbar Slot |
| **`E`** | Open / Close Inventory (Survival Inventory or searchable Creative Menu) |
| **`Q`** | Drop 1 Item from active slot (`Ctrl + Q` drops the entire stack) |
| **`F`** | Toggle **Creative / Flight Mode** (infinite items, flight, no damage, enables `/` commands) |
| **`F3`** | Toggle Debug Overlay (FPS, XYZ, Chunk, Light levels, Biome, Temperature/Moisture) |
| **`F5`** | Cycle Camera Perspective (*First-Person → Third-Person Back → Third-Person Front* with 3D Steve model) |
| **`/` (Slash)** | Open In-Game Command Console *(requires Creative Mode `F`)* |
| **`R`** | Reset Player Position to World Origin `(0, 80, 0)` |
| **`Esc`** | Close active GUI / Open Pause & Settings Menu (Auto-saves world on quit) |

---

## In-Game Command Reference

When **Creative Mode (`F`)** is active, press **`/`** to open the command bar. Use **`Up` / `Down`** arrows to cycle through command history and **`Enter`** to execute.

### 1. Teleport (`/tp`)
Teleport to absolute coordinates, relative tilde (`~`) coordinates, across dimensions, or back to your last death location:
```text
/tp                                    # Teleport to last death location (or world spawn)
/tp <x> <y> <z>                        # Teleport in current dimension (e.g., /tp 150 72 -200)
/tp ~10 ~5 ~-15                        # Relative teleport from current position
/tp <x> <y> <z> <overworld|nether|end> # Cross-dimension teleport (e.g., /tp 0 70 0 end)
```

### 2. Locate Structures (`/locate`)
Mathematically locates the nearest structure in the current dimension in `<0.1 ms` without needing to load chunks:
```text
/locate village        # Overworld: Closest Village
/locate stronghold     # Overworld: Closest Stronghold (End Portal room)
/locate dungeon        # Overworld: Closest Underground Mob Spawner Dungeon
/locate fortress       # Nether: Closest Nether Fortress
/locate pillars        # End: Closest Obsidian Pillar & End Crystal
/locate exit_portal    # End: Central Bedrock Fountain & Exit Portal
/locate spawn_platform # End: Obsidian Entry Platform
```

### 3. Summon Entities (`/summon`)
Spawn any mob or the Ender Dragon boss in front of you or at specific coordinates:
```text
/summon <mob_name> [x] [y] [z]
```
- **Available Entities**: `cow`, `pig`, `sheep`, `chicken`, `zombie`, `skeleton`, `spider`, `creeper`, `enderman`, `zombie_pigman`, `blaze`, `silverfish`, `ghast`, `magma_cube`, `ender_dragon`.

### 4. World Time & Moon Phases (`/time`)
Query or control the time of day, day counter, and lunar phase:
```text
/time                              # Display current clock time (AM/PM)
/time set <sunrise|midday|sunset|midnight>
/time set day <number>             # Jump to a specific day number
/time set moon <phase>             # Jump to midnight on a specific Moon Phase
/time add <seconds>                # Advance or rewind time (1200s = 1 full 20-minute day)
/time query <time|day|moon>        # Inspect current time, day count, or moon illumination %
```
- **Moon Phase Presets for `/time set moon <phase>`**:
  `full` (`0`), `waning_gibbous` (`1`), `third_quarter` (`2`), `waning_crescent` (`3`), `new` (`4`), `waxing_crescent` (`5`), `first_quarter` (`6`), `waxing_gibbous` (`7`).

### 5. Kill Entities (`/kill`)
```text
/kill @s   # Kill player self
/kill @e   # Kill all active mobs and bosses in the dimension
/kill @a   # Kill all entities and the player
```

---

## Project Structure

```text
├── main.py                 # Main application window, game loop, input handling, and rendering orchestration
├── world.py                # Chunk management, multiprocess generation/meshing, 3D lighting, and block updates
├── chunk.py / subchunk.py  # 16×16×256 chunk storage and 16×16×16 section VBO mesh uploading
├── biome.py                # Temperature/moisture Perlin noise, 10 biome definitions, and tree generators
├── block_type.py           # Block & item registry, hardness, tool tiers, and custom block geometries
├── block_state.py          # Directional/stateful blocks (stairs, slabs, doors, trapdoors, fences, crops, beds)
├── vert.glsl / frag.glsl   # Core 3D world vertex & fragment shaders (Block & Photorealistic Shader modes)
├── overworld_sky.py        # Atmospheric sky dome, sun, stars, and 8-phase moon shader renderer
├── space_sky.py            # End dimension procedural nebula & starfield skybox renderer
├── end_portal_shader.py    # Parallax starfield shader for End Portal blocks
├── entity_shadows.py       # Directional world heightmap shadows and entity ground shadow renderer
├── clouds.py               # Volumetric 3D cloud mesh generator and renderer
├── gui.py                  # HUD, Hotbar, Survival/Creative Inventory, Crafting, Furnace, Chest & Menus
├── enchanting.py           # Enchanting Table logic, bookshelf power calculation, and combat/mining modifiers
├── command_system.py       # Creative mode '/' command parser and fast mathematical structure locator
├── mob_manager.py          # Natural mob spawning, despawning, spawner cages, and New Moon buffs
├── mob_entity.py           # AI state machines, pathfinding, physics, and combat for 14 standard mobs
├── mob_model.py            # Articulated 3D box models, UV mappings, and animations for mobs & spawners
├── ender_dragon.py         # Ender Dragon boss entity, multi-phase flight AI, and custom 3D renderer
├── player_model.py         # Articulated 3D Steve player model for F5 third-person perspectives
├── village.py              # Procedural village layout planner and structure stamper
├── stronghold_manager.py   # Underground stronghold room generator and End Portal chamber
├── fortress_manager.py     # Nether Fortress procedural bridge & corridor generator
├── dungeon.py              # Underground mossy cobblestone dungeon & spawner generator
├── portal_manager.py       # Obsidian Nether Portal frame validation, ignition, and dimension linking
├── end_generator.py        # The End island, obsidian pillars, End Crystals, and exit fountain generator
├── explosion.py            # Raycast explosion physics, block destruction, and entity knockback
├── world_save.py           # Persistent world saving/loading (modified blocks, states, inventories, entities)
├── models/                 # Custom 3D voxel geometry definitions (stairs, doors, fences, liquids, beds, etc.)
└── textures/               # Block, item, mob, GUI, and celestial textures
```
