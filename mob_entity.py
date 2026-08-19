"""
Minecraft Passive Mob Entities & AI System (Cow, Pig, Sheep, Chicken)
----------------------------------------------------------------------
Implements CowEntity, PigEntity, SheepEntity, and ChickenEntity with authentic attributes,
terrain physics collisions, hazard avoidance (water, lava, cliffs), Minecraft-style
environmental damage (fire, lava, drowning, fall damage), panic fleeing, and fire-extinguishing AI.
"""

import math
import random


def is_liquid_or_fire_block(block_id):
	"""Returns True if the block is water, lava, or fire."""
	return block_id in (9, 19, 15, 20, 78)


def is_water_block(block_id):
	"""Returns True if the block is water source or flowing water."""
	return block_id in (9, 19)


def is_lava_block(block_id):
	"""Returns True if the block is lava source or flowing lava."""
	return block_id in (15, 20)


def is_walkable_ground(block_id):
	"""Returns True if the block is a valid ground block for mobs to walk on (rejects liquids, fire, and leaves)."""
	return block_id != 0 and block_id not in (9, 19, 15, 20, 78, 13, 14, 18)


class RandomStrollGoal:
	"""AI Goal: Pick occasional safe destinations and wander without walking into hazards, trees, or cliffs."""
	def __init__(self, mob):
		self.mob = mob
		self.cooldown = random.uniform(2.0, 5.0)

	def update(self, dt, world):
		self.cooldown -= dt
		if self.cooldown <= 0:
			self.cooldown = random.uniform(4.0, 9.0)

			# Try picking a safe destination avoiding water, lava, leaves, and cliffs
			for _ in range(8):
				angle = random.uniform(0, math.tau)
				dist = random.uniform(4.0, 8.0)
				tx = self.mob.position[0] + math.cos(angle) * dist
				tz = self.mob.position[2] + math.sin(angle) * dist

				if self.is_destination_safe(tx, tz, world):
					self.mob.set_target_destination(tx, tz, speed_mult=1.0)
					break

	def is_destination_safe(self, tx, tz, world):
		"""Checks if the destination has solid ground, is not liquid/fire/leaves, and has 2-block headroom."""
		bx = int(math.floor(tx))
		bz = int(math.floor(tz))
		curr_y = int(math.floor(self.mob.position[1]))

		# Search around current Y level (within +1 to -3 blocks) for ground surface
		ground_y = None
		for dy in range(1, -4, -1):
			check_y = curr_y + dy
			b_curr = world.get_block_number((bx, check_y, bz))
			b_above1 = world.get_block_number((bx, check_y + 1, bz))
			b_above2 = world.get_block_number((bx, check_y + 2, bz))

			if is_walkable_ground(b_curr) and b_above1 == 0 and b_above2 == 0:
				ground_y = check_y
				break

		if ground_y is None:
			return False

		# Must not be a steep jump up (> 1.2 blocks) or steep drop (> 2.5 blocks)
		y_diff = (ground_y + 1.0) - self.mob.position[1]
		if y_diff > 1.2 or y_diff < -2.5:
			return False

		return True


class LookAroundGoal:
	"""AI Goal: Periodically look around with subtle head pitch & yaw variations."""
	def __init__(self, mob):
		self.mob = mob
		self.cooldown = random.uniform(1.5, 4.0)

	def update(self, dt):
		self.cooldown -= dt
		if self.cooldown <= 0:
			self.cooldown = random.uniform(2.5, 6.0)
			self.mob.target_pitch = random.uniform(-0.25, 0.25)
			if not self.mob.is_moving:
				self.mob.target_yaw += random.uniform(-0.6, 0.6)


class PanicGoal:
	"""AI Goal: When damaged, flee away from attacker at high speed while avoiding hazards."""
	def __init__(self, mob):
		self.mob = mob
		self.panic_timer = 0.0
		self.repath_timer = 0.0
		self.attacker_pos = None

	def trigger(self, attacker_pos=None):
		self.panic_timer = random.uniform(4.0, 6.0)
		self.repath_timer = 0.0
		self.attacker_pos = attacker_pos

	def update(self, dt, world):
		if self.panic_timer <= 0:
			return

		self.panic_timer -= dt
		self.repath_timer -= dt

		if self.repath_timer <= 0 or self.mob.target_dest is None:
			self.repath_timer = random.uniform(1.0, 2.0)

			# Choose a fleeing direction away from attacker with random jitter
			if self.attacker_pos:
				dx = self.mob.position[0] - self.attacker_pos[0]
				dz = self.mob.position[2] - self.attacker_pos[2]
				base_angle = math.atan2(dx, dz)
			else:
				base_angle = random.uniform(0, math.tau)

			best_tx, best_tz = None, None
			for angle_offset in (0.0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2):
				angle = base_angle + angle_offset + random.uniform(-0.2, 0.2)
				dist = random.uniform(10.0, 14.0)
				tx = self.mob.position[0] + math.sin(angle) * dist
				tz = self.mob.position[2] + math.cos(angle) * dist

				if self.is_safe_flee_target(tx, tz, world):
					best_tx, best_tz = tx, tz
					break

			if best_tx is not None:
				self.mob.set_target_destination(best_tx, best_tz, speed_mult=1.6)
			else:
				# Fallback flee target
				angle = base_angle + random.uniform(-0.5, 0.5)
				dist = 10.0
				tx = self.mob.position[0] + math.sin(angle) * dist
				tz = self.mob.position[2] + math.cos(angle) * dist
				self.mob.set_target_destination(tx, tz, speed_mult=1.6)

	def is_safe_flee_target(self, tx, tz, world):
		bx = int(math.floor(tx))
		bz = int(math.floor(tz))
		curr_y = int(math.floor(self.mob.position[1]))

		for dy in range(1, -4, -1):
			check_y = curr_y + dy
			b_curr = world.get_block_number((bx, check_y, bz))
			b_above1 = world.get_block_number((bx, check_y + 1, bz))
			b_above2 = world.get_block_number((bx, check_y + 2, bz))
			if is_walkable_ground(b_curr) and b_above1 == 0 and b_above2 == 0:
				y_diff = (check_y + 1.0) - self.mob.position[1]
				if -2.5 <= y_diff <= 1.2:
					return True
		return False


