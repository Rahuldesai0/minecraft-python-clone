"""
Minecraft Passive & Hostile Mob Spawning, Simulation, & Rendering Manager
-------------------------------------------------------------------------
Implements natural passive and hostile mob population spawning, Survival-mode validation,
cave/underground spawning, nighttime surface spawning, simulation capping, and 3D rendering
for Cow, Pig, Sheep, Chicken, Zombie, Skeleton, and Spider.
"""

import math
import random
import mob_entity
import mob_model
import fireball
import fortress_manager
import stronghold_manager
import block_state


class MobManager:
	def __init__(self, world):
		self.world = world
		self.mobs = []
		self.next_entity_id = 1

		# Render Models for all passive, hostile & neutral mobs
		self.pig_model = mob_model.PigModel()
		self.cow_model = mob_model.CowModel()
		self.sheep_model = mob_model.SheepModel()
		self.chicken_model = mob_model.ChickenModel()
		self.zombie_model = mob_model.ZombieModel()
		self.zombie_pigman_model = mob_model.ZombiePigmanModel()
		self.blaze_model = mob_model.BlazeModel()
		self.enderman_model = mob_model.EndermanModel()
		self.silverfish_model = mob_model.SilverfishModel()
		self.skeleton_model = mob_model.SkeletonModel()
		self.spider_model = mob_model.SpiderModel()
		self.creeper_model = mob_model.CreeperModel()

		self.fireball_manager = fireball.FireballManager(self.world)

		# Spawning Parameters
		self.passive_spawn_timer = 0.0
		self.hostile_spawn_timer = 0.0
		self.spawner_tick_timer = 0.0
		self.active_spawners = {}  # pos -> {"mob_type": str, "delay": float}
		self.max_passive_mobs = 24
		self.max_hostile_mobs = 28
		self.max_surface_hostiles = 20
		self.max_cave_hostiles = 8
		self.max_nether_mobs = 45
		self.max_blaze_mobs = 20
		self.max_end_mobs = 14

	def spawn_mob(self, mob_type, position):
		eid = self.next_entity_id
		self.next_entity_id += 1

		if mob_type == "pig":
			mob = mob_entity.PigEntity(eid, position)
		elif mob_type == "cow":
			mob = mob_entity.CowEntity(eid, position)
		elif mob_type == "sheep":
			mob = mob_entity.SheepEntity(eid, position)
		elif mob_type == "chicken":
			mob = mob_entity.ChickenEntity(eid, position)
		elif mob_type == "zombie":
			mob = mob_entity.ZombieEntity(eid, position)
		elif mob_type == "zombie_pigman":
			mob = mob_entity.ZombiePigmanEntity(eid, position)
		elif mob_type == "blaze":
			mob = mob_entity.BlazeEntity(eid, position)
		elif mob_type == "enderman":
			mob = mob_entity.EndermanEntity(eid, position)
		elif mob_type == "silverfish":
			mob = mob_entity.SilverfishEntity(eid, position)
		elif mob_type == "skeleton":
			mob = mob_entity.SkeletonEntity(eid, position)
		elif mob_type == "spider":
			mob = mob_entity.SpiderEntity(eid, position)
		elif mob_type == "creeper":
			mob = mob_entity.CreeperEntity(eid, position)
		else:
			mob = mob_entity.CowEntity(eid, position)

		self.mobs.append(mob)
		return mob

	def reset_all_aggro(self):
		"""Resets aggression and targeting across all active mobs on player death/respawn."""
		for mob in self.mobs:
			if hasattr(mob, "reset_aggro"):
				mob.reset_aggro()
			else:
				if hasattr(mob, "is_angry"):
					mob.is_angry = False
				if hasattr(mob, "is_screaming"):
					mob.is_screaming = False
				if hasattr(mob, "target"):
					mob.target = None
				if hasattr(mob, "target_dest"):
					mob.target_dest = None
				if hasattr(mob, "fuse_timer"):
					mob.fuse_timer = 0.0

	def get_balanced_spawn_type(self):
		"""Returns the passive mob type that is currently least populated."""
		counts = {"cow": 0, "pig": 0, "sheep": 0, "chicken": 0}
		for m in self.mobs:
			if m.mob_type in counts:
				counts[m.mob_type] += 1
		min_count = min(counts.values())
		candidates = [t for t, c in counts.items() if c == min_count]
		return random.choice(candidates)

	def get_balanced_hostile_type(self):
		"""Returns the hostile mob type that is currently least populated."""
		counts = {"zombie": 0, "skeleton": 0, "spider": 0, "creeper": 0, "enderman": 0}
		for m in self.mobs:
			if m.mob_type in counts:
				counts[m.mob_type] += 1
		min_count = min(counts.values())
		candidates = [t for t, c in counts.items() if c == min_count]
		return random.choice(candidates)

	def populate_initial_mobs(self, player_pos):
		"""Spawns an initial balanced population of mobs around spawn/player."""
		if len(self.mobs) >= 20:
			return

		px, py, pz = player_pos

		if getattr(self.world, "dimension", "overworld") == "nether":
			world_seed = getattr(self.world, "seed", 0)

			# 1. Spawn Blazes directly at nearby spawner platforms
			nearby_spawners = fortress_manager.get_nearby_spawner_positions(player_pos, seed=world_seed, radius=160)
			for spx, spy, spz in nearby_spawners:
				sp_blazes = random.randint(2, 4)
				for _ in range(sp_blazes):
					if len(self.mobs) >= self.max_nether_mobs:
						break
					off_x = spx + random.uniform(-1.5, 1.5)
					off_y = spy + random.uniform(0.5, 2.5)
					off_z = spz + random.uniform(-1.5, 1.5)
					self.spawn_mob("blaze", (off_x, off_y, off_z))

			# 2. General spatial spawning across fortress & wilderness
			for _ in range(25):
				if len(self.mobs) >= self.max_nether_mobs:
					break
				angle = random.uniform(0, math.tau)
				dist = random.uniform(8.0, 52.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				sy = None
				for y in range(115, 32, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (84, 85, 90):  # Netherrack, Soul Sand, or Nether Brick
						if self.world.get_block_number((sx, y + 1, sz)) == 0 and self.world.get_block_number((sx, y + 2, sz)) == 0:
							sy = y + 1
							break
				if sy is not None:
					in_fortress = fortress_manager.is_inside_fortress_spawn_region((sx, sy, sz), seed=world_seed)
					if in_fortress:
						r_pick = random.random()
						if r_pick < 0.70:
							# Blaze pack spawning
							pack = random.randint(2, 4)
							for _ in range(pack):
								if len(self.mobs) >= self.max_nether_mobs:
									break
								self.spawn_mob("blaze", (sx + random.uniform(-1.2, 1.2), sy + random.uniform(0.2, 1.2), sz + random.uniform(-1.2, 1.2)))
						elif r_pick < 0.85:
							self.spawn_mob("skeleton", (sx, sy, sz))
						elif r_pick < 0.95:
							self.spawn_mob("enderman", (sx, sy, sz))
						else:
							self.spawn_mob("zombie_pigman", (sx, sy, sz))
					else:
						if random.random() < 0.15:
							self.spawn_mob("enderman", (sx, sy, sz))
						else:
							pack = random.randint(2, 4)
							for _ in range(pack):
								if len(self.mobs) >= self.max_nether_mobs:
									break
								off_x = sx + random.uniform(-1.5, 1.5)
								off_z = sz + random.uniform(-1.5, 1.5)
								self.spawn_mob("zombie_pigman", (off_x, sy, off_z))
			return

		if getattr(self.world, "dimension", "overworld") == "end":
			# End Dimension Initial Spawning: Only Endermen spawn in the End! (Atmospheric balanced density)
			enderman_count = sum(1 for m in self.mobs if m.mob_type == "enderman")
			for _ in range(16):
				if enderman_count >= 8:
					break
				angle = random.uniform(0, math.tau)
				dist = random.uniform(20.0, 56.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				# Find End Stone (188) surface or any solid platform
				sy = None
				for y in range(110, 15, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (188, 87, 189) or (b_id != 0 and b_id not in (183, 15, 20, 78) and b_id not in block_state.PASSABLE_BLOCKS):
						if (self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and
						    self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS and
						    self.world.get_block_number((sx, y + 3, sz)) in block_state.PASSABLE_BLOCKS):
							sy = y + 1
							break
				if sy is not None:
					pack = random.randint(1, 2)
					for _ in range(pack):
						if enderman_count >= 8:
							break
						off_x = sx + random.uniform(-1.5, 1.5)
						off_z = sz + random.uniform(-1.5, 1.5)
						self.spawn_mob("enderman", (off_x, sy, off_z))
						enderman_count += 1
			return

		# Overworld Initial Spawning
		mob_types = ["cow", "pig", "sheep", "chicken"]
		random.shuffle(mob_types)

		for mtype in mob_types:
			if len(self.mobs) >= self.max_passive_mobs:
				break
			# Search for valid grass surface at distance 12..42 blocks
			for _ in range(20):
				angle = random.uniform(0, math.tau)
				dist = random.uniform(12.0, 42.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				sy = None
				for y in range(120, 45, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (2, 3):  # Grass block or Dirt
						if self.world.get_block_number((sx, y + 1, sz)) == 0:
							sy = y + 1
							break

				if sy is not None:
					pack = random.randint(2, 4)
					for _ in range(pack):
						if len(self.mobs) >= self.max_passive_mobs:
							break
						off_x = sx + random.uniform(-1.5, 1.5)
						off_z = sz + random.uniform(-1.5, 1.5)
						self.spawn_mob(mtype, (off_x, sy, off_z))
					break

	def try_natural_spawning(self, player_pos):
		"""Spawns passive animal packs (or Nether Fortresses / Pigmen / Endermen) periodically near the player if below cap."""
		if getattr(self.world, "dimension", "overworld") == "nether":
			nether_count = len(self.mobs)
			if nether_count >= self.max_nether_mobs:
				return
			blaze_count = sum(1 for m in self.mobs if m.mob_type == "blaze")
			px, py, pz = player_pos
			world_seed = getattr(self.world, "seed", 0)
			for _ in range(16):
				if len(self.mobs) >= self.max_nether_mobs:
					break
				angle = random.uniform(0, math.tau)
				dist = random.uniform(14.0, 48.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				sy = None
				for y in range(115, 32, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (84, 85, 90):  # Netherrack, Soul Sand, or Nether Brick
						if self.world.get_block_number((sx, y + 1, sz)) == 0 and self.world.get_block_number((sx, y + 2, sz)) == 0:
							sy = y + 1
							break
				if sy is not None:
					in_fortress = fortress_manager.is_inside_fortress_spawn_region((sx, sy, sz), seed=world_seed)
					if in_fortress:
						r_pick = random.random()
						if r_pick < 0.70 and blaze_count < self.max_blaze_mobs:
							pack = random.randint(2, 4)
							for _ in range(pack):
								if len(self.mobs) >= self.max_nether_mobs:
									break
								self.spawn_mob("blaze", (sx + random.uniform(-1.2, 1.2), sy + random.uniform(0.2, 1.5), sz + random.uniform(-1.2, 1.2)))
								blaze_count += 1
						elif r_pick < 0.85:
							self.spawn_mob("skeleton", (sx, sy, sz))
						elif r_pick < 0.95:
							self.spawn_mob("enderman", (sx, sy, sz))
						else:
							self.spawn_mob("zombie_pigman", (sx, sy, sz))
						break
					else:
						if random.random() < 0.15:
							self.spawn_mob("enderman", (sx, sy, sz))
						else:
							pack = random.randint(1, 3)
							for _ in range(pack):
								if len(self.mobs) >= self.max_nether_mobs:
									break
								off_x = sx + random.uniform(-1.8, 1.8)
								off_z = sz + random.uniform(-1.8, 1.8)
								self.spawn_mob("zombie_pigman", (off_x, sy, off_z))
						break
			return

	def try_passive_spawning(self, player_pos):
		"""Spawns passive mobs on grassy terrain around the player (Overworld only)."""
		if not player_pos:
			return

		if getattr(self.world, "dimension", "overworld") in ("end", "nether"):
			return

		passive_count = sum(1 for m in self.mobs if m.mob_type in ("cow", "pig", "sheep", "chicken"))
		if passive_count >= self.max_passive_mobs:
			return

		px, py, pz = player_pos
		mob_type = self.get_balanced_spawn_type()

		for _ in range(10):
			angle = random.uniform(0, math.tau)
			dist = random.uniform(20.0, 52.0)
			sx = int(round(px + math.cos(angle) * dist))
			sz = int(round(pz + math.sin(angle) * dist))

			sy = None
			for y in range(120, 45, -1):
				b_id = self.world.get_block_number((sx, y, sz))
				if b_id in (2, 3):  # Grass block or Dirt
					if self.world.get_block_number((sx, y + 1, sz)) == 0 and self.world.get_block_number((sx, y + 2, sz)) == 0:
						sy = y + 1
						break

			if sy is not None:
				pack = random.randint(1, 3)
				for _ in range(pack):
					if passive_count >= self.max_passive_mobs:
						break
					off_x = sx + random.uniform(-2.2, 2.2)
					off_z = sz + random.uniform(-2.2, 2.2)
					self.spawn_mob(mob_type, (off_x, sy, off_z))
					passive_count += 1
				break

	def is_valid_overworld_hostile_light(self, position, time_of_day=0.5):
		"""Returns True if the effective light level at position is 7 or lower (Standard Minecraft Hostile Spawn Rule)."""
		eff_l, sky_l, blk_l = self.world.get_light_at(position)
		tod = time_of_day % 1.0
		# Sun height: noon (0.50) -> sun_y = 1.0, sunrise/sunset (0.25, 0.75) -> sun_y = 0.0, midnight (0.0/1.0) -> sun_y = -1.0
		sun_y = math.cos((tod - 0.5) * 2.0 * math.pi)
		# Sunlight factor in Overworld: fades to 0 when sun is below horizon
		sun_factor = max(0.0, min(1.0, (sun_y + 0.1) / 0.3))
		# Night sky light is at most 4 (or moonlight level 4)
		effective_sky = int(round(sky_l * (0.25 + 0.75 * sun_factor))) if sun_factor > 0.0 else int(round(sky_l * (4.0 / 15.0)))
		cur_light = max(effective_sky, blk_l)
		return cur_light <= 7

	def try_hostile_spawning(self, player_pos, time_of_day=0.5, flying=False):
		"""Spawns hostile mobs in Survival mode during night on surface, underground caves, or Nether Fortresses."""
		if flying or not player_pos:
			return

		px, py, pz = player_pos

		if getattr(self.world, "dimension", "overworld") == "nether":
			# Nether Hostile Spawning: Blazes, Skeletons, & Endermen in Fortresses
			nether_hostiles = sum(1 for m in self.mobs if m.mob_type in ("blaze", "skeleton", "enderman"))
			blaze_count = sum(1 for m in self.mobs if m.mob_type == "blaze")
			if nether_hostiles >= self.max_hostile_mobs or len(self.mobs) >= self.max_nether_mobs:
				return

			world_seed = getattr(self.world, "seed", 0)
			for _ in range(12):
				if nether_hostiles >= self.max_hostile_mobs or len(self.mobs) >= self.max_nether_mobs:
					break

				angle = random.uniform(0, math.tau)
				dist = random.uniform(12.0, 44.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				spawn_y = None
				for y in range(115, 32, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (84, 85, 90):
						if self.world.get_block_number((sx, y + 1, sz)) == 0 and self.world.get_block_number((sx, y + 2, sz)) == 0 and self.world.get_block_number((sx, y + 3, sz)) == 0:
							spawn_y = y + 1
							break

				if spawn_y is not None:
					in_fortress = fortress_manager.is_inside_fortress_spawn_region((sx, spawn_y, sz), seed=world_seed)
					if in_fortress:
						# Fortress: Wither Skeletons (30%), Skeletons (25%), Blazes (25%), Endermen (10%), Zombified Piglins (10%)
						roll = random.random()
						if roll < 0.30:
							self.spawn_mob("wither_skeleton", (sx, spawn_y, sz))
						elif roll < 0.55:
							self.spawn_mob("skeleton", (sx, spawn_y, sz))
						elif roll < 0.80 and blaze_count < self.max_blaze_mobs:
							self.spawn_mob("blaze", (sx + random.uniform(-1.0, 1.0), spawn_y + random.uniform(0.2, 1.2), sz + random.uniform(-1.0, 1.0)))
						elif roll < 0.90:
							self.spawn_mob("enderman", (sx, spawn_y, sz))
						else:
							self.spawn_mob("zombie_pigman", (sx, spawn_y, sz))
					else:
						# General Nether Wilderness: Zombified Piglins (55%), Endermen (15%), Ghasts (15%), Magma Cubes (15%)
						roll = random.random()
						if roll < 0.55:
							self.spawn_mob("zombie_pigman", (sx, spawn_y, sz))
						elif roll < 0.70:
							self.spawn_mob("enderman", (sx, spawn_y, sz))
						elif roll < 0.85:
							self.spawn_mob("ghast", (sx, spawn_y + 4.0, sz))
						else:
							self.spawn_mob("magma_cube", (sx, spawn_y, sz))
			return

		if getattr(self.world, "dimension", "overworld") == "end":
			# End Hostile Spawning: ONLY Endermen spawn in the End! (Atmospheric balanced density)
			end_count = len(self.mobs)
			if end_count >= self.max_end_mobs:
				return
			px, py, pz = player_pos
			for _ in range(4):
				if len(self.mobs) >= self.max_end_mobs:
					break
				angle = random.uniform(0, math.tau)
				dist = random.uniform(24.0, 52.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				spawn_y = None
				for y in range(110, 15, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (188, 87, 189, 36, 12, 1) or (b_id != 0 and b_id not in (15, 20, 78, 183) and b_id not in block_state.PASSABLE_BLOCKS):
						# 3 air/passable blocks above for Enderman (tall 2.9 blocks hitbox)
						if (self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and
							self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS and
							self.world.get_block_number((sx, y + 3, sz)) in block_state.PASSABLE_BLOCKS):
							spawn_y = y + 1
							break

				if spawn_y is not None:
					self.spawn_mob("enderman", (sx, spawn_y, sz))
					break
			return

		# Overworld Hostile Mob Spawning
		px, py, pz = player_pos
		tod = time_of_day % 1.0
		is_night = (tod <= 0.25 or tod >= 0.73)

		surface_hostiles = sum(1 for m in self.mobs if m.mob_type in ("zombie", "skeleton", "spider", "creeper", "enderman") and m.position[1] >= 55)
		cave_hostiles = sum(1 for m in self.mobs if m.mob_type in ("zombie", "skeleton", "spider", "creeper", "enderman") and m.position[1] < 55)
		total_hostiles = surface_hostiles + cave_hostiles

		if total_hostiles >= self.max_hostile_mobs:
			return

		# 1. Nighttime Surface Spawning (Only on blocks with light level <= 7)
		if is_night and surface_hostiles < self.max_surface_hostiles:
			needed = min(self.max_surface_hostiles - surface_hostiles, self.max_hostile_mobs - total_hostiles)
			attempts = min(16, needed * 2)
			for _ in range(attempts):
				if surface_hostiles >= self.max_surface_hostiles or total_hostiles >= self.max_hostile_mobs:
					break

				angle = random.uniform(0, math.tau)
				dist = random.uniform(14.0, 36.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				spawn_y = None
				for y in range(130, 48, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id != 0 and b_id not in (13, 14, 18, 224, 234, 244, 254, 264) and b_id not in block_state.PASSABLE_BLOCKS:
						if (self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and
						    self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS and
						    self.world.get_block_number((sx, y + 3, sz)) in block_state.PASSABLE_BLOCKS):
							spawn_y = y + 1
							break

				if spawn_y is not None:
					# Overworld hostile mob rule: block light level must be 7 or lower!
					if not self.is_valid_overworld_hostile_light((sx, spawn_y, sz), time_of_day=time_of_day):
						continue

					mob_type = self.get_balanced_hostile_type()
					pack = random.randint(1, 2) if mob_type == "enderman" else random.randint(1, 3)
					for _ in range(pack):
						if surface_hostiles >= self.max_surface_hostiles or total_hostiles >= self.max_hostile_mobs:
							break
						off_x = sx + random.uniform(-1.0, 1.0)
						off_z = sz + random.uniform(-1.0, 1.0)
						# Verify spawn offset light level
						if not self.is_valid_overworld_hostile_light((off_x, spawn_y, off_z), time_of_day=time_of_day):
							continue
						self.spawn_mob(mob_type, (off_x, spawn_y, off_z))
						surface_hostiles += 1
						total_hostiles += 1

		# 2. Underground / Cave Spawning (Only in dark caves with light level <= 7)
		if cave_hostiles < self.max_cave_hostiles and total_hostiles < self.max_hostile_mobs:
			for _ in range(6):
				if cave_hostiles >= self.max_cave_hostiles or total_hostiles >= self.max_hostile_mobs:
					break

				angle = random.uniform(0, math.tau)
				dist = random.uniform(12.0, 36.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				spawn_y = None
				for y in range(54, 12, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id != 0 and b_id not in (13, 14, 18, 224, 234, 244, 254, 264) and b_id not in block_state.PASSABLE_BLOCKS:
						if (self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and
						    self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS and
						    self.world.get_block_number((sx, y + 3, sz)) in block_state.PASSABLE_BLOCKS):
							# Check for solid ceiling above (cave)
							has_ceil = False
							for cy in range(y + 4, min(120, y + 18)):
								cb = self.world.get_block_number((sx, cy, sz))
								if cb != 0 and cb not in (9, 19, 78):
									has_ceil = True
									break
							if has_ceil:
								spawn_y = y + 1
								break

				if spawn_y is not None:
					# Overworld hostile mob rule: block light level must be 7 or lower!
					if not self.is_valid_overworld_hostile_light((sx, spawn_y, sz), time_of_day=time_of_day):
						continue

					mob_type = self.get_balanced_hostile_type()
					self.spawn_mob(mob_type, (sx, spawn_y, sz))
					cave_hostiles += 1

	def update_spawners(self, dt, player_pos, time_of_day=0.5, flying=False):
		"""
		Ticks active Monster Spawners (Block ID 52):
		1. Activated only when player distance <= 16.0 blocks.
		2. Spawns mobs at intervals of 10.0 to 40.0 seconds.
		3. Spawns 1 to 4 mobs at a time based on space availability.
		4. Spawn area: 7x7 horizontal area ([-3, +3] in X and Z) and 5 blocks vertically ([-1, +4] relative to spawner).
		5. Light level requirements:
		   - Zombie / Skeleton / Spider: light level <= 7
		   - Blaze: light level <= 11 (Nether dimension)
		   - Silverfish: light level <= 11
		6. Nearby mob cap: <= 6 of same mob within 9x9 area.
		"""
		if not player_pos:
			return

		px, py, pz = player_pos
		curr_dim = getattr(self.world, "dimension", "overworld")
		world_seed = getattr(self.world, "seed", 0)

		# 1. Collect all nearby spawners within player active search radius (48 blocks)
		nearby_spawners = []  # list of (spx, spy, spz, mob_type)

		if curr_dim == "overworld":
			# Dungeon Spawners (Zombie, Skeleton, Spider)
			try:
				import dungeon
				d_spawners = dungeon.get_nearby_dungeon_spawners(player_pos, seed=world_seed, radius=48)
				for d in d_spawners:
					spx, spy, spz = d["pos"]
					nearby_spawners.append((spx, spy, spz, d["mob_type"]))
			except Exception:
				pass

			# Stronghold Silverfish Spawner (Portal Room)
			try:
				import stronghold_manager
				sf_spawners = stronghold_manager.get_nearby_silverfish_spawners(player_pos, seed=world_seed, radius=48)
				for spx, spy, spz in sf_spawners:
					nearby_spawners.append((spx, spy, spz, "silverfish"))
			except Exception:
				pass

		elif curr_dim == "nether":
			# Nether Fortress Blaze Spawners (2 platforms per fortress)
			try:
				import fortress_manager
				f_spawners = fortress_manager.get_nearby_spawner_positions(player_pos, seed=world_seed, radius=48)
				for spx, spy, spz in f_spawners:
					nearby_spawners.append((spx, spy, spz, "blaze"))
			except Exception:
				pass

		# Also scan loaded chunks within 24 blocks of player for any placed / loaded Block 177
		ipx, ipy, ipz = int(round(px)), int(round(py)), int(round(pz))
		for cdx in (-1, 0, 1):
			for cdz in (-1, 0, 1):
				cx = (ipx // 16) + cdx
				cz = (ipz // 16) + cdz
				c_pos = (cx, 0, cz)
				if hasattr(self.world, "chunks") and c_pos in self.world.chunks:
					chk = self.world.chunks[c_pos]
					if hasattr(chk, "blocks") and 177 in chk.blocks:
						for lx in range(16):
							for ly in range(max(0, ipy - 20), min(256, ipy + 20)):
								for lz in range(16):
									if chk.blocks[lx * 4096 + ly * 16 + lz] == 177:
										wx = cx * 16 + lx
										wz = cz * 16 + lz
										if not any(s[0] == wx and s[1] == ly and s[2] == wz for s in nearby_spawners):
											default_mob = "blaze" if curr_dim == "nether" else "zombie"
											if (wx, ly, wz) in self.active_spawners:
												default_mob = self.active_spawners[(wx, ly, wz)].get("mob_type", default_mob)
											nearby_spawners.append((wx, ly, wz, default_mob))

		# Also include already tracked / placed spawners in active_spawners
		for (cspx, cspy, cspz), cdata in list(self.active_spawners.items()):
			if not any(spx == cspx and spy == cspy and spz == cspz for spx, spy, spz, _ in nearby_spawners):
				nearby_spawners.append((cspx, cspy, cspz, cdata.get("mob_type", "zombie")))

		# 2. Process each active spawner
		for spx, spy, spz, mob_type in nearby_spawners:
			sp_pos = (int(round(spx)), int(round(spy)), int(round(spz)))

			# Verify spawner block is still intact (Block ID 177 = Mob Spawner)
			# (If broken by player, skip)
			block_num = self.world.get_block_number(sp_pos)
			if block_num != 177 and block_num != 0:
				continue

			# Check player proximity (Activation range <= 16.0 blocks in X-Z horizontal direction)
			xz_dist_sq = (spx - px) ** 2 + (spz - pz) ** 2
			if xz_dist_sq > 16.0 * 16.0:
				continue

			# Initialize spawner state if new (quick 1.5-4s initial countdown on first encounter)
			if sp_pos not in self.active_spawners:
				self.active_spawners[sp_pos] = {
					"mob_type": mob_type,
					"delay": random.uniform(1.5, 4.0),
				}

			sp_data = self.active_spawners[sp_pos]
			sp_data["delay"] -= dt

			if sp_data["delay"] <= 0.0:
				# Reset countdown to next random interval (10 to 40 seconds)
				sp_data["delay"] = random.uniform(10.0, 40.0)

				# Check nearby mob cap (Max 6 of same mob within 9x9 area)
				nearby_same_mobs = sum(
					1 for m in self.mobs
					if m.mob_type == mob_type and
					abs(m.position[0] - spx) <= 4.5 and
					abs(m.position[1] - spy) <= 4.5 and
					abs(m.position[2] - spz) <= 4.5
				)
				if nearby_same_mobs >= 6:
					continue

				# Check total mob caps
				if curr_dim == "nether" and len(self.mobs) >= self.max_nether_mobs:
					continue
				if curr_dim == "overworld" and len(self.mobs) >= self.max_hostile_mobs + 10:
					continue

				# Roll 1 to 4 mobs to spawn
				spawn_batch = random.randint(1, 4)
				spawned_this_cycle = 0

				# Attempt spawn placements within 7x7 area horizontally ([-3, +3]) and 5 blocks vertically ([-1, +3])
				for _ in range(48):
					if spawned_this_cycle >= spawn_batch:
						break

					ox = random.randint(-3, 3)
					oz = random.randint(-3, 3)

					for oy in (0, 1, -1, 2):
						sx = spx + ox
						sy = spy + oy
						sz = spz + oz

						# 1. Clearance & Space availability check
						# Mob body position must be in air/passable blocks
						b_feet = self.world.get_block_number((sx, sy, sz))
						b_head = self.world.get_block_number((sx, sy + 1, sz))
						b_floor = self.world.get_block_number((sx, sy - 1, sz))

						if b_feet != 0 or (mob_type not in ("spider", "silverfish") and b_head != 0):
							continue

						# Land mobs require solid floor underneath; Blazes can spawn in air
						if mob_type != "blaze":
							if b_floor == 0 or b_floor in (9, 19, 15, 20):
								continue

						# 2. Light level requirements
						if mob_type in ("zombie", "skeleton", "spider"):
							# Must be light level 7 or below (disabled by torches)
							if not self.is_valid_overworld_hostile_light((sx, sy, sz), time_of_day=time_of_day):
								continue
						elif mob_type == "blaze":
							# Nether Blaze spawner light requirement: light level <= 11
							eff_l, sky_l, blk_l = self.world.get_light_at((sx, sy, sz))
							if blk_l > 11:
								continue
						elif mob_type == "silverfish":
							# Stronghold Portal Room Silverfish Spawner (spawns on stairs/floor around spawner)
							pass

						# Spawn the mob with slight center offset
						spawn_x = sx + 0.5
						spawn_y = sy + (0.1 if mob_type != "blaze" else 0.5)
						spawn_z = sz + 0.5
						self.spawn_mob(mob_type, (spawn_x, spawn_y, spawn_z))
						spawned_this_cycle += 1
						break

	def update(self, dt, player_pos, camera=None, gui=None, tnt_manager=None, item_drop_manager=None, arrow_manager=None, time_of_day=0.5, flying=False):
		# Dimension Safeguard: Only update mobs if this manager matches the active player dimension
		if camera:
			win_ref = getattr(camera, 'window', None)
			if win_ref:
				win_dim = getattr(win_ref, 'dimension', None)
				curr_dim = getattr(self.world, 'dimension', 'overworld')
				if win_dim and win_dim != curr_dim:
					return

		# Throttled passive and hostile mob spawning
		self.passive_spawn_timer += dt
		if self.passive_spawn_timer >= 2.0:
			self.passive_spawn_timer = 0.0
			curr_dim = getattr(self.world, "dimension", "overworld")
			if curr_dim == "overworld":
				self.try_passive_spawning(player_pos)
			elif curr_dim == "nether":
				self.try_natural_spawning(player_pos)

		self.hostile_spawn_timer += dt
		if self.hostile_spawn_timer >= 1.5:
			self.hostile_spawn_timer = 0.0
			self.try_hostile_spawning(player_pos, time_of_day=time_of_day, flying=flying)

		px, py, pz = player_pos

		# Active Monster Spawners (10-40s Interval, 1-4 mobs, 7x7x5 area, light requirements)
		self.update_spawners(dt, player_pos, time_of_day=time_of_day, flying=flying)

		px, py, pz = player_pos

		# Update active Small Fireball projectiles
		if hasattr(self, 'fireball_manager') and self.fireball_manager:
			self.fireball_manager.update(dt, camera=camera, gui=gui)

		i = 0
		while i < len(self.mobs):
			mob = self.mobs[i]

			dx = mob.position[0] - px
			dy = mob.position[1] - py
			dz = mob.position[2] - pz
			dist_sq = dx * dx + dy * dy + dz * dz

			# Despawn distant mobs (Hostiles beyond 56 blocks, Passives beyond 96 blocks)
			is_hostile = mob.mob_type in ("zombie", "skeleton", "spider", "creeper", "blaze", "enderman")
			despawn_dist_sq = 3136.0 if is_hostile else 9216.0  # 56m for hostiles, 96m for passives
			if dist_sq > despawn_dist_sq:
				self.mobs.pop(i)
				continue

			# Simulation Distance Capping: Only run full AI & Physics for mobs within 64 blocks
			if dist_sq <= 4096.0:
				mob.update(
					dt, self.world, player_pos,
					camera=camera, gui=gui, tnt_manager=tnt_manager, mob_manager=self,
					item_drop_manager=item_drop_manager, arrow_manager=arrow_manager,
					fireball_manager=self.fireball_manager,
					time_of_day=time_of_day, flying=flying
				)

			# Process dead mob drops & removal
			if mob.is_dead:
				looting_lvl = getattr(mob, "last_looting_level", 0)
				drops, xp = mob.get_loot_drops(is_on_fire=(mob.fire_timer > 0), looting_level=looting_lvl)
				if item_drop_manager:
					for b_id, count in drops:
						item_drop_manager.spawn_drop(b_id, count, mob.position)
					if xp and xp > 0:
						item_drop_manager.spawn_xp_orb(xp, mob.position)
				self.mobs.pop(i)
				continue

			i += 1

	def attack_mob_at_crosshair(self, camera, max_reach=5.0, damage=4, fire_duration=0.0, looting_level=0):
		"""Checks if player's attack Raycast hits a nearby mob and deals damage."""
		cam_x, cam_y, cam_z = camera.position
		yaw, pitch = camera.rotation

		# Match camera rotation vector convention from hit.py
		dx = math.cos(yaw) * math.cos(pitch)
		dy = math.sin(pitch)
		dz = math.sin(yaw) * math.cos(pitch)

		closest_mob = None
		closest_dist = max_reach

		for mob in self.mobs:
			mx, my, mz = mob.position
			half_w = (mob.width / 2.0) + 0.25  # Generous bounding box margin
			min_x, max_x = mx - half_w, mx + half_w
			min_y, max_y = my - 0.2, my + mob.height + 0.2
			min_z, max_z = mz - half_w, mz + half_w

			# Fine 0.05 step raycast along camera direction vector
			steps = int(max_reach / 0.05)
			for step in range(1, steps + 1):
				dist = step * 0.05
				rx = cam_x + dx * dist
				ry = cam_y + dy * dist
				rz = cam_z + dz * dist

				if min_x <= rx <= max_x and min_y <= ry <= max_y and min_z <= rz <= max_z:
					if dist < closest_dist:
						closest_dist = dist
						closest_mob = mob
					break

		if closest_mob:
			attacker_pos = list(camera.position)
			closest_mob.take_damage(damage, attacker_pos=attacker_pos, world=self.world, mob_manager=self, looting_level=looting_level)

			if fire_duration > 0.0:
				closest_mob.fire_timer = max(getattr(closest_mob, "fire_timer", 0.0), float(fire_duration))

			# If a Zombie Pigman is provoked, immediately alert ALL nearby Pigmen within 32 blocks!
			if closest_mob.mob_type == "zombie_pigman":
				closest_mob.become_angry(attacker_pos)
				mx, my, mz = closest_mob.position
				for other in self.mobs:
					if other is not closest_mob and other.mob_type == "zombie_pigman" and not other.is_dead:
						ox, oy, oz = other.position
						dx, dy, dz = ox - mx, oy - my, oz - mz
						if (dx * dx + dy * dy + dz * dz) <= (32.0 * 32.0):
							other.become_angry(attacker_pos)
			return True
		return False

	def draw(self, camera, world=None, sky_factor=1.0, min_light=0.20):
		"""Render active 3D models for all passive, hostile, and neutral mobs."""
		for mob in self.mobs:
			if world:
				mx, my, mz = mob.position
				b_coord = (int(math.floor(mx)), int(math.floor(my)), int(math.floor(mz)))
				if getattr(mob, "_last_light_coord", None) == b_coord and hasattr(mob, "_cached_light_mult"):
					mob_light = mob._cached_light_mult
				else:
					_, sky_lvl, blk_lvl = world.get_light_at(b_coord)
					eff_sky = sky_lvl * sky_factor
					eff_light = max(eff_sky, blk_lvl)
					smooth_ratio = (eff_light / 15.0) ** 1.5
					mob_light = min_light + (1.0 - min_light) * smooth_ratio
					mob._last_light_coord = b_coord
					mob._cached_light_mult = mob_light
			else:
				mob_light = 1.0

			# Blaze is intrinsically glowing
			if mob.mob_type == "blaze":
				mob_light = max(mob_light, 1.0)

			if mob.mob_type == "pig":
				self.pig_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					light_mult=mob_light
				)
			elif mob.mob_type == "cow":
				self.cow_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					light_mult=mob_light
				)
			elif mob.mob_type == "sheep":
				self.sheep_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_grazing=getattr(mob, "is_grazing", False),
					light_mult=mob_light
				)
			elif mob.mob_type == "chicken":
				self.chicken_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					wing_flap=getattr(mob, "wing_flap", 0.0),
					light_mult=mob_light
				)
			elif mob.mob_type == "zombie":
				self.zombie_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					attack_anim_time=getattr(mob, "attack_anim_time", 0.0),
					light_mult=mob_light
				)
			elif mob.mob_type == "zombie_pigman":
				self.zombie_pigman_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_angry=getattr(mob, "is_angry", False),
					attack_anim_time=getattr(mob, "attack_anim_time", 0.0),
					light_mult=mob_light
				)
			elif mob.mob_type == "blaze":
				self.blaze_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_charging=getattr(mob, "is_charging", False),
					light_mult=mob_light
				)
			elif mob.mob_type == "enderman":
				self.enderman_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					target_yaw=getattr(mob, "target_yaw", mob.yaw),
					is_screaming=getattr(mob, "is_screaming", False),
					light_mult=mob_light
				)
			elif mob.mob_type == "silverfish":
				self.silverfish_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					light_mult=mob_light
				)
			elif mob.mob_type == "skeleton":
				self.skeleton_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_aiming=getattr(mob, "is_aiming", False),
					light_mult=mob_light
				)
			elif mob.mob_type == "spider":
				self.spider_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_climbing=getattr(mob, "is_climbing", False),
					light_mult=mob_light
				)
			elif mob.mob_type == "creeper":
				self.creeper_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					fuse_progress=getattr(mob, "fuse_progress", 0.0),
					light_mult=mob_light
				)

		# Draw active Small Fireball projectiles
		if hasattr(self, 'fireball_manager') and self.fireball_manager:
			self.fireball_manager.draw(camera)

		# Draw Spinning Miniature Mobs inside active/nearby Monster Spawners
		self.draw_spawners(camera, world=world)

	def draw_spawners(self, camera, world=None):
		"""Renders miniature spinning 3D mob inside monster spawner cages and flame particles."""
		if not camera or not self.active_spawners:
			return

		import time
		cur_t = time.time()
		px, py, pz = camera.position

		for (spx, spy, spz), sdata in list(self.active_spawners.items()):
			# Check if spawner block is still intact
			b_curr = self.world.get_block_number((spx, spy, spz))
			if b_curr != 177 and b_curr != 0:
				continue

			dist_sq = (spx + 0.5 - px) ** 2 + (spy + 0.5 - py) ** 2 + (spz + 0.5 - pz) ** 2
			if dist_sq > 36.0 * 36.0:
				continue

			mob_t = sdata.get("mob_type", "zombie")
			is_active = ((spx + 0.5 - px) ** 2 + (spz + 0.5 - pz) ** 2) <= 16.0 * 16.0
			spin_speed = 3.5 if is_active else 1.2
			spin_yaw = (cur_t * spin_speed) % math.tau

			# Render miniature mob inside cage
			if mob_t == "spider":
				m_pos = (spx + 0.5, spy + 0.35, spz + 0.5)
				self.spider_model.render(camera, m_pos, spin_yaw, 0.0, cur_t * 2.0, True, scale=0.38, light_mult=1.1)
			elif mob_t == "skeleton":
				m_pos = (spx + 0.5, spy + 0.10, spz + 0.5)
				self.skeleton_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.40, light_mult=1.1)
			elif mob_t == "blaze":
				m_pos = (spx + 0.5, spy + 0.18, spz + 0.5)
				self.blaze_model.render(camera, m_pos, spin_yaw, 0.0, cur_t * 3.0, True, scale=0.38, light_mult=1.2)
			elif mob_t == "silverfish":
				m_pos = (spx + 0.5, spy + 0.42, spz + 0.5)
				self.silverfish_model.render(camera, m_pos, spin_yaw, 0.0, cur_t * 4.0, True, scale=0.55, light_mult=1.1)
			elif mob_t == "creeper":
				m_pos = (spx + 0.5, spy + 0.15, spz + 0.5)
				self.creeper_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.40, light_mult=1.1)
			elif mob_t == "zombie_pigman":
				m_pos = (spx + 0.5, spy + 0.10, spz + 0.5)
				self.zombie_pigman_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.40, light_mult=1.1)
			elif mob_t == "enderman":
				m_pos = (spx + 0.5, spy + 0.05, spz + 0.5)
				self.enderman_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.28, light_mult=1.1)
			elif mob_t == "pig":
				m_pos = (spx + 0.5, spy + 0.25, spz + 0.5)
				self.pig_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.40, light_mult=1.1)
			elif mob_t == "cow":
				m_pos = (spx + 0.5, spy + 0.20, spz + 0.5)
				self.cow_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.35, light_mult=1.1)
			elif mob_t == "sheep":
				m_pos = (spx + 0.5, spy + 0.20, spz + 0.5)
				self.sheep_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.38, light_mult=1.1)
			elif mob_t == "chicken":
				m_pos = (spx + 0.5, spy + 0.35, spz + 0.5)
				self.chicken_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.45, light_mult=1.1)
			else: # Default zombie
				m_pos = (spx + 0.5, spy + 0.10, spz + 0.5)
				self.zombie_model.render(camera, m_pos, spin_yaw, 0.0, 0.0, False, scale=0.40, light_mult=1.1)
