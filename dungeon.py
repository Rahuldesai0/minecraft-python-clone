"""
Procedural Overworld Monster Dungeons Generator
-----------------------------------------------
Generates authentic Minecraft Java Edition underground dungeons:
1. Size: 7x7x7 Cobblestone & Mossy Cobblestone cube (5x5x5 hollow interior).
2. Spawner in center (Block ID 52): Zombie (50%), Skeleton (25%), or Spider (25%).
3. 1 to 2 Chests (Block ID 54) placed along walls with authentic loot tables.
"""

import math
import random
import hashlib
from noise import pnoise2, pnoise3

# Block IDs
BLOCK_AIR = 0
BLOCK_COBBLESTONE = 1
BLOCK_MOSSY_COBBLESTONE = 82
BLOCK_MOB_SPAWNER = 177
BLOCK_CHEST = 37

# Item IDs for Dungeon Chest Loot
ITEM_SADDLE = 125
ITEM_IRON_INGOT = 123
ITEM_GOLD_INGOT = 124
ITEM_BREAD = 152
ITEM_WHEAT = 154
ITEM_GUNPOWDER = 118
ITEM_STRING = 109
ITEM_BUCKET = 147
ITEM_REDSTONE = 121
ITEM_ROTTEN_FLESH = 136
ITEM_BONE = 137
ITEM_MUSIC_DISC = 160
ITEM_NAME_TAG = 161
ITEM_GOLDEN_APPLE = 135
ITEM_ENCHANTED_BOOK = 162
ITEM_COAL = 121


def get_dungeon_loot(rng):
    """Generates 27-slot chest inventory with authentic Minecraft dungeon loot."""
    slots = [[0, 0] for _ in range(27)]

    # Pool of possible dungeon loot items with weight and count ranges
    loot_pool = [
        (ITEM_SADDLE, 1, 1, 0.28),
        (ITEM_IRON_INGOT, 1, 4, 0.50),
        (ITEM_GOLD_INGOT, 1, 3, 0.20),
        (ITEM_BREAD, 1, 2, 0.55),
        (ITEM_WHEAT, 1, 4, 0.55),
        (ITEM_GUNPOWDER, 1, 4, 0.55),
        (ITEM_STRING, 1, 4, 0.55),
        (ITEM_BUCKET, 1, 1, 0.18),
        (ITEM_REDSTONE, 1, 4, 0.30),
        (ITEM_ROTTEN_FLESH, 1, 8, 0.60),
        (ITEM_BONE, 1, 8, 0.60),
        (ITEM_NAME_TAG, 1, 1, 0.28),
        (ITEM_GOLDEN_APPLE, 1, 1, 0.08),
        (ITEM_ENCHANTED_BOOK, 1, 1, 0.15),
        (ITEM_MUSIC_DISC, 1, 1, 0.12),
    ]

    # Pick 4 to 8 random loot stacks
    num_items = rng.randint(4, 8)
    chosen_slots = rng.sample(range(27), num_items)

    for slot_idx in chosen_slots:
        # Weighted roll from pool
        for item_id, min_c, max_c, chance in loot_pool:
            if rng.random() < chance:
                count = rng.randint(min_c, max_c)
                slots[slot_idx] = [item_id, count]
                break

    return slots


def get_dungeon_in_chunk(cx, cz, seed=0):
    """
    Deterministically determines if a dungeon generates in chunk (cx, cz).
    Returns (dungeon_center_x, dungeon_center_y, dungeon_center_z, mob_type) or None.
    """
    # Deterministic hash for dungeon generation in chunk
    chunk_hash = int(hashlib.md5(f"dungeon_{seed}_{cx}_{cz}".encode()).hexdigest(), 16)
    rng = random.Random(chunk_hash)

    # 1 in 8 chunks has a dungeon attempt
    if (chunk_hash % 8) != 0:
        return None

    # Center coordinates inside chunk
    lx = rng.randint(4, 11)
    lz = rng.randint(4, 11)
    # Underground depth between Y=18 and Y=48
    ly = rng.randint(18, 48)

    wx = cx * 16 + lx
    wz = cz * 16 + lz
    wy = ly

    # Mob Spawner Type: 50% Zombie, 25% Skeleton, 25% Spider
    m_roll = rng.random()
    if m_roll < 0.50:
        mob_type = "zombie"
    elif m_roll < 0.75:
        mob_type = "skeleton"
    else:
        mob_type = "spider"

    return (wx, wy, wz, mob_type)