class FireExtinguishGoal:
	"""AI Goal: When burning, seek nearby safe reachable water to extinguish fire."""
	def __init__(self, mob):
		self.mob = mob
		self.scan_cooldown = 0.0

	def update(self, dt, world):
		if self.mob.fire_timer <= 0 or self.mob.is_in_water(world):
			return

		self.scan_cooldown -= dt
		if self.scan_cooldown <= 0:
			self.scan_cooldown = 1.0

			mx, my, mz = self.mob.position
			curr_bx, curr_by, curr_bz = int(math.floor(mx)), int(math.floor(my)), int(math.floor(mz))

			best_water = None
			min_dist_sq = float('inf')

			# Scan in a 10x4x10 area for safe water
			for dx in range(-8, 9):
				for dz in range(-8, 9):
					for dy in range(-2, 3):
						bx, by, bz = curr_bx + dx, curr_by + dy, curr_bz + dz
						b_id = world.get_block_number((bx, by, bz))

						if is_water_block(b_id):
							# Check that there is no adjacent lava
							has_lava = False
							for adj_x, adj_z in ((1,0), (-1,0), (0,1), (0,-1)):
								if is_lava_block(world.get_block_number((bx + adj_x, by, bz + adj_z))):
									has_lava = True
									break

							if not has_lava:
								d_sq = dx * dx + dy * dy + dz * dz
								if d_sq < min_dist_sq:
									min_dist_sq = d_sq
									best_water = (bx + 0.5, bz + 0.5)

			if best_water:
				self.mob.set_target_destination(best_water[0], best_water[1], speed_mult=1.4)


