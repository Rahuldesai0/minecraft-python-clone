"""
Minecraft Passive Mob Entities & AI System (Pig & Cow)
------------------------------------------------------
Implements PigEntity and CowEntity with attributes, physics collisions,
AI Goals (RandomStrollGoal, LookAroundGoal, PanicGoal), damage processing, and drops.
"""

import math
import random


class RandomStrollGoal:
	def __init__(self, mob):
		self.mob = mob
		self.cooldown = random.uniform(2.0, 5.0)

	def update(self, dt):
		self.cooldown -= dt
		if self.cooldown <= 0:
			self.cooldown = random.uniform(4.0, 8.0)
			# Pick random target within 6-8 blocks
			angle = random.uniform(0, math.tau)
			dist = random.uniform(4.0, 8.0)
			target_x = self.mob.position[0] + math.cos(angle) * dist
			target_z = self.mob.position[2] + math.sin(angle) * dist
			self.mob.set_target_destination(target_x, target_z)


class LookAroundGoal:
	def __init__(self, mob):
		self.mob = mob
		self.cooldown = random.uniform(1.0, 3.0)

	def update(self, dt):
		self.cooldown -= dt
		if self.cooldown <= 0:
			self.cooldown = random.uniform(2.0, 5.0)
			self.mob.target_pitch = random.uniform(-0.25, 0.25)


class PanicGoal:
	def __init__(self, mob):
		self.mob = mob
		self.panic_timer = 0.0

	def trigger(self, attacker_pos=None):
		self.panic_timer = 2.5
		if attacker_pos:
			# Flee directly away from attacker
			dx = self.mob.position[0] - attacker_pos[0]
			dz = self.mob.position[2] - attacker_pos[2]
			length = math.sqrt(dx * dx + dz * dz)
			if length > 0.001:
				target_x = self.mob.position[0] + (dx / length) * 12.0
				target_z = self.mob.position[2] + (dz / length) * 12.0
				self.mob.set_target_destination(target_x, target_z, speed_mult=1.6)
		else:
			angle = random.uniform(0, math.tau)
			target_x = self.mob.position[0] + math.cos(angle) * 10.0
			target_z = self.mob.position[2] + math.sin(angle) * 10.0
			self.mob.set_target_destination(target_x, target_z, speed_mult=1.6)

	def update(self, dt):
		if self.panic_timer > 0:
			self.panic_timer -= dt