def get_dungeon_blocks_for_chunk(cx, cz, seed=0):
    """
    Returns (solid_blocks, air_blocks, chests_dict, spawner_info) for chunk (cx, cz).
    solid_blocks: dict (local_x, local_y, local_z) -> block_id
    air_blocks: set of (local_x, local_y, local_z)
    chests_dict: dict (world_x, world_y, world_z) -> 27-slot items
    spawner_info: dict with 'pos': (wx, wy, wz), 'mob_type': str
    """
    solid_blocks = {}
    air_blocks = set()
    chests_dict = {}
    spawner_info = None

    # Check this chunk and 8 neighbor chunks since 7x7x7 dungeon can cross chunk boundaries
    for ncx in range(cx - 1, cx + 2):
        for ncz in range(cz - 1, cz + 2):
            d_data = get_dungeon_in_chunk(ncx, ncz, seed)
            if not d_data:
                continue

            dwx, dwy, dwz, mob_type = d_data
            d_rng = random.Random(int(hashlib.md5(f"dungeon_layout_{seed}_{dwx}_{dwz}".encode()).hexdigest(), 16))

            # 7x7x7 bounding box: X in [-3, 3], Z in [-3, 3], Y in [-3, 3] relative to center
            # Spawner is placed on the floor at (dwx, dwy - 2, dwz) resting on cobblestone floor (dwy - 3)
            if cx * 16 <= dwx < (cx + 1) * 16 and cz * 16 <= dwz < (cz + 1) * 16:
                spawner_info = {
                    "pos": (dwx, dwy - 2, dwz),
                    "mob_type": mob_type,
                }

            # Pre-determine 1 to 2 chest locations against the interior walls (Y = -2 relative to center)
            possible_chest_locs = [
                (dwx - 2, dwy - 2, dwz),      # West wall
                (dwx + 2, dwy - 2, dwz),      # East wall
                (dwx, dwy - 2, dwz - 2),      # North wall
                (dwx, dwy - 2, dwz + 2),      # South wall
            ]
            d_rng.shuffle(possible_chest_locs)
            num_chests = d_rng.randint(1, 2)
            chest_positions = set(possible_chest_locs[:num_chests])

            # Carve 7x7x7 cube
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    for dz in range(-3, 4):
                        wx = dwx + dx
                        wy = dwy + dy
                        wz = dwz + dz

                        # Check if within current chunk
                        if not (cx * 16 <= wx < (cx + 1) * 16 and cz * 16 <= wz < (cz + 1) * 16):
                            continue

                        lx = wx - cx * 16
                        ly = wy
                        lz = wz - cz * 16

                        is_outer_wall = (abs(dx) == 3 or abs(dz) == 3 or dy == -3 or dy == 3)

                        if is_outer_wall:
                            # 50% Cobblestone, 50% Mossy Cobblestone
                            b_mat = BLOCK_MOSSY_COBBLESTONE if d_rng.random() < 0.50 else BLOCK_COBBLESTONE
                            solid_blocks[(lx, ly, lz)] = b_mat
                        else:
                            # Interior:
                            if dx == 0 and dy == -2 and dz == 0:
                                # Central Mob Spawner (Block 286) resting on the floor
                                solid_blocks[(lx, ly, lz)] = BLOCK_MOB_SPAWNER
                            elif (wx, wy, wz) in chest_positions and dy == -2:
                                # Chest (Block 37)
                                solid_blocks[(lx, ly, lz)] = BLOCK_CHEST
                                chests_dict[(wx, wy, wz)] = get_dungeon_loot(d_rng)
                            else:
                                air_blocks.add((lx, ly, lz))

    return solid_blocks, air_blocks, chests_dict, spawner_info


def get_nearby_dungeon_spawners(player_pos, seed=0, radius=64):
    """Finds all active dungeon spawners within radius of player."""
    px, py, pz = player_pos
    min_cx = math.floor((px - radius) / 16)
    max_cx = math.floor((px + radius) / 16)
    min_cz = math.floor((pz - radius) / 16)
    max_cz = math.floor((pz + radius) / 16)

    spawners = []
    for cx in range(min_cx, max_cx + 1):
        for cz in range(min_cz, max_cz + 1):
            d_data = get_dungeon_in_chunk(cx, cz, seed)
            if d_data:
                dwx, dwy, dwz, mob_type = d_data
                sp_pos = (dwx, dwy - 2, dwz)
                dist = math.sqrt((sp_pos[0] - px) ** 2 + (sp_pos[1] - py) ** 2 + (sp_pos[2] - pz) ** 2)
                if dist <= radius:
                    spawners.append({
                        "pos": sp_pos,
                        "mob_type": mob_type,
                    })
    return spawners