class MobEntity:
	"""Base dynamic passive mob entity with full Minecraft physics, AI, damage, and animations."""
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
		self.fall_start_y = None
		self.walk_time = random.uniform(0, 100.0)
		self.is_moving = False
		self.hurt_time = 0.0
		self.is_dead = False

		# Environmental & Damage state (consistent with player camera mechanics)
		self.fire_timer = 0.0
		self.fire_damage_timer = 0.0
		self.air = 10.0
		self.max_air = 10.0
		self.drown_damage_timer = 0.0

		# Navigation & Goals
		self.target_dest = None
		self.speed_mult = 1.0

		self.stroll_goal = RandomStrollGoal(self)
		self.look_goal = LookAroundGoal(self)
		self.panic_goal = PanicGoal(self)
		self.extinguish_goal = FireExtinguishGoal(self)

		# Animation states
		self.wing_flap = 0.0
		self.grazing_timer = 0.0
		self.is_grazing = False

	def set_target_destination(self, x, z, speed_mult=1.0):
		self.target_dest = (x, z)
		self.speed_mult = speed_mult

	def is_touching_fire(self, world):
		"""Checks if the mob's bounding box intersects a Fire block (78)."""
		mx, my, mz = self.position
		half_w = self.width / 2.0
		min_bx = int(math.floor(mx - half_w))
		max_bx = int(math.floor(mx + half_w))
		min_by = int(math.floor(my))
		max_by = int(math.floor(my + self.height))
		min_bz = int(math.floor(mz - half_w))
		max_bz = int(math.floor(mz + half_w))

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
		min_bx = int(math.floor(mx - half_w))
		max_bx = int(math.floor(mx + half_w))
		min_by = int(math.floor(my))
		max_by = int(math.floor(my + self.height))
		min_bz = int(math.floor(mz - half_w))
		max_bz = int(math.floor(mz + half_w))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if is_water_block(b_num):
						return True
		return False

	def is_in_lava(self, world):
		"""Checks if the mob's bounding box touches lava (15 or 20)."""
		mx, my, mz = self.position
		half_w = self.width / 2.0
		min_bx = int(math.floor(mx - half_w))
		max_bx = int(math.floor(mx + half_w))
		min_by = int(math.floor(my))
		max_by = int(math.floor(my + self.height))
		min_bz = int(math.floor(mz - half_w))
		max_bz = int(math.floor(mz + half_w))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if is_lava_block(b_num):
						return True
		return False

	def is_head_underwater(self, world):
		"""Checks if the mob's head is submerged in water."""
		mx, my, mz = self.position
		head_y = my + self.height * 0.85
		b_head = world.get_block_number((int(math.floor(mx)), int(math.floor(head_y)), int(math.floor(mz))))
		return is_water_block(b_head)

	def take_damage(self, damage, attacker_pos=None, is_fire=False, is_drowning=False, is_fall=False):
		"""Applies damage, flashes red, and enters directional panic fleeing state."""
		if self.is_dead or damage <= 0:
			return

		self.health = max(0, self.health - damage)
		self.hurt_time = 0.4
		self.panic_goal.trigger(attacker_pos)

		if self.health == 0:
			self.is_dead = True

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, **kwargs):
		if self.is_dead:
			return

		if self.hurt_time > 0:
			self.hurt_time = max(0.0, self.hurt_time - dt)

		in_water = self.is_in_water(world)
		in_lava = self.is_in_lava(world)
		touching_fire = self.is_touching_fire(world)

		# 1. Fire & Lava Mechanics
		if in_water:
			self.fire_timer = 0.0
			self.fire_damage_timer = 0.0
		else:
			if in_lava:
				self.fire_timer = 15.0
				self.fire_damage_timer += dt
				if self.fire_damage_timer >= 0.5:
					self.fire_damage_timer = 0.0
					self.take_damage(4, is_fire=True)
			elif touching_fire:
				self.fire_timer = max(self.fire_timer, random.uniform(5.0, 6.0))
				self.fire_damage_timer += dt
				if self.fire_damage_timer >= 0.8:
					self.fire_damage_timer = 0.0
					self.take_damage(1, is_fire=True)
			elif self.fire_timer > 0.0:
				self.fire_timer = max(0.0, self.fire_timer - dt)
				self.fire_damage_timer += dt
				if self.fire_damage_timer >= 1.0:
					self.fire_damage_timer = 0.0
					self.take_damage(1, is_fire=True)
			else:
				self.fire_damage_timer = 0.0

		# 2. Oxygen & Drowning Mechanics
		head_underwater = self.is_head_underwater(world)
		if head_underwater:
			self.air = max(0.0, self.air - dt)
			if self.air <= 0.0:
				self.drown_damage_timer += dt
				if self.drown_damage_timer >= 1.0:
					self.drown_damage_timer = 0.0
					self.take_damage(2, is_drowning=True)
			else:
				self.drown_damage_timer = 0.0
		else:
			self.drown_damage_timer = 0.0
			if self.air < self.max_air:
				self.air = min(self.max_air, self.air + dt * 2.0)

		# 3. AI Goal Decisions
		if self.fire_timer > 0.0 and not in_water:
			self.extinguish_goal.update(dt, world)

		self.panic_goal.update(dt, world)

		if self.panic_goal.panic_timer <= 0 and (self.fire_timer <= 0.0 or in_water):
			if getattr(self, 'target', None) is None:
				self.stroll_goal.update(dt, world)

		self.look_goal.update(dt)

		# 4. Movement Execution & Hazard Check Ahead
		if self.target_dest is not None:
			tx, tz = self.target_dest
			dx = tx - self.position[0]
			dz = tz - self.position[2]
			dist = math.sqrt(dx * dx + dz * dz)

			if dist < 0.4:
				self.target_dest = None
				self.is_moving = False
				self.velocity[0] = 0.0
				self.velocity[2] = 0.0
			else:
				self.target_yaw = math.atan2(dx, dz)
				move_speed = self.speed * 4.3 * self.speed_mult

				# Check ahead for water, lava, fire, or cliff hazards
				ahead_dist = 0.8
				ahead_x = self.position[0] + (dx / dist) * ahead_dist
				ahead_z = self.position[2] + (dz / dist) * ahead_dist
				abx, abz = int(math.floor(ahead_x)), int(math.floor(ahead_z))
				curr_by = int(math.floor(self.position[1]))

				ahead_block = world.get_block_number((abx, curr_by, abz))
				ahead_below = world.get_block_number((abx, curr_by - 1, abz))
				ahead_deep  = world.get_block_number((abx, curr_by - 2, abz))

				is_hazard = is_liquid_or_fire_block(ahead_block) or is_liquid_or_fire_block(ahead_below) or is_liquid_or_fire_block(ahead_deep)
				is_cliff = (ahead_block == 0 and ahead_below == 0 and ahead_deep == 0)

				# Avoid walking into water/lava unless extinguishing fire in water
				is_seeking_water = (self.fire_timer > 0.0 and (is_water_block(ahead_block) or is_water_block(ahead_below) or is_water_block(ahead_deep)))
				if not is_seeking_water and (is_hazard or is_cliff):
					# Hazard directly ahead! Stop and clear destination
					self.target_dest = None
					self.is_moving = False
					self.velocity[0] = 0.0
					self.velocity[2] = 0.0
				else:
					self.velocity[0] = (dx / dist) * move_speed
					self.velocity[2] = (dz / dist) * move_speed
					self.is_moving = True
		else:
			self.velocity[0] = 0.0
			self.velocity[2] = 0.0
			self.is_moving = False

		# 5. Smooth Body Rotation
		yaw_diff = (self.target_yaw - self.yaw + math.pi) % math.tau - math.pi
		self.yaw += yaw_diff * min(1.0, 8.0 * dt)
		self.pitch += (self.target_pitch - self.pitch) * min(1.0, 8.0 * dt)

		if self.is_moving:
			self.walk_time += dt * 8.0 * self.speed_mult

		# 6. Gravity, Obstacle Step-Jumping & Collision Resolution
		if getattr(self, "is_climbing", False):
			# Spider wall climbing overrides gravity and ascends vertically
			self.fall_start_y = None
			self.velocity[1] = 3.5
			self.position[1] += self.velocity[1] * dt
			self.position[0] += self.velocity[0] * dt
			self.position[2] += self.velocity[2] * dt
		elif in_water or in_lava:
			# Buoyancy in liquids with terminal upward swim speed
			self.fall_start_y = None
			if in_water:
				self.velocity[1] = min(2.0, max(-2.0, self.velocity[1] + 8.0 * dt))
			else:
				self.velocity[1] = min(1.5, max(-1.5, self.velocity[1] + 5.0 * dt))
			self.position[0] += self.velocity[0] * dt
			self.position[2] += self.velocity[2] * dt

			# Vertical movement with swept ceiling check
			ny = self.position[1] + self.velocity[1] * dt
			hw = (self.width / 2.0) * 0.7
			if self.velocity[1] > 0.0:
				min_cy = int(math.floor(self.position[1] + self.height))
				max_cy = int(math.floor(ny + self.height))
				hit_ceil = None
				for cy in range(min_cy, max_cy + 1):
					for chk_bx in (int(math.floor(self.position[0] - hw)), int(math.floor(self.position[0] + hw))):
						for chk_bz in (int(math.floor(self.position[2] - hw)), int(math.floor(self.position[2] + hw))):
							b_ceil = world.get_block_number((chk_bx, cy, chk_bz))
							if b_ceil != 0 and not is_liquid_or_fire_block(b_ceil):
								hit_ceil = cy
								break
						if hit_ceil is not None:
							break
					if hit_ceil is not None:
						break

				if hit_ceil is not None:
					self.velocity[1] = 0.0
					ny = float(hit_ceil) - self.height - 0.01
			self.position[1] = ny
		else:
			# Airborne gravity vs Ground handling
			if not self.on_ground:
				if self.fall_start_y is None or self.position[1] > self.fall_start_y:
					self.fall_start_y = self.position[1]

				if self.mob_type == "chicken":
					self.velocity[1] = max(-2.5, self.velocity[1] - 12.0 * dt)
					self.wing_flap += dt * 18.0
				else:
					self.velocity[1] = max(-30.0, self.velocity[1] - 26.0 * dt)
			else:
				# Landing fall damage check
				if self.fall_start_y is not None:
					fall_dist = self.fall_start_y - self.position[1]
					if fall_dist > 3.0 and self.mob_type != "chicken":
						dmg = int(round(fall_dist - 3.0))
						if dmg > 0:
							self.take_damage(dmg, is_fall=True)
					self.fall_start_y = None

				# Auto-jump over 1-block obstacles while moving on ground
				if self.is_moving and self.velocity[1] <= 0.0:
					yaw = self.yaw
					ahead_x = self.position[0] + math.sin(yaw) * 0.45
					ahead_z = self.position[2] + math.cos(yaw) * 0.45
					curr_by = int(math.floor(self.position[1]))
					abx, abz = int(math.floor(ahead_x)), int(math.floor(ahead_z))

					b_obs = world.get_block_number((abx, curr_by, abz))
					b_above1 = world.get_block_number((abx, curr_by + 1, abz))
					b_above2 = world.get_block_number((abx, curr_by + 2, abz))

					curr_bx, curr_bz = int(math.floor(self.position[0])), int(math.floor(self.position[2]))
					headroom_curr = (world.get_block_number((curr_bx, curr_by + 1, curr_bz)) == 0 and
					                 world.get_block_number((curr_bx, curr_by + 2, curr_bz)) == 0)
					headroom_ahead = (b_above1 == 0 and b_above2 == 0)

					# Only jump if obstacle is valid walkable ground and headroom is clear
					if is_walkable_ground(b_obs) and headroom_ahead and headroom_curr:
						self.velocity[1] = 4.6  # Authentic Minecraft 1.2-block step jump
						self.on_ground = False

			# Horizontal movement & solid wall collision check
			hw = (self.width / 2.0) * 0.7
			curr_y = int(math.floor(self.position[1]))
			mob_h_ceil = int(math.ceil(self.height))

			# X-axis step
			nx = self.position[0] + self.velocity[0] * dt
			check_x = int(math.floor(nx + (hw if self.velocity[0] > 0 else -hw)))
			blocked_x = False
			if self.velocity[0] != 0:
				for y_chk in range(curr_y, curr_y + mob_h_ceil):
					for z_chk in (int(math.floor(self.position[2] - hw)), int(math.floor(self.position[2] + hw))):
						b = world.get_block_number((check_x, y_chk, z_chk))
						if b != 0 and not is_liquid_or_fire_block(b):
							blocked_x = True
							break
					if blocked_x:
						break

			if blocked_x and self.on_ground:
				self.velocity[0] = 0.0
			else:
				self.position[0] = nx

			# Z-axis step
			nz = self.position[2] + self.velocity[2] * dt
			check_z = int(math.floor(nz + (hw if self.velocity[2] > 0 else -hw)))
			blocked_z = False
			if self.velocity[2] != 0:
				for y_chk in range(curr_y, curr_y + mob_h_ceil):
					for x_chk in (int(math.floor(self.position[0] - hw)), int(math.floor(self.position[0] + hw))):
						b = world.get_block_number((x_chk, y_chk, check_z))
						if b != 0 and not is_liquid_or_fire_block(b):
							blocked_z = True
							break
					if blocked_z:
						break

			if blocked_z and self.on_ground:
				self.velocity[2] = 0.0
			else:
				self.position[2] = nz

			# Vertical movement (Y-axis)
			ny = self.position[1] + self.velocity[1] * dt
			bx = int(math.floor(self.position[0]))
			bz = int(math.floor(self.position[2]))

			if self.velocity[1] > 0.0:
				# Upward swept ceiling check (check overhead across mob AABB)
				min_cy = int(math.floor(self.position[1] + self.height))
				max_cy = int(math.floor(ny + self.height))
				hit_ceil = None
				for cy in range(min_cy, max_cy + 1):
					for chk_bx in (int(math.floor(self.position[0] - hw)), int(math.floor(self.position[0] + hw))):
						for chk_bz in (int(math.floor(self.position[2] - hw)), int(math.floor(self.position[2] + hw))):
							b_ceil = world.get_block_number((chk_bx, cy, chk_bz))
							if b_ceil != 0 and not is_liquid_or_fire_block(b_ceil):
								hit_ceil = cy
								break
						if hit_ceil is not None:
							break
					if hit_ceil is not None:
						break

				if hit_ceil is not None:
					self.velocity[1] = 0.0
					ny = float(hit_ceil) - self.height - 0.01
				self.position[1] = ny
				self.on_ground = False
			else:
				# Downward floor collision check
				check_top_y = int(math.floor(self.position[1] + 0.1))
				check_bot_y = int(math.floor(ny - 0.2))
				hit_floor = None
				for fy in range(check_top_y - 1, check_bot_y - 1, -1):
					b = world.get_block_number((bx, fy, bz))
					if b != 0 and not is_liquid_or_fire_block(b):
						hit_floor = fy
						break
				if hit_floor is not None:
					self.velocity[1] = 0.0
					self.position[1] = hit_floor + 1.0

					# Landing event: calculate fall damage
					if self.fall_start_y is not None:
						fall_dist = self.fall_start_y - self.position[1]
						if fall_dist > 3.0 and self.mob_type != "chicken":
							dmg = int(round(fall_dist - 3.0))
							if dmg > 0:
								self.take_damage(dmg, is_fall=True)
						self.fall_start_y = None

					self.on_ground = True
				else:
					self.position[1] = ny
					self.on_ground = False


