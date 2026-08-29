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
		self.max_passive_mobs = 24
		self.max_hostile_mobs = 28
		self.max_surface_hostiles = 20
		self.max_cave_hostiles = 8
		self.max_nether_mobs = 45
		self.max_blaze_mobs = 20

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
		if getattr(self.world, "dimension", "overworld") == "end":
			# End Dimension Initial Spawning: Only Endermen spawn in the End! (No zombies, skeletons, spiders, creepers)
			enderman_count = sum(1 for m in self.mobs if m.mob_type == "enderman")
			for _ in range(20):
				if enderman_count >= 16 or len(self.mobs) >= 20:
					break
				angle = random.uniform(0, math.tau)
				dist = random.uniform(14.0, 55.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				# Find End Stone (188) surface
				sy = None
				for y in range(80, 40, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id == 188:  # End Stone
						if (self.world.get_block_number((sx, y + 1, sz)) == 0 and
						    self.world.get_block_number((sx, y + 2, sz)) == 0 and
						    self.world.get_block_number((sx, y + 3, sz)) == 0):
							sy = y + 1
							break
				if sy is not None:
					pack = random.randint(1, 3)
					for _ in range(pack):
						if enderman_count >= 16:
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
		sun_y = math.cos((time_of_day - 0.5) * 2.0 * math.pi)
		sky_factor = 0.40 + 0.60 * max(0.0, min(1.0, (sun_y + 0.2) / 1.2))
		cur_light = max(int(round(sky_l * sky_factor)), blk_l)
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
						r_pick = random.random()
						if r_pick < 0.70 and blaze_count < self.max_blaze_mobs:
							pack = random.randint(2, 3)
						# Fortress: Wither Skeletons (35%), Skeletons (25%), Blazes (20%), Zombified Piglins (20%)
						roll = random.random()
						if roll < 0.35:
							self.spawn_mob("wither_skeleton", (sx, spawn_y, sz))
						elif roll < 0.60:
							self.spawn_mob("skeleton", (sx, spawn_y, sz))
						elif roll < 0.80:
							self.spawn_mob("blaze", (sx + random.uniform(-1.0, 1.0), spawn_y + random.uniform(0.2, 1.2), sz + random.uniform(-1.0, 1.0)))
						else:
							self.spawn_mob("zombie_pigman", (sx, spawn_y, sz))
					else:
						# General Nether Wilderness: Zombified Piglins (70%), Ghasts (15%), Magma Cubes (15%)
						roll = random.random()
						if roll < 0.70:
							self.spawn_mob("zombie_pigman", (sx, spawn_y, sz))
						elif roll < 0.85:
							self.spawn_mob("ghast", (sx, spawn_y + 4.0, sz))
						else:
							self.spawn_mob("magma_cube", (sx, spawn_y, sz))
			return

		if getattr(self.world, "dimension", "overworld") == "end":
			# End Hostile Spawning: ONLY Endermen spawn in the End! (No zombies, skeletons, spiders, creepers)
			end_count = len(self.mobs)
			if end_count >= self.max_end_mobs:
				return
			px, py, pz = player_pos
			for _ in range(8):
				if len(self.mobs) >= self.max_end_mobs:
					break
				angle = random.uniform(0, math.tau)
				dist = random.uniform(14.0, 48.0)
				sx = int(round(px + math.cos(angle) * dist))
				sz = int(round(pz + math.sin(angle) * dist))

				spawn_y = None
				for y in range(110, 15, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id in (87, 36, 12, 1) or (b_id != 0 and b_id not in (15, 20, 78, 183) and b_id not in block_state.PASSABLE_BLOCKS):
						# 3 air/passable blocks above for Enderman (tall 2.9 blocks hitbox)
						if (self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and
							self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS and
							self.world.get_block_number((sx, y + 3, sz)) in block_state.PASSABLE_BLOCKS):
							spawn_y = y + 1
							break

				if spawn_y is not None:
					pack = random.randint(1, 3)
					for _ in range(pack):
						if len(self.mobs) >= self.max_end_mobs:
							break
						off_x = sx + random.uniform(-1.5, 1.5)
						off_z = sz + random.uniform(-1.5, 1.5)
						self.spawn_mob("enderman", (off_x, spawn_y, off_z))
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
			attempts = min(12, needed * 2)
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
						if self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS:
							spawn_y = y + 1
							break

				if spawn_y is not None:
					# Overworld hostile mob rule: block light level must be 7 or lower!
					if not self.is_valid_overworld_hostile_light((sx, spawn_y, sz), time_of_day=time_of_day):
						continue

					mob_type = self.get_balanced_hostile_type()
					pack = 1 if mob_type == "enderman" else random.randint(1, 3)
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
						if self.world.get_block_number((sx, y + 1, sz)) in block_state.PASSABLE_BLOCKS and self.world.get_block_number((sx, y + 2, sz)) in block_state.PASSABLE_BLOCKS:
							# Check for solid ceiling above (cave)
							has_ceil = False
							for cy in range(y + 3, min(120, y + 18)):
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
			self.try_natural_spawning(player_pos)

		self.hostile_spawn_timer += dt
		if self.hostile_spawn_timer >= 1.5:
			self.hostile_spawn_timer = 0.0
			self.try_hostile_spawning(player_pos, time_of_day=time_of_day, flying=flying)

		px, py, pz = player_pos

		# Active Spawner Platform Spawner Tick (Every 4.0s)
		self.spawner_tick_timer += dt
		if self.spawner_tick_timer >= 4.0:
			self.spawner_tick_timer = 0.0
			# 1. Blaze Spawners (Nether Fortress)
			if getattr(self.world, "dimension", "overworld") == "nether" and player_pos and not flying:
				world_seed = getattr(self.world, "seed", 0)
				spawners = fortress_manager.get_nearby_spawner_positions(player_pos, seed=world_seed, radius=32)
				for spx, spy, spz in spawners:
					dist = math.sqrt((spx - px) ** 2 + (spy - py) ** 2 + (spz - pz) ** 2)
					if dist <= 24.0:
						nearby_blazes = sum(1 for m in self.mobs if m.mob_type == "blaze" and math.sqrt((m.position[0] - spx) ** 2 + (m.position[1] - spy) ** 2 + (m.position[2] - spz) ** 2) <= 16.0)
						if nearby_blazes < 6 and len(self.mobs) < self.max_nether_mobs:
							sp_count = random.randint(1, 3)
							for _ in range(sp_count):
								if len(self.mobs) >= self.max_nether_mobs:
									break
								off_x = spx + random.uniform(-2.0, 2.0)
								off_y = spy + random.uniform(0.5, 2.5)
								off_z = spz + random.uniform(-2.0, 2.0)
								self.spawn_mob("blaze", (off_x, off_y, off_z))

			# 2. Portal Room Silverfish Spawners (Overworld Strongholds)
			if getattr(self.world, "dimension", "overworld") == "overworld" and player_pos and not flying:
				world_seed = getattr(self.world, "seed", 0)
				try:
					sf_spawners = stronghold_manager.get_nearby_silverfish_spawners(player_pos, seed=world_seed, radius=32)
					for spx, spy, spz in sf_spawners:
						dist = math.sqrt((spx - px) ** 2 + (spy - py) ** 2 + (spz - pz) ** 2)
						if dist <= 16.0:
							nearby_sf = sum(1 for m in self.mobs if m.mob_type == "silverfish" and math.sqrt((m.position[0] - spx) ** 2 + (m.position[2] - spz) ** 2) <= 10.0)
							if nearby_sf < 6:
								for _ in range(random.randint(1, 2)):
									sx = spx + random.uniform(-1.0, 1.0)
									sy = spy + 0.1
									sz = spz + random.uniform(-1.0, 1.0)
									self.spawn_mob("silverfish", (sx, sy, sz))
				except Exception:
					pass

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
		if not self.mobs and not (hasattr(self, 'fireball_manager') and self.fireball_manager and self.fireball_manager.fireballs):
			return

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
				self.silverfish_model.draw(
					camera, mob.position, mob.yaw, mob.pitch,
					walk_time=mob.walk_time, hurt_time=mob.hurt_time,
					is_moving=mob.is_moving,
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
