"""
Minecraft Passive Mob Spawning, Simulation, & Rendering Manager
----------------------------------------------------------------
Implements natural mob population spawning on Grass blocks, entity distance-based
simulation capping, mob rendering, and player hit detection.
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

		# Render Models
		self.pig_model = mob_model.PigModel()
		self.cow_model = mob_model.CowModel()

		# Spawning Parameters
		self.spawn_timer = 0.0
		self.max_passive_mobs = 16

	def spawn_mob(self, mob_type, position):
		eid = self.next_entity_id
		self.next_entity_id += 1

		if mob_type == "pig":
			mob = mob_entity.PigEntity(eid, position)
		else:
			mob = mob_entity.CowEntity(eid, position)

		self.mobs.append(mob)
		return mob

	def try_natural_spawning(self, player_pos):
		if len(self.mobs) >= self.max_passive_mobs:
			return

		px, py, pz = player_pos
		# Choose random spawn location 24 to 64 blocks away from player
		angle = random.uniform(0, math.tau)
		dist = random.uniform(24.0, 64.0)
		sx = int(round(px + math.cos(angle) * dist))
		sz = int(round(pz + math.sin(angle) * dist))

		# Find top solid block height
		sy = 0
		for y in range(120, 40, -1):
			b_id = self.world.get_block_number((sx, y, sz))
			if b_id == 2:  # Grass Block
				above_id = self.world.get_block_number((sx, y + 1, sz))
				if above_id == 0:  # Air
					sy = y + 1
					break

		if sy > 0:
			# Valid spawn surface on Grass block! Spawn group of 2-3 mobs
			mob_type = random.choice(["pig", "cow"])
			group_size = random.randint(2, 3)
			for i in range(group_size):
				if len(self.mobs) >= self.max_passive_mobs:
					break
				off_x = sx + random.uniform(-2.0, 2.0)
				off_z = sz + random.uniform(-2.0, 2.0)
				self.spawn_mob(mob_type, (off_x, sy, off_z))

	def update(self, dt, player_pos, item_drop_manager=None):
		# Throttled natural mob spawning every 3 seconds
		self.spawn_timer += dt
		if self.spawn_timer >= 3.0:
			self.spawn_timer = 0.0
			self.try_natural_spawning(player_pos)

		px, py, pz = player_pos
		i = 0
		while i < len(self.mobs):
			mob = self.mobs[i]

			dx = mob.position[0] - px
			dy = mob.position[1] - py
			dz = mob.position[2] - pz
			dist_sq = dx * dx + dy * dy + dz * dz

			# Despawn distant mobs beyond 128 blocks
			if dist_sq > 16384.0:
				self.mobs.pop(i)
				continue

			# Simulation Distance Capping: Only run full AI & Physics for mobs within 64 blocks
			if dist_sq <= 4096.0:
				mob.update(dt, self.world, player_pos)

			# Process dead mob drops & removal
			if mob.is_dead:
				drops, xp = mob.get_loot_drops()
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
		"""Render active Pig and Cow 3D models."""
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