class PigEntity(MobEntity):
	"""Minecraft Pig Entity: 10 HP (5 hearts), speed 0.25, drops 1-3 Porkchops."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="pig", max_health=10, speed=0.25, width=0.9, height=0.9)

	def get_loot_drops(self, is_on_fire=False):
		count = random.randint(1, 3)
		item_id = 128 if is_on_fire else 125  # Cooked (128) vs Raw Porkchop (125)
		xp = random.randint(1, 3)
		return [(item_id, count)], xp


class CowEntity(MobEntity):
	"""Minecraft Cow Entity: 10 HP (5 hearts), speed 0.20, drops 0-2 Leather and 1-3 Beef."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="cow", max_health=10, speed=0.20, width=0.9, height=1.4)

	def get_loot_drops(self, is_on_fire=False):
		beef_count = random.randint(1, 3)
		beef_id = 129 if is_on_fire else 127  # Steak (129) vs Raw Beef (127)
		leather_count = random.randint(0, 2)
		xp = random.randint(1, 3)

		drops = [(beef_id, beef_count)]
		if leather_count > 0:
			drops.append((126, leather_count))  # Leather (126)
		return drops, xp


class SheepEntity(MobEntity):
	"""Minecraft Sheep Entity: 8 HP (4 hearts), speed 0.23, drops 1 White Wool and 1-2 Mutton."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="sheep", max_health=8, speed=0.23, width=0.9, height=1.3)

	def update(self, dt, world, player_pos, *args, **kwargs):
		super().update(dt, world, player_pos, *args, **kwargs)
		# Periodic grazing idle animation
		if not self.is_moving and self.on_ground:
			self.grazing_timer += dt
			if self.grazing_timer > 6.0:
				self.is_grazing = True
				if self.grazing_timer > 8.0:
					self.grazing_timer = 0.0
					self.is_grazing = False
		else:
			self.grazing_timer = 0.0
			self.is_grazing = False

	def get_loot_drops(self, is_on_fire=False):
		mutton_count = random.randint(1, 2)
		mutton_id = 165 if is_on_fire else 164  # Cooked (165) vs Raw Mutton (164)
		wool_id = 83  # White Wool (83)
		xp = random.randint(1, 3)
		return [(wool_id, 1), (mutton_id, mutton_count)], xp


class ChickenEntity(MobEntity):
	"""Minecraft Chicken Entity: 4 HP (2 hearts), speed 0.25, drops 0-2 Feathers and 1 Chicken."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="chicken", max_health=4, speed=0.25, width=0.4, height=0.7)

	def update(self, dt, world, player_pos, *args, **kwargs):
		super().update(dt, world, player_pos, *args, **kwargs)
		if not self.on_ground:
			self.wing_flap += dt * 18.0
		elif self.is_moving:
			self.wing_flap += dt * 8.0
		else:
			self.wing_flap = 0.0

	def get_loot_drops(self, is_on_fire=False):
		chicken_id = 163 if is_on_fire else 162  # Cooked (163) vs Raw Chicken (162)
		feather_count = random.randint(0, 2)
		xp = random.randint(1, 3)

		drops = [(chicken_id, 1)]
		if feather_count > 0:
			drops.append((160, feather_count))  # Feather (160)
		return drops, xp