class MobEntity:
	def __init__(self, entity_id, position, mob_type, max_health=10, speed=0.25, width=0.9, height=0.9):
		self.entity_id = entity_id
		self.position = list(position)  # [x, y, z]
		self.mob_type = mob_type
		self.max_health = max_health
		self.health = max_health
		self.speed = speed
		self.width = width
		self.height = height

		self.yaw = random.uniform(0, math.tau)
		self.pitch = 0.0
		self.target_yaw = self.yaw
		self.target_pitch = 0.0

		self.velocity = [0.0, 0.0, 0.0]
		self.on_ground = False
		self.walk_time = random.uniform(0, 100.0)
		self.is_moving = False
		self.hurt_time = 0.0
		self.is_dead = False
		self.fire_timer = 0.0
		self.fire_damage_timer = 0.0

		self.target_dest = None
		self.speed_mult = 1.0

		# AI Goals
		self.stroll_goal = RandomStrollGoal(self)
		self.look_goal = LookAroundGoal(self)
		self.panic_goal = PanicGoal(self)

	def set_target_destination(self, x, z, speed_mult=1.0):
		self.target_dest = (x, z)
		self.speed_mult = speed_mult

	def is_touching_fire(self, world):
		"""Checks if the mob's bounding box intersects a Fire block (78)."""
		mx, my, mz = self.position
		half_w = self.width / 2.0
		min_bx = int(math.floor(mx - half_w + 0.5))
		max_bx = int(math.floor(mx + half_w + 0.5))
		min_by = int(math.floor(my + 0.5))
		max_by = int(math.floor(my + self.height + 0.5))
		min_bz = int(math.floor(mz - half_w + 0.5))
		max_bz = int(math.floor(mz + half_w + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num == 78 or (bx, by, bz) in getattr(world, 'active_fires', {}):
						return True
		return False

	def is_in_water(self, world):
		"""Checks if the mob's bounding box touches water (9 or 19)."""
		mx, my, mz = self.position
		half_w = self.width / 2.0
		min_bx = int(math.floor(mx - half_w + 0.5))
		max_bx = int(math.floor(mx + half_w + 0.5))
		min_by = int(math.floor(my + 0.5))
		max_by = int(math.floor(my + self.height + 0.5))
		min_bz = int(math.floor(mz - half_w + 0.5))
		max_bz = int(math.floor(mz + half_w + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num in (9, 19):
						return True
		return False

	def is_in_lava(self, world):
		"""Checks if the mob's bounding box touches lava (15 or 20)."""
		mx, my, mz = self.position
		half_w = self.width / 2.0
		min_bx = int(math.floor(mx - half_w + 0.5))
		max_bx = int(math.floor(mx + half_w + 0.5))
		min_by = int(math.floor(my + 0.5))
		max_by = int(math.floor(my + self.height + 0.5))
		min_bz = int(math.floor(mz - half_w + 0.5))
		max_bz = int(math.floor(mz + half_w + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num in (15, 20):
						return True
		return False

	def take_damage(self, damage, attacker_pos=None, is_fire=False):
		if self.is_dead or damage <= 0:
			return

		self.health = max(0, self.health - damage)
		self.hurt_time = 0.4
		self.panic_goal.trigger(attacker_pos)

		if self.health == 0:
			self.is_dead = True

	def update(self, dt, world, player_pos):
		if self.is_dead:
			return

		if self.hurt_time > 0:
			self.hurt_time = max(0.0, self.hurt_time - dt)

		# Fire, Lava & Water physics / damage
		if self.is_in_water(world):
			self.fire_timer = 0.0
			self.fire_damage_timer = 0.0
		else:
			in_lava = self.is_in_lava(world)
			touching_fire = self.is_touching_fire(world)

			if in_lava or touching_fire:
				self.fire_timer = max(self.fire_timer, random.uniform(5.0, 6.0))

			if in_lava:
				# Lava deals heavy damage (4 HP every 0.5s)
				self.fire_damage_timer += dt
				if self.fire_damage_timer >= 0.5:
					self.fire_damage_timer = 0.0
					self.take_damage(4, is_fire=True)
			elif self.fire_timer > 0.0:
				self.fire_timer = max(0.0, self.fire_timer - dt)
				self.fire_damage_timer += dt
				damage_interval = 0.8 if touching_fire else 1.0
				if self.fire_damage_timer >= damage_interval:
					self.fire_damage_timer = 0.0
					self.take_damage(1, is_fire=True)
			else:
				self.fire_damage_timer = 0.0

		# Tick AI Goals
		self.panic_goal.update(dt)
		if self.panic_goal.panic_timer <= 0:
			self.stroll_goal.update(dt)
		self.look_goal.update(dt)

		# Path movement toward target destination
		if self.target_dest is not None:
			tx, tz = self.target_dest
			dx = tx - self.position[0]
			dz = tz - self.position[2]
			dist = math.sqrt(dx * dx + dz * dz)

			if dist < 0.5:
				self.target_dest = None
				self.is_moving = False
				self.velocity[0] = 0.0
				self.velocity[2] = 0.0
			else:
				self.target_yaw = math.atan2(dx, dz)
				move_speed = self.speed * 4.3 * self.speed_mult
				self.velocity[0] = (dx / dist) * move_speed
				self.velocity[2] = (dz / dist) * move_speed
				self.is_moving = True
		else:
			self.velocity[0] = 0.0
			self.velocity[2] = 0.0
			self.is_moving = False

		# Smooth body yaw & head pitch rotation
		yaw_diff = (self.target_yaw - self.yaw + math.pi) % math.tau - math.pi
		self.yaw += yaw_diff * min(1.0, 8.0 * dt)
		self.pitch += (self.target_pitch - self.pitch) * min(1.0, 8.0 * dt)

		if self.is_moving:
			self.walk_time += dt * 8.0 * self.speed_mult

		# Gravity & Ground Collision
		if not self.on_ground:
			self.velocity[1] -= 24.0 * dt
			self.velocity[1] = max(-30.0, self.velocity[1])
		else:
			# Auto-jump over 1-block obstacles while moving forward
			if self.is_moving:
				ahead_x = self.position[0] + self.velocity[0] * 0.4
				ahead_z = self.position[2] + self.velocity[2] * 0.4
				bx, by, bz = int(round(ahead_x)), int(round(self.position[1])), int(round(ahead_z))
				if world.get_block_number((bx, by, bz)) != 0:
					self.velocity[1] = 6.5
					self.on_ground = False

		nx = self.position[0] + self.velocity[0] * dt
		ny = self.position[1] + self.velocity[1] * dt
		nz = self.position[2] + self.velocity[2] * dt

		# Check ground collision
		feet_bx, feet_by, feet_bz = int(round(nx)), int(math.floor(ny)), int(round(nz))
		if world.get_block_number((feet_bx, feet_by, feet_bz)) != 0:
			self.velocity[1] = 0.0
			self.on_ground = True
			self.position[1] = feet_by + 1.0
		else:
			self.on_ground = False
			self.position[1] = ny

		self.position[0] = nx
		self.position[2] = nz


class PigEntity(MobEntity):
	def __init__(self, entity_id, position):
		# Pig attributes: 10 HP (5 hearts), speed = 0.25
		super().__init__(entity_id, position, mob_type="pig", max_health=10, speed=0.25, width=0.9, height=0.9)

	def get_loot_drops(self, is_on_fire=False):
		"""Minecraft Pig Loot Table: 1-3 Raw Porkchops (125) or Cooked Porkchops (128) + 1-3 XP."""
		count = random.randint(1, 3)
		item_id = 128 if is_on_fire else 125
		xp = random.randint(1, 3)
		return [(item_id, count)], xp


class CowEntity(MobEntity):
	def __init__(self, entity_id, position):
		# Cow attributes: 10 HP (5 hearts), speed = 0.20
		super().__init__(entity_id, position, mob_type="cow", max_health=10, speed=0.20, width=0.9, height=1.4)

	def get_loot_drops(self, is_on_fire=False):
		"""Minecraft Cow Loot Table: 0-2 Leather (126) + 1-3 Raw Beef (127) or Steak (129) + 1-3 XP."""
		beef_count = random.randint(1, 3)
		beef_id = 129 if is_on_fire else 127
		leather_count = random.randint(0, 2)
		xp = random.randint(1, 3)

		drops = [(beef_id, beef_count)]
		if leather_count > 0:
			drops.append((126, leather_count))
		return drops, xp
