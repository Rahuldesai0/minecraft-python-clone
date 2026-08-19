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


class MobManager:
	def __init__(self, world):
		self.world = world
		self.mobs = []
		self.next_entity_id = 1

		# Render Models for all 8 passive & hostile mobs
		self.pig_model = mob_model.PigModel()
		self.cow_model = mob_model.CowModel()
		self.sheep_model = mob_model.SheepModel()
		self.chicken_model = mob_model.ChickenModel()
		self.zombie_model = mob_model.ZombieModel()
		self.skeleton_model = mob_model.SkeletonModel()
		self.spider_model = mob_model.SpiderModel()
		self.creeper_model = mob_model.CreeperModel()

		# Spawning Parameters
		self.passive_spawn_timer = 0.0
		self.hostile_spawn_timer = 0.0
		self.max_passive_mobs = 24
		self.max_hostile_mobs = 28
		self.max_surface_hostiles = 20
		self.max_cave_hostiles = 8

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
		counts = {"zombie": 0, "skeleton": 0, "spider": 0, "creeper": 0}
		for m in self.mobs:
			if m.mob_type in counts:
				counts[m.mob_type] += 1
		min_count = min(counts.values())
		candidates = [t for t, c in counts.items() if c == min_count]
		return random.choice(candidates)

	def populate_initial_mobs(self, player_pos):
		"""Spawns an initial balanced population of passive mobs around spawn/player."""
		if len(self.mobs) >= 16:
			return

		px, py, pz = player_pos
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
		"""Spawns passive animal packs periodically near the player if below cap."""
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

	def try_hostile_spawning(self, player_pos, time_of_day=0.5, flying=False):
		"""Spawns hostile mobs in Survival mode during night on surface or anytime underground/caves."""
		if flying or not player_pos:
			return  # Hostiles do not spawn in Creative/Fly mode!

		px, py, pz = player_pos
		tod = time_of_day % 1.0
		is_night = (tod <= 0.25 or tod >= 0.73)

		surface_hostiles = sum(1 for m in self.mobs if m.mob_type in ("zombie", "skeleton", "spider", "creeper") and m.position[1] >= 55)
		cave_hostiles = sum(1 for m in self.mobs if m.mob_type in ("zombie", "skeleton", "spider", "creeper") and m.position[1] < 55)
		total_hostiles = surface_hostiles + cave_hostiles

		if total_hostiles >= self.max_hostile_mobs:
			return

		# 1. Nighttime Surface Spawning (Generous pack spawning across open terrain)
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

				# Scan down from world top to find top solid surface block
				spawn_y = None
				for y in range(130, 48, -1):
					b_id = self.world.get_block_number((sx, y, sz))
					if b_id != 0 and b_id not in (9, 19, 15, 20, 78, 13, 14, 18):
						# 2 air blocks above for mob clearance
						if self.world.get_block_number((sx, y + 1, sz)) == 0 and self.world.get_block_number((sx, y + 2, sz)) == 0:
							spawn_y = y + 1
							break

				if spawn_y is not None:
					mob_type = self.get_balanced_hostile_type()
					pack = random.randint(1, 3)
					for _ in range(pack):
						if surface_hostiles >= self.max_surface_hostiles or total_hostiles >= self.max_hostile_mobs:
							break
						off_x = sx + random.uniform(-1.0, 1.0)
						off_z = sz + random.uniform(-1.0, 1.0)
						self.spawn_mob(mob_type, (off_x, spawn_y, off_z))
						surface_hostiles += 1
						total_hostiles += 1

		# 2. Underground / Cave Spawning (Allowed anytime in covered caverns)
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
					if b_id != 0 and b_id not in (9, 19, 15, 20, 78, 13, 14, 18):
						if self.world.get_block_number((sx, y + 1, sz)) == 0 and self.world.get_block_number((sx, y + 2, sz)) == 0:
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
					mob_type = self.get_balanced_hostile_type()
					self.spawn_mob(mob_type, (sx, spawn_y, sz))
					cave_hostiles += 1

	def update(self, dt, player_pos, camera=None, gui=None, tnt_manager=None, item_drop_manager=None, arrow_manager=None, time_of_day=0.5, flying=False):
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
		i = 0
		while i < len(self.mobs):
			mob = self.mobs[i]

			dx = mob.position[0] - px
			dy = mob.position[1] - py
			dz = mob.position[2] - pz
			dist_sq = dx * dx + dy * dy + dz * dz

			# Despawn distant mobs (Hostiles beyond 56 blocks, Passives beyond 96 blocks)
			is_hostile = mob.mob_type in ("zombie", "skeleton", "spider", "creeper")
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
					time_of_day=time_of_day, flying=flying
				)

			# Process dead mob drops & removal
			if mob.is_dead:
				drops, xp = mob.get_loot_drops(is_on_fire=(mob.fire_timer > 0))
				if item_drop_manager:
					for b_id, count in drops:
						item_drop_manager.spawn_drop(b_id, count, mob.position)
				self.mobs.pop(i)
				continue

			i += 1

	def attack_mob_at_crosshair(self, camera, max_reach=5.0, damage=4):
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
			closest_mob.take_damage(damage, attacker_pos=camera.position)
			return True
		return False

	def draw(self, camera):
		"""Render active 3D models for all 8 passive and hostile mobs."""
		if not self.mobs:
			return

		for mob in self.mobs:
			if mob.mob_type == "pig":
				self.pig_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time
				)
			elif mob.mob_type == "cow":
				self.cow_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time
				)
			elif mob.mob_type == "sheep":
				self.sheep_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_grazing=getattr(mob, "is_grazing", False)
				)
			elif mob.mob_type == "chicken":
				self.chicken_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					wing_flap=getattr(mob, "wing_flap", 0.0)
				)
			elif mob.mob_type == "zombie":
				self.zombie_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					attack_anim_time=getattr(mob, "attack_anim_time", 0.0)
				)
			elif mob.mob_type == "skeleton":
				self.skeleton_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_aiming=getattr(mob, "is_aiming", False)
				)
			elif mob.mob_type == "spider":
				self.spider_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					is_climbing=getattr(mob, "is_climbing", False)
				)
			elif mob.mob_type == "creeper":
				self.creeper_model.render(
					camera, mob.position, mob.yaw, mob.pitch,
					mob.walk_time, mob.is_moving, mob.hurt_time,
					fuse_progress=getattr(mob, "fuse_progress", 0.0)
				)