# ==============================================================================
# REUSABLE HOSTILE MOB AI GOALS
# ==============================================================================

class FindTargetGoal:
	"""AI Goal: Throttled search for nearby Survival-mode player target within detection range."""
	def __init__(self, mob, detection_range=16.0):
		self.mob = mob
		self.detection_range = detection_range
		self.scan_timer = 0.0

	def update(self, dt, player_pos, camera=None, flying=False):
		self.scan_timer -= dt
		if self.scan_timer > 0:
			return
		self.scan_timer = 0.2  # Check target every 0.2s

		# Only target valid Survival-mode living players
		is_creative = flying or (camera and getattr(camera, 'flying', False))
		is_dead = (camera and getattr(camera, 'health', 1) <= 0)
		if is_creative or is_dead or not player_pos:
			self.mob.target = None
			return

		px, py, pz = player_pos
		mx, my, mz = self.mob.position
		dx = px - mx
		dy = py - my
		dz = pz - mz
		dist_sq = dx * dx + dy * dy + dz * dz

		if dist_sq <= self.detection_range * self.detection_range:
			self.mob.target = tuple(player_pos)
		else:
			self.mob.target = None


class MeleeAttackGoal:
	"""AI Goal: Pursue target and inflict melee damage on contact within attack cooldown."""
	def __init__(self, mob, attack_range=1.8, damage=3, cooldown=1.0):
		self.mob = mob
		self.attack_range = attack_range
		self.damage = damage
		self.cooldown_max = cooldown
		self.cooldown_timer = 0.0
		self.repath_timer = 0.0

	def update(self, dt, world, player_pos, camera=None, gui=None, flying=False):
		if self.cooldown_timer > 0:
			self.cooldown_timer = max(0.0, self.cooldown_timer - dt)

		is_creative = flying or (camera and getattr(camera, 'flying', False))
		is_dead = (camera and getattr(camera, 'health', 1) <= 0)
		if is_creative or is_dead or not player_pos:
			self.mob.target = None
			return

		# Measure actual live distance to player (prevents hitting dead/respawned players from distance)
		px, py, pz = player_pos
		mx, my, mz = self.mob.position
		dx = px - mx
		dy = py - my
		dz = pz - mz
		dist = math.sqrt(dx * dx + dz * dz)

		# Lose target immediately if player is beyond detection range (e.g. after respawn)
		if dist > 16.0 or abs(dy) > 16.0:
			self.mob.target = None
			return

		self.mob.target = (px, py, pz)

		# Face target
		self.mob.target_yaw = math.atan2(dx, dz)

		if dist <= self.attack_range and abs(dy) <= 2.2:
			# Within melee attack range! Stop and strike
			self.mob.is_moving = False
			self.mob.velocity[0] = 0.0
			self.mob.velocity[2] = 0.0
			self.mob.target_dest = None

			if self.cooldown_timer <= 0.0:
				self.cooldown_timer = self.cooldown_max
				self.mob.attack_anim_time = 0.35
				if camera and hasattr(camera, "take_damage"):
					camera.take_damage(self.damage, flying=is_creative, gui=gui, world=world)
		else:
			# Pursue target
			self.repath_timer -= dt
			if self.repath_timer <= 0 or self.mob.target_dest is None:
				self.repath_timer = 0.25
				self.mob.set_target_destination(px, pz, speed_mult=1.25)


class RangedBowAttackGoal:
	"""AI Goal: Skeletons maintain tactical distance, aim bow, and shoot arrows."""
	def __init__(self, mob, min_range=5.0, max_range=15.0, attack_cooldown=1.8):
		self.mob = mob
		self.min_range = min_range
		self.max_range = max_range
		self.attack_cooldown_max = attack_cooldown
		self.attack_cooldown = random.uniform(0.5, 1.2)
		self.bow_draw_time = 0.0
		self.repath_timer = 0.0

	def has_line_of_sight(self, world, px, py, pz):
		mx, my, mz = self.mob.position
		sx, sy, sz = mx, my + 1.5, mz
		tx, ty, tz = px, py + 1.2, pz
		dx, dy, dz = tx - sx, ty - sy, tz - sz
		dist = math.sqrt(dx * dx + dy * dy + dz * dz)
		if dist < 0.1:
			return True

		steps = int(dist * 2.0)
		for i in range(1, steps):
			frac = i / float(steps)
			bx = int(math.floor(sx + dx * frac))
			by = int(math.floor(sy + dy * frac))
			bz = int(math.floor(sz + dz * frac))
			b_num = world.get_block_number((bx, by, bz))
			if b_num != 0 and b_num not in (9, 19, 15, 20, 78):
				return False
		return True

	def update(self, dt, world, player_pos, camera=None, arrow_manager=None, flying=False):
		if self.attack_cooldown > 0:
			self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

		is_creative = flying or (camera and getattr(camera, 'flying', False))
		is_dead = (camera and getattr(camera, 'health', 1) <= 0)
		if is_creative or is_dead or not player_pos:
			self.mob.target = None
			self.mob.is_aiming = False
			self.bow_draw_time = 0.0
			return

		# Measure actual live distance to player
		px, py, pz = player_pos
		mx, my, mz = self.mob.position
		dx = px - mx
		dy = py - my
		dz = pz - mz
		dist = math.sqrt(dx * dx + dz * dz)

		if dist > self.max_range * 1.2 or abs(dy) > 16.0:
			self.mob.target = None
			self.mob.is_aiming = False
			self.bow_draw_time = 0.0
			return

		self.mob.target = (px, py, pz)
		self.mob.target_yaw = math.atan2(dx, dz)
		has_los = self.has_line_of_sight(world, px, py, pz)

		if dist < self.min_range:
			# Player is too close: back away to maintain distance
			self.mob.is_aiming = False
			self.repath_timer -= dt
			if self.repath_timer <= 0:
				self.repath_timer = 0.3
				angle = math.atan2(-dx, -dz) + random.uniform(-0.3, 0.3)
				tx = mx + math.sin(angle) * 6.0
				tz = mz + math.cos(angle) * 6.0
				self.mob.set_target_destination(tx, tz, speed_mult=1.1)

		elif dist > self.max_range or not has_los:
			# Out of range or no line of sight: navigate closer
			self.mob.is_aiming = False
			self.repath_timer -= dt
			if self.repath_timer <= 0:
				self.repath_timer = 0.4
				self.mob.set_target_destination(px, pz, speed_mult=1.1)

		else:
			# In shooting range with clear line of sight! Aim and fire
			self.mob.is_moving = False
			self.mob.velocity[0] = 0.0
			self.mob.velocity[2] = 0.0
			self.mob.target_dest = None
			self.mob.is_aiming = True

			self.bow_draw_time += dt
			if self.bow_draw_time >= 0.9 and self.attack_cooldown <= 0.0:
				self.bow_draw_time = 0.0
				self.attack_cooldown = self.attack_cooldown_max

				if arrow_manager and hasattr(arrow_manager, "spawn_arrow"):
					launch_x, launch_y, launch_z = mx, my + 1.4, mz
					target_y = py - 0.4  # Target player chest level (camera is at eye level)
					dx = px - launch_x
					dy = target_y - launch_y
					dz = pz - launch_z
					dist = max(0.1, math.sqrt(dx * dx + dz * dz))

					# Parabolic arc solving for 0.05 gravity and 0.99 drag
					speed = 1.6  # blocks / tick
					t = (dist / speed) * 1.04
					vy = (dy + 0.5 * 0.05 * (t ** 2)) / t
					vh = dist / t
					vx = (dx / dist) * vh
					vz = (dz / dist) * vh

					# Slight authentic accuracy spread (±0.015)
					inaccuracy = 0.015
					vx += random.gauss(0, 1) * inaccuracy
					vy += random.gauss(0, 1) * inaccuracy
					vz += random.gauss(0, 1) * inaccuracy

					arrow_manager.spawn_arrow((launch_x, launch_y, launch_z), [vx, vy, vz], shooter=self.mob)


class SunlightBurnGoal:
	"""AI Goal: Zombies and Skeletons detect direct sunlight during daytime and ignite."""
	def __init__(self, mob):
		self.mob = mob
		self.check_timer = 0.0

	def is_exposed_to_sunlight(self, world, time_of_day):
		tod = time_of_day % 1.0
		is_day = (0.23 < tod < 0.77)
		if not is_day:
			return False

		# Check vertical column above mob up to sky
		mx, my, mz = self.mob.position
		bx = int(math.floor(mx))
		by = int(math.floor(my + self.mob.height))
		bz = int(math.floor(mz))

		for y in range(by + 1, by + 35):
			b = world.get_block_number((bx, y, bz))
			if b != 0 and b not in (9, 19, 78):
				return False  # Shaded by solid ceiling!
		return True

	def update(self, dt, world, time_of_day=0.5):
		self.check_timer -= dt
		if self.check_timer <= 0:
			self.check_timer = 0.8
			if self.is_exposed_to_sunlight(world, time_of_day):
				self.mob.fire_timer = max(self.mob.fire_timer, 8.0)
				self.mob.is_in_sunlight = True
			else:
				self.mob.is_in_sunlight = False


class FindShelterGoal:
	"""AI Goal: When burning in daylight, navigate toward shaded ceiling voxels or water."""
	def __init__(self, mob):
		self.mob = mob
		self.search_cooldown = 0.0

	def update(self, dt, world, time_of_day=0.5):
		if self.mob.fire_timer <= 0 and not getattr(self.mob, 'is_in_sunlight', False):
			return

		tod = time_of_day % 1.0
		if not (0.23 < tod < 0.77):
			return

		self.search_cooldown -= dt
		if self.search_cooldown <= 0:
			self.search_cooldown = 1.2

			mx, my, mz = self.mob.position
			curr_bx, curr_by, curr_bz = int(math.floor(mx)), int(math.floor(my)), int(math.floor(mz))

			best_shelter = None
			min_dist_sq = float('inf')

			# Scan in 12x4x12 area for shade (solid ceiling block overhead) or water
			for dx in range(-10, 11, 2):
				for dz in range(-10, 11, 2):
					for dy in range(-2, 3):
						bx, by, bz = curr_bx + dx, curr_by + dy, curr_bz + dz
						b_ground = world.get_block_number((bx, by, bz))
						b_above1 = world.get_block_number((bx, by + 1, bz))
						b_above2 = world.get_block_number((bx, by + 2, bz))

						# Check if water or shaded ground
						if is_water_block(b_ground) or is_water_block(b_above1):
							d_sq = dx * dx + dy * dy + dz * dz
							if d_sq < min_dist_sq:
								min_dist_sq = d_sq
								best_shelter = (bx + 0.5, bz + 0.5)
						elif b_ground != 0 and not is_liquid_or_fire_block(b_ground) and b_above1 == 0 and b_above2 == 0:
							# Check for solid ceiling above
							has_ceil = False
							for cy in range(by + 3, by + 20):
								b_ceil = world.get_block_number((bx, cy, bz))
								if b_ceil != 0 and b_ceil not in (9, 19, 78):
									has_ceil = True
									break
							if has_ceil:
								d_sq = dx * dx + dy * dy + dz * dz
								if d_sq < min_dist_sq:
									min_dist_sq = d_sq
									best_shelter = (bx + 0.5, bz + 0.5)

			if best_shelter:
				self.mob.set_target_destination(best_shelter[0], best_shelter[1], speed_mult=1.3)


# ==============================================================================
# HOSTILE MOB ENTITY IMPLEMENTATIONS
# ==============================================================================

class HostileEntity(MobEntity):
	"""Base reusable hostile mob entity with targeting, combat, and sunlight goals."""
	def __init__(self, entity_id, position, mob_type, max_health=20, speed=0.23, width=0.6, height=1.9):
		super().__init__(entity_id, position, mob_type=mob_type, max_health=max_health, speed=speed, width=width, height=height)
		self.target = None
		self.attack_anim_time = 0.0
		self.is_aiming = False
		self.is_in_sunlight = False

		# AI Goals
		self.find_target_goal = FindTargetGoal(self, detection_range=16.0)
		self.shelter_goal = FindShelterGoal(self)
		self.sunlight_goal = SunlightBurnGoal(self)

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		if self.is_dead:
			return

		if self.attack_anim_time > 0:
			self.attack_anim_time = max(0.0, self.attack_anim_time - dt)

		# 1. Target finding
		self.find_target_goal.update(dt, player_pos, camera=camera, flying=flying)

		# 2. Sunlight check & shelter seeking for sun-vulnerable mobs
		if self.mob_type in ("zombie", "skeleton"):
			self.sunlight_goal.update(dt, world, time_of_day=time_of_day)
			if self.fire_timer > 0.0 or self.is_in_sunlight:
				self.shelter_goal.update(dt, world, time_of_day=time_of_day)

		# 3. Base movement, physics, and damage handling
		super().update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)


class ZombieEntity(HostileEntity):
	"""Minecraft Zombie Entity: 20 HP (10 hearts), speed 0.23, melee 3 damage, drops 0-2 Rotten Flesh."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="zombie", max_health=20, speed=0.23, width=0.6, height=1.95)
		self.melee_goal = MeleeAttackGoal(self, attack_range=1.8, damage=3, cooldown=1.0)

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		super().update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)
		if not self.is_dead:
			self.melee_goal.update(dt, world, player_pos, camera=camera, gui=gui, flying=flying)

	def get_loot_drops(self, is_on_fire=False):
		flesh_count = random.randint(0, 2)
		xp = random.randint(3, 5)
		drops = []
		if flesh_count > 0:
			drops.append((166, flesh_count))  # Rotten Flesh (166)
		return drops, xp


class SkeletonEntity(HostileEntity):
	"""Minecraft Skeleton Entity: 20 HP (10 hearts), speed 0.24, ranged bow attack, drops 0-2 Bones & 0-2 Arrows."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="skeleton", max_health=20, speed=0.24, width=0.6, height=1.98)
		self.ranged_goal = RangedBowAttackGoal(self, min_range=5.0, max_range=15.0, attack_cooldown=1.8)

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		super().update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)
		if not self.is_dead:
			self.ranged_goal.update(dt, world, player_pos, camera=camera, arrow_manager=arrow_manager, flying=flying)

	def get_loot_drops(self, is_on_fire=False):
		bone_count = random.randint(0, 2)
		arrow_count = random.randint(0, 2)
		xp = random.randint(3, 5)
		drops = []
		if bone_count > 0:
			drops.append((167, bone_count))   # Bone (167)
		if arrow_count > 0:
			drops.append((158, arrow_count))  # Arrow (158)
		return drops, xp


class SpiderEntity(HostileEntity):
	"""Minecraft Spider Entity: 16 HP (8 hearts), speed 0.30, width 1.4, height 0.9, wall climbing, melee 3 damage."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="spider", max_health=16, speed=0.30, width=1.4, height=0.9)
		self.is_climbing = False
		self.melee_goal = MeleeAttackGoal(self, attack_range=1.6, damage=3, cooldown=0.8)

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		# Spider Wall Climbing Surface Detection
		reach = (self.width / 2.0) + 0.3
		yaw = self.yaw
		ahead_x = self.position[0] + math.sin(yaw) * reach
		ahead_z = self.position[2] + math.cos(yaw) * reach
		curr_by = int(math.floor(self.position[1]))
		ahead_bx = int(math.floor(ahead_x))
		ahead_bz = int(math.floor(ahead_z))

		wall_block = world.get_block_number((ahead_bx, curr_by, ahead_bz))
		wall_upper = world.get_block_number((ahead_bx, curr_by + 1, ahead_bz))

		is_wall_ahead = (wall_block != 0 and not is_liquid_or_fire_block(wall_block)) or (wall_upper != 0 and not is_liquid_or_fire_block(wall_upper))

		if is_wall_ahead:
			self.is_climbing = True
			self.velocity[1] = 3.5
			self.target_pitch = -1.2  # Wall climbing angle
			self.pitch = -1.2
		else:
			self.is_climbing = False
			if self.target_pitch < -0.5:
				self.target_pitch = 0.0

		super().update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)
		if not self.is_dead:
			self.melee_goal.update(dt, world, player_pos, camera=camera, gui=gui, flying=flying)

	def get_loot_drops(self, is_on_fire=False):
		string_count = random.randint(0, 2)
		eye_count = 1 if random.random() < 0.33 else 0
		xp = random.randint(3, 5)
		drops = []
		if string_count > 0:
			drops.append((159, string_count))  # String (159)
		if eye_count > 0:
			drops.append((168, eye_count))     # Spider Eye (168)
		return drops, xp


class CreeperAttackGoal:
	"""AI Goal: Approaching player, swelling/hissing countdown at <=3m, and explosion detonation at 30 ticks."""
	def __init__(self, mob, fuse_max=30, explosion_power=3.0, trigger_distance=3.0, abort_distance=7.0):
		self.mob = mob
		self.fuse_max = float(fuse_max)  # 30 ticks = 1.5s
		self.fuse_time = 0.0
		self.explosion_power = explosion_power
		self.trigger_distance = trigger_distance
		self.abort_distance = abort_distance
		self.repath_timer = 0.0

	def update(self, dt, world, player_pos, camera=None, gui=None, tnt_manager=None, mob_manager=None, item_drop_manager=None, flying=False):
		is_creative = flying or (camera and getattr(camera, 'flying', False))
		is_dead = (camera and getattr(camera, 'health', 1) <= 0)
		if is_creative or is_dead or not player_pos:
			self.fuse_time = max(0.0, self.fuse_time - dt * 20.0)
			self.mob.fuse_progress = self.fuse_time / self.fuse_max
			self.mob.is_hissing = False
			return

		px, py, pz = player_pos
		mx, my, mz = self.mob.position
		dx = px - mx
		dy = py - my
		dz = pz - mz
		dist = math.sqrt(dx * dx + dz * dz)

		self.mob.target_yaw = math.atan2(dx, dz)

		if dist <= self.trigger_distance and abs(dy) <= 3.0:
			# Player in close range! Stop movement and hiss/swell
			self.mob.is_moving = False
			self.mob.velocity[0] = 0.0
			self.mob.velocity[2] = 0.0
			self.mob.target_dest = None
			self.mob.is_hissing = True

			self.fuse_time += dt * 20.0
			self.mob.fuse_progress = min(1.0, self.fuse_time / self.fuse_max)

			if self.fuse_time >= self.fuse_max:
				# Detonate Creeper Explosion!
				self.mob.is_dead = True
				import explosion
				ex_pos = (mx, my + 0.85, mz)
				explosion.create_explosion(
					world, ex_pos, power=self.explosion_power, source_entity=self.mob,
					tnt_manager=tnt_manager, mob_manager=mob_manager,
					camera=camera, gui=gui, item_drop_manager=item_drop_manager
				)
				return

		elif dist > self.abort_distance or abs(dy) > 4.0:
			# Player fled beyond abort distance! Cool down fuse
			self.fuse_time = max(0.0, self.fuse_time - dt * 20.0)
			self.mob.fuse_progress = self.fuse_time / self.fuse_max
			self.mob.is_hissing = False

			self.repath_timer -= dt
			if self.repath_timer <= 0 or self.mob.target_dest is None:
				self.repath_timer = 0.3
				self.mob.set_target_destination(px, pz, speed_mult=1.15)

		else:
			# Medium distance: continue fuse if already swelling, otherwise pursue
			if self.fuse_time > 0.0:
				self.fuse_time += dt * 20.0
				self.mob.fuse_progress = min(1.0, self.fuse_time / self.fuse_max)
				if self.fuse_time >= self.fuse_max:
					self.mob.is_dead = True
					import explosion
					ex_pos = (mx, my + 0.85, mz)
					explosion.create_explosion(
						world, ex_pos, power=self.explosion_power, source_entity=self.mob,
						tnt_manager=tnt_manager, mob_manager=mob_manager,
						camera=camera, gui=gui, item_drop_manager=item_drop_manager
					)
					return
			else:
				self.mob.is_hissing = False
				self.repath_timer -= dt
				if self.repath_timer <= 0 or self.mob.target_dest is None:
					self.repath_timer = 0.3
					self.mob.set_target_destination(px, pz, speed_mult=1.15)


class CreeperEntity(HostileEntity):
	"""Minecraft Creeper Entity: 20 HP (10 hearts), speed 0.25, drops 0-2 Gunpowder, detonates 3.0 power explosion."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="creeper", max_health=20, speed=0.25, width=0.6, height=1.7)
		self.fuse_progress = 0.0
		self.is_hissing = False
		self.attack_goal = CreeperAttackGoal(self, fuse_max=30, explosion_power=3.0)

	def update(self, dt, world, player_pos, camera=None, gui=None, tnt_manager=None, mob_manager=None, item_drop_manager=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		super().update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)
		if not self.is_dead:
			self.attack_goal.update(
				dt, world, player_pos, camera=camera, gui=gui,
				tnt_manager=tnt_manager, mob_manager=mob_manager,
				item_drop_manager=item_drop_manager, flying=flying
			)

	def get_loot_drops(self, is_on_fire=False):
		gunpowder_count = random.randint(0, 2)
		xp = 5
		drops = []
		if gunpowder_count > 0:
			drops.append((169, gunpowder_count))  # Gunpowder (169)
		return drops, xp


