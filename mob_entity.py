"""
Minecraft Passive Mob Entities & AI System (Cow, Pig, Sheep, Chicken)
----------------------------------------------------------------------
Implements CowEntity, PigEntity, SheepEntity, and ChickenEntity with authentic attributes,
terrain physics collisions, hazard avoidance (water, lava, cliffs), Minecraft-style
environmental damage (fire, lava, drowning, fall damage), panic fleeing, and fire-extinguishing AI.
"""

import math
import random
import block_state


def is_liquid_or_fire_block(block_id):
	"""Returns True if the block is passable without collision (liquids, fire, flowers, ferns, saplings, portals)."""
	return block_id in block_state.PASSABLE_BLOCKS


def is_water_block(block_id):
	"""Returns True if the block is water source or flowing water."""
	return block_id in (9, 19)


def is_lava_block(block_id):
	"""Returns True if the block is lava source or flowing lava."""
	return block_id in (15, 20)


def is_walkable_ground(block_id):
	"""Returns True if the block is a valid solid ground block for mobs to walk on (rejects liquids, fire, foliage/flowers, leaves, and cacti)."""
	return block_id != 0 and block_id not in block_state.PASSABLE_BLOCKS and block_id not in (11, 13, 14, 18, 224, 234, 244, 254, 264)


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

	def is_touching_cactus(self, world):
		"""Checks if the mob's bounding box touches a Cactus block (11)."""
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
					if world.get_block_number((bx, by, bz)) == 11:
						return True
		return False

	def is_head_underwater(self, world):
		"""Checks if the mob's head is submerged in water."""
		mx, my, mz = self.position
		head_y = my + self.height * 0.85
		b_head = world.get_block_number((int(math.floor(mx)), int(math.floor(head_y)), int(math.floor(mz))))
		return is_water_block(b_head)

	def take_damage(self, damage, attacker_pos=None, is_fire=False, is_drowning=False, is_fall=False, world=None, mob_manager=None, looting_level=0, *args, **kwargs):
		"""Applies damage, flashes red, and enters directional panic fleeing state."""
		if self.is_dead or damage <= 0:
			return
		if is_fire and getattr(self, "is_fire_immune", False):
			return

		if looting_level > 0:
			self.last_looting_level = looting_level

		self.health = max(0, self.health - damage)
		self.hurt_time = 0.4
		if hasattr(self, "panic_goal") and self.panic_goal:
			self.panic_goal.trigger(attacker_pos)

		if self.health == 0:
			self.is_dead = True

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, **kwargs):
		if self.is_dead:
			return

		# Void Despawn / Death (Y < -10)
		if self.position[1] < -10.0:
			self.is_dead = True
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
		elif getattr(self, "is_fire_immune", False):
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

		# 2. Cactus Contact Damage
		if self.is_touching_cactus(world):
			self.cactus_damage_timer = getattr(self, "cactus_damage_timer", 0.0) + dt
			if self.cactus_damage_timer >= 0.5:
				self.cactus_damage_timer = 0.0
				self.take_damage(1)
		else:
			self.cactus_damage_timer = 0.0

		# 3. Oxygen & Drowning Mechanics
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

			if blocked_x:
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

			if blocked_z:
				self.velocity[2] = 0.0
			else:
				self.position[2] = nz

			# Vertical movement (Y-axis)
			ny = self.position[1] + self.velocity[1] * dt

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
				# Downward swept 4-corner floor collision check across full AABB footprint
				bx_min = int(math.floor(self.position[0] - hw + 0.02))
				bx_max = int(math.floor(self.position[0] + hw - 0.02))
				bz_min = int(math.floor(self.position[2] - hw + 0.02))
				bz_max = int(math.floor(self.position[2] + hw - 0.02))

				check_top_y = int(math.floor(self.position[1] + 0.1))
				check_bot_y = int(math.floor(ny - 0.2))
				hit_floor = None

				for fy in range(check_top_y, check_bot_y - 1, -1):
					is_solid = False
					for fbx in range(bx_min, bx_max + 1):
						for fbz in range(bz_min, bz_max + 1):
							b = world.get_block_number((fbx, fy, fbz))
							if b != 0 and not is_liquid_or_fire_block(b):
								is_solid = True
								break
						if is_solid:
							break
					if is_solid and (fy + 1.0) <= (self.position[1] + 0.5):
						hit_floor = fy
						break

				if hit_floor is not None:
					self.velocity[1] = 0.0
					self.position[1] = float(hit_floor + 1.0)

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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		count = random.randint(1, 3 + looting_level)
		item_id = 128 if is_on_fire else 125  # Cooked (128) vs Raw Porkchop (125)
		xp = random.randint(1, 3)
		return [(item_id, count)], xp


class CowEntity(MobEntity):
	"""Minecraft Cow Entity: 10 HP (5 hearts), speed 0.20, drops 0-2 Leather and 1-3 Beef."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="cow", max_health=10, speed=0.20, width=0.9, height=1.4)

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		beef_count = random.randint(1, 3 + looting_level)
		beef_id = 129 if is_on_fire else 127  # Steak (129) vs Raw Beef (127)
		leather_count = random.randint(0, 2 + looting_level)
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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		mutton_count = random.randint(1, 2 + looting_level)
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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		chicken_id = 163 if is_on_fire else 162  # Cooked (163) vs Raw Chicken (162)
		chicken_count = 1 + random.randint(0, looting_level)
		feather_count = random.randint(0, 2 + looting_level)
		xp = random.randint(1, 3)

		drops = [(chicken_id, chicken_count)]
		if feather_count > 0:
			drops.append((160, feather_count))  # Feather (160)
		return drops, xp


# ==============================================================================
# REUSABLE HOSTILE MOB AI GOALS
# ==============================================================================

def check_line_of_sight(world, sx, sy, sz, tx, ty, tz):
	"""Checks whether there is an unobstructed line of sight through non-solid blocks."""
	if not world:
		return True
	dx = tx - sx
	dy = ty - sy
	dz = tz - sz
	dist = math.sqrt(dx * dx + dy * dy + dz * dz)
	if dist < 0.2:
		return True
	steps = max(2, int(dist * 3.0))
	for i in range(1, steps):
		frac = i / float(steps)
		bx = int(math.floor(sx + dx * frac))
		by = int(math.floor(sy + dy * frac))
		bz = int(math.floor(sz + dz * frac))
		b_num = world.get_block_number((bx, by, bz))
		if b_num != 0 and b_num not in (9, 19, 15, 20, 78, 79, 81):
			return False
	return True


class FindTargetGoal:
	"""AI Goal: Throttled search for nearby Survival-mode player target within detection range."""
	def __init__(self, mob, detection_range=16.0):
		self.mob = mob
		self.detection_range = detection_range
		self.scan_timer = 0.0

	def update(self, dt, player_pos, camera=None, flying=False, world=None):
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
			if world is None or check_line_of_sight(world, mx, my + 1.2, mz, px, py + 1.2, pz):
				self.mob.target = tuple(player_pos)
			else:
				self.mob.target = None
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
			# Verify line of sight so mobs cannot strike through solid walls/floors/ceilings
			if check_line_of_sight(world, mx, my + min(self.mob.height * 0.75, 1.4), mz, px, py + 1.2, pz):
				# Within melee attack range and clear line of sight! Stop and strike
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
	def __init__(self, mob, min_range=3.0, max_range=16.0, attack_cooldown=1.8):
		self.mob = mob
		self.min_range = min_range
		self.max_range = max_range
		self.attack_cooldown_max = attack_cooldown
		self.attack_cooldown = random.uniform(0.3, 0.8)
		self.bow_draw_time = 0.0
		self.repath_timer = 0.0

	def has_line_of_sight(self, world, px, py, pz):
		mx, my, mz = self.mob.position
		return check_line_of_sight(world, mx, my + 1.4, mz, px, py + 1.2, pz)

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

		if not has_los or dist > self.max_range:
			# Out of range or no line of sight: navigate closer
			self.mob.is_aiming = False
			self.bow_draw_time = 0.0
			self.repath_timer -= dt
			if self.repath_timer <= 0 or self.mob.target_dest is None:
				self.repath_timer = 0.4
				self.mob.set_target_destination(px, pz, speed_mult=1.1)
		else:
			# In shooting range with clear line of sight! Aim bow and shoot
			self.mob.is_aiming = True

			if dist < self.min_range:
				# Player is very close: back away slightly to keep spacing while still drawing bow
				self.repath_timer -= dt
				if self.repath_timer <= 0 or self.mob.target_dest is None:
					self.repath_timer = 0.35
					angle = math.atan2(-dx, -dz) + random.uniform(-0.4, 0.4)
					tx = mx + math.sin(angle) * 4.0
					tz = mz + math.cos(angle) * 4.0
					self.mob.set_target_destination(tx, tz, speed_mult=0.85)
			else:
				self.mob.is_moving = False
				self.mob.velocity[0] = 0.0
				self.mob.velocity[2] = 0.0
				self.mob.target_dest = None

			# Charge bow and release arrow
			self.bow_draw_time += dt
			if self.bow_draw_time >= 0.9 and self.attack_cooldown <= 0.0:
				self.bow_draw_time = 0.0
				self.attack_cooldown = self.attack_cooldown_max

				if arrow_manager and hasattr(arrow_manager, "spawn_arrow"):
					launch_x, launch_y, launch_z = mx, my + 1.4, mz
					target_y = py - 0.4  # Target player chest level (camera is at eye level)
					adx = px - launch_x
					ady = target_y - launch_y
					adz = pz - launch_z
					adist = max(0.1, math.sqrt(adx * adx + adz * adz))

					# Parabolic arc solving for 0.05 gravity and 0.99 drag
					speed = 1.6  # blocks / tick
					t = (adist / speed) * 1.04
					vy = (ady + 0.5 * 0.05 * (t ** 2)) / t
					vh = adist / t
					vx = (adx / adist) * vh
					vz = (adz / adist) * vh

					# Slight authentic accuracy spread (±0.015)
					inaccuracy = 0.015
					vx += random.gauss(0, 1) * inaccuracy
					vy += random.gauss(0, 1) * inaccuracy
					vz += random.gauss(0, 1) * inaccuracy

					arrow_manager.spawn_arrow((launch_x, launch_y, launch_z), (vx, vy, vz), is_critical=False, shooter="skeleton")

class BlazeAttackGoal:
	"""AI Goal: 3D flying target acquisition (up to 48 blocks), attack flare preparation (1.0s),
	and triple Small Fireball projectile burst attack."""
	def __init__(self, mob, max_range=48.0, cooldown=4.5):
		self.mob = mob
		self.max_range = max_range
		self.cooldown_max = cooldown
		self.cooldown_timer = random.uniform(1.0, 3.0)
		self.charge_timer = 0.0
		self.burst_count = 0
		self.burst_interval = 0.0
		self.repath_timer = 0.0

	def has_line_of_sight(self, world, px, py, pz):
		mx, my, mz = self.mob.position
		sx, sy, sz = mx, my + 1.4, mz
		tx, ty, tz = px, py, pz
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
			if b_num != 0 and b_num not in (9, 19, 15, 20, 78, 88, 89, 94):
				return False
		return True

	def update(self, dt, world, player_pos, camera=None, fireball_manager=None, flying=False):
		if self.cooldown_timer > 0:
			self.cooldown_timer = max(0.0, self.cooldown_timer - dt)

		is_creative = flying or (camera and getattr(camera, 'flying', False))
		is_dead = (camera and getattr(camera, 'health', 1) <= 0)
		if is_creative or is_dead or not player_pos:
			self.mob.target = None
			self.mob.is_charging = False
			self.charge_timer = 0.0
			self.burst_count = 0
			return

		px, py, pz = player_pos
		mx, my, mz = self.mob.position
		dx = px - mx
		dy = py - my
		dz = pz - mz
		dist = math.sqrt(dx * dx + dz * dz)
		total_dist = math.sqrt(dx * dx + dy * dy + dz * dz)

		if total_dist > self.max_range:
			self.mob.target = None
			self.mob.is_charging = False
			self.charge_timer = 0.0
			return

		has_los = self.has_line_of_sight(world, px, py, pz)
		if not has_los:
			self.mob.target = None
			self.mob.is_charging = False
			return

		self.mob.target = (px, py, pz)
		self.mob.target_yaw = math.atan2(dx, dz)

		# 3D Flight Pursuit / Repositioning: maintain height 1.5 - 3.5 blocks above player
		target_hover_y = py + 2.0
		vy_diff = target_hover_y - my
		self.mob.velocity[1] = max(-2.5, min(3.5, self.mob.velocity[1] + vy_diff * dt * 2.0))

		# Horizontal approach if > 12 blocks away
		if dist > 12.0:
			speed_mult = 0.28
			self.mob.velocity[0] += (dx / dist) * speed_mult * dt * 4.0
			self.mob.velocity[2] += (dz / dist) * speed_mult * dt * 4.0
		elif dist < 5.0:
			# Back up if too close
			self.mob.velocity[0] -= (dx / dist) * 0.25 * dt * 4.0
			self.mob.velocity[2] -= (dz / dist) * 0.25 * dt * 4.0

		# Attack Sequence: Charge for 1.0s -> Fire 3 Fireballs spaced 0.33s -> Cooldown 4.5s
		if self.cooldown_timer <= 0.0 and self.burst_count == 0 and self.charge_timer == 0.0:
			# Begin charge!
			self.charge_timer = 1.0
			self.mob.is_charging = True

		if self.charge_timer > 0.0:
			self.charge_timer -= dt
			if self.charge_timer <= 0.0:
				self.charge_timer = 0.0
				self.burst_count = 3
				self.burst_interval = 0.0

		if self.burst_count > 0:
			self.burst_interval -= dt
			if self.burst_interval <= 0.0:
				self.burst_interval = 0.33 # 6 ticks between fireballs
				self.burst_count -= 1

				# Fire Small Fireball towards player eye level
				if fireball_manager and hasattr(fireball_manager, "spawn_fireball"):
					lx, ly, lz = mx, my + 1.4, mz
					tx, ty, tz = px, py - 0.2, pz
					fx = tx - lx
					fy = ty - ly
					fz = tz - lz
					fdist = max(0.1, math.sqrt(fx * fx + fy * fy + fz * fz))

					speed = 15.0 # blocks / second
					vx = (fx / fdist) * speed + random.gauss(0, 0.25)
					vy = (fy / fdist) * speed + random.gauss(0, 0.25)
					vz = (fz / fdist) * speed + random.gauss(0, 0.25)

					fireball_manager.spawn_fireball((lx, ly, lz), [vx, vy, vz], shooter=self.mob)

				if self.burst_count == 0:
					self.mob.is_charging = False
					self.cooldown_timer = self.cooldown_max + random.uniform(-0.5, 0.5)


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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		flesh_count = random.randint(0, 2 + looting_level)
		xp = random.randint(3, 5)
		drops = []
		if flesh_count > 0:
			drops.append((166, flesh_count))  # Rotten Flesh (166)
		return drops, xp


class ZombiePigmanEntity(HostileEntity):
	"""Minecraft Zombie Pigman (Zombified Piglin): 20 HP (10 hearts), speed 0.23 (0.38 when angry),
	neutral mob that only attacks when provoked. Provoking one alerts all nearby pigmen within 32 blocks.
	100% Fire and Lava immune. Drops 0-1 Rotten Flesh & 0-1 Gold Ingot."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="zombie_pigman", max_health=20, speed=0.23, width=0.6, height=1.95)
		self.is_fire_immune = True
		self.is_angry = False
		self.anger_timer = 0.0
		self.melee_goal = MeleeAttackGoal(self, attack_range=1.8, damage=5, cooldown=1.0)

	def become_angry(self, target_pos, anger_duration=25.0):
		"""Angers the pigman towards the player for anger_duration seconds."""
		self.is_angry = True
		self.anger_timer = anger_duration
		self.speed = 0.38  # Aggressive sprint speed when angry
		if target_pos:
			self.target = tuple(target_pos)

	def take_damage(self, damage, attacker_pos=None, is_fire=False, is_drowning=False, is_fall=False, world=None, mob_manager=None, looting_level=0, *args, **kwargs):
		if self.is_dead or damage <= 0:
			return
		if is_fire and self.is_fire_immune:
			return

		if looting_level > 0:
			self.last_looting_level = looting_level

		self.health = max(0, self.health - damage)
		self.hurt_time = 0.4

		# If attacked by player, become angry!
		if attacker_pos:
			self.become_angry(attacker_pos)

		if self.health == 0:
			self.is_dead = True

	def update(self, dt, world, player_pos, camera=None, gui=None, mob_manager=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		if self.is_dead:
			return

		if self.attack_anim_time > 0:
			self.attack_anim_time = max(0.0, self.attack_anim_time - dt)

		# Anger timer decay
		if self.is_angry:
			self.anger_timer -= dt
			if self.anger_timer <= 0.0 or (camera and getattr(camera, 'health', 1) <= 0):
				self.is_angry = False
				self.anger_timer = 0.0
				self.speed = 0.23
				self.target = None
				self.target_dest = None

		# If angry and in range, pursue and melee attack player
		if self.is_angry:
			self.find_target_goal.update(dt, player_pos, camera=camera, flying=flying)
			self.melee_goal.update(dt, world, player_pos, camera=camera, gui=gui, flying=flying)
		else:
			# Neutral wander behavior
			self.stroll_goal.update(dt, world)

		# Base physics, movement, gravity, collisions
		super(HostileEntity, self).update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		flesh_count = random.randint(0, 1 + looting_level)
		gold_chance = 0.35 + 0.15 * looting_level
		gold_count = random.randint(0, 1 + looting_level) if random.random() < gold_chance else 0
		xp = 5
		drops = []
		if flesh_count > 0:
			drops.append((166, flesh_count))  # Rotten Flesh (166)
		if gold_count > 0:
			drops.append((124, gold_count))   # Gold Ingot (124)
		return drops, xp


class BlazeEntity(HostileEntity):
	"""Minecraft Blaze Mob: 20 HP (10 hearts), 3D Flight & Hovering physics,
	100% Fire/Lava immune, 3-fireball burst attack, drops 0-1 Blaze Rods."""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="blaze", max_health=20, speed=0.25, width=0.6, height=1.8)
		self.is_fire_immune = True
		self.is_charging = False
		self.attack_goal = BlazeAttackGoal(self, max_range=48.0, cooldown=4.5)
		self.hover_time = random.uniform(0.0, 10.0)

	def update(self, dt, world, player_pos, camera=None, gui=None, fireball_manager=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		if self.is_dead:
			return

		self.hover_time += dt
		self.walk_time = self.hover_time

		if self.hurt_time > 0:
			self.hurt_time = max(0.0, self.hurt_time - dt)

		# 3D Flying Physics: Custom drag & buoyancy (no ground gravity sticking)
		self.velocity[0] *= (0.91 ** (dt * 20.0))
		self.velocity[2] *= (0.91 ** (dt * 20.0))
		self.velocity[1] *= (0.91 ** (dt * 20.0))

		# Execute Blaze Attack Goal
		self.attack_goal.update(dt, world, player_pos, camera=camera, fireball_manager=fireball_manager, flying=flying)

		# If no active target, float gently around
		if not self.target:
			self.velocity[1] += math.sin(self.hover_time * 2.0) * dt * 0.8
			self.stroll_goal.update(dt, world)

		# Update position using velocity
		self.position[0] += self.velocity[0] * dt
		self.position[1] += self.velocity[1] * dt
		self.position[2] += self.velocity[2] * dt

		# Ensure Blaze stays within reasonable Nether height bounds (Y=10..120)
		self.position[1] = max(10.0, min(120.0, self.position[1]))

		# Smooth yaw rotation
		diff = (self.target_yaw - self.yaw + math.pi) % math.tau - math.pi
		self.yaw += diff * min(1.0, dt * 8.0)

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		rod_count = random.randint(0, 1 + looting_level)
		xp = 10
		drops = []
		if rod_count > 0:
			drops.append((172, rod_count))  # Blaze Rod (172)
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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		bone_count = random.randint(0, 2 + looting_level)
		arrow_count = random.randint(0, 2 + looting_level)
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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		string_count = random.randint(0, 2 + looting_level)
		eye_chance = 0.33 + 0.15 * looting_level
		eye_count = 1 + random.randint(0, looting_level) if random.random() < eye_chance else 0
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
			# Verify line of sight so creepers do not hiss/explode through solid walls
			if check_line_of_sight(world, mx, my + 0.8, mz, px, py + 1.2, pz):
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
			else:
				self.mob.is_hissing = False
				self.fuse_time = max(0.0, self.fuse_time - dt * 20.0)
				self.mob.fuse_progress = self.fuse_time / self.fuse_max

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

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		gunpowder_count = random.randint(0, 2 + looting_level)
		xp = 5
		drops = []
		if gunpowder_count > 0:
			drops.append((169, gunpowder_count))  # Gunpowder (169)
		return drops, xp


class EndermanEntity(HostileEntity):
	"""Minecraft Java Edition Enderman Entity:
	- 40 HP (20 hearts)
	- Neutral until player makes direct eye contact with head/eyes or attacks first
	- Fast aggro pursuit (speed 0.45, wander speed 0.30)
	- Melee attack: 7 damage (3.5 hearts), 1.0s cooldown, 2.0 block reach
	- 3D Teleportation: Random repositioning, evasive teleport on damage, water aversion teleport
	- Drops 0-1 Ender Pearls (50% drop rate) and 5 XP
	"""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="enderman", max_health=40, speed=0.30, width=0.6, height=2.9)
		self.is_angry = False
		self.is_screaming = False
		self.stare_timer = 0.0
		self.anger_timer = 0.0
		self.teleport_cooldown = random.uniform(3.0, 6.0)
		self.combat_teleport_timer = random.uniform(5.0, 8.0)
		self.eye_height = 2.55
		self.damage = 7
		self.melee_goal = MeleeAttackGoal(self, attack_range=2.0, damage=7, cooldown=1.0)
		self.stroll_goal = RandomStrollGoal(self)

	def become_angry(self, attacker_pos=None):
		self.is_angry = True
		self.is_screaming = True
		self.stare_timer = 0.6 # Stare & scream before rushing
		self.anger_timer = 20.0 # Calms down after 20 seconds of no aggression
		self.speed = 0.45      # Aggressive pursuit speed
		if attacker_pos:
			self.target = tuple(attacker_pos)

	def check_player_stare(self, world, player_pos, camera):
		"""
		Authentic Minecraft eye-contact detection:
		Checks if the player's camera look ray directly hits the Enderman's eye/head.
		Looking at other body parts (chest, legs, feet) does NOT trigger anger.
		Respects solid block line-of-sight obstruction.
		"""
		if not player_pos or not camera or self.is_angry:
			return False

		# Creative / spectator mode ignores gaze
		if getattr(camera, 'flying', False) or getattr(camera, 'health', 1) <= 0:
			return False

		px, py, pz = player_pos
		eye_offset = getattr(camera, 'eye_offset', 1.62)
		cam_x, cam_y, cam_z = px, py + eye_offset, pz

		# Enderman eye / head center
		mx, my, mz = self.position
		end_eye_x = mx
		end_eye_y = my + self.eye_height
		end_eye_z = mz

		# Vector from camera to Enderman eye
		dx = end_eye_x - cam_x
		dy = end_eye_y - cam_y
		dz = end_eye_z - cam_z
		dist = math.sqrt(dx * dx + dy * dy + dz * dz)

		# Minecraft eye-stare detection range: up to 32 blocks
		if dist > 32.0 or dist < 0.5:
			return False

		# Camera look direction unit vector matching hit.py and engine coordinate raycasts
		yaw, pitch = camera.rotation
		look_x = math.cos(yaw) * math.cos(pitch)
		look_y = math.sin(pitch)
		look_z = math.sin(yaw) * math.cos(pitch)

		# Dot product (must be looking towards the Enderman)
		dot = (dx * look_x + dy * look_y + dz * look_z)
		if dot <= 0.0:
			return False

		# Cosine of angle between look ray and direction to Enderman
		cos_theta = dot / dist
		# Must be aimed directly at head (< 5 degrees and perpendicular distance <= 0.35m)
		if cos_theta < 0.996:
			return False

		proj_x = cam_x + look_x * dot
		proj_y = cam_y + look_y * dot
		proj_z = cam_z + look_z * dot
		perp_dist = math.sqrt((end_eye_x - proj_x) ** 2 + (end_eye_y - proj_y) ** 2 + (end_eye_z - proj_z) ** 2)

		if perp_dist > 0.35:
			return False

		# Check line-of-sight: raycast between camera and Enderman eye through world
		steps = max(2, int(dist * 2.0))
		for i in range(1, steps):
			frac = i / float(steps)
			bx = int(round(cam_x + dx * frac))
			by = int(round(cam_y + dy * frac))
			bz = int(round(cam_z + dz * frac))

			b_num = world.get_block_number((bx, by, bz))
			if b_num != 0 and not is_liquid_or_fire_block(b_num):
				# Line of sight blocked by opaque wall/terrain
				return False

		return True

	def is_safe_teleport_dest(self, world, tx, ty, tz):
		"""
		Validates candidate teleport destination:
		1. Solid walkable ground underneath.
		2. 3 vertical air blocks clearance (height 2.9).
		3. Not in water, lava, fire, or solid blocks.
		"""
		bx = int(math.floor(tx))
		by = int(math.floor(ty))
		bz = int(math.floor(tz))

		# Floor beneath destination
		floor_b = world.get_block_number((bx, by - 1, bz))
		if not is_walkable_ground(floor_b):
			return False

		# Check 3-block vertical air clearance for 2.9-block height
		for cy in range(by, by + 3):
			b = world.get_block_number((bx, cy, bz))
			if b != 0 and not is_liquid_or_fire_block(b):
				return False
			if is_water_block(b) or is_lava_block(b) or b == 78:
				return False

		# Check horizontal box clearance (0.6 x 0.6)
		hw = 0.3
		for cx in (int(math.floor(tx - hw)), int(math.floor(tx + hw))):
			for cz in (int(math.floor(tz - hw)), int(math.floor(tz + hw))):
				for cy in range(by, by + 3):
					b = world.get_block_number((cx, cy, cz))
					if b != 0 and not is_liquid_or_fire_block(b):
						return False

		return True

	def teleport_randomly(self, world, max_h=32, max_v=16, near_pos=None):
		"""
		Attempts to teleport to a safe location in the environment.
		Optionally targets an area near 'near_pos' (e.g. flanking behind the player).
		"""
		base_x, base_y, base_z = near_pos if near_pos else self.position

		for _ in range(16):
			rx = base_x + random.uniform(-max_h, max_h)
			rz = base_z + random.uniform(-max_h, max_h)
			ry_start = int(math.floor(base_y + random.uniform(-max_v / 2.0, max_v / 2.0)))

			# Scan down to find solid floor
			found_y = None
			for y in range(min(125, ry_start + 4), max(1, ry_start - 8), -1):
				b = world.get_block_number((int(math.floor(rx)), y - 1, int(math.floor(rz))))
				if is_walkable_ground(b):
					found_y = y
					break

			if found_y is not None and self.is_safe_teleport_dest(world, rx, found_y, rz):
				self.position = [rx, float(found_y), rz]
				self.velocity = [0.0, 0.0, 0.0]
				self.target_dest = None
				self.is_moving = False
				self.teleport_cooldown = random.uniform(2.0, 4.0)
				return True

		return False

	def take_damage(self, damage, attacker_pos=None, is_fall=False, world=None, *args, **kwargs):
		"""Damaging an Enderman triggers immediate hostility and evasive teleportation."""
		super().take_damage(damage, attacker_pos=attacker_pos, is_fall=is_fall, *args, **kwargs)

		if attacker_pos:
			self.become_angry(attacker_pos)

		# Immediate evasive teleport on damage (unless killed)
		if not self.is_dead and world:
			self.teleport_randomly(world, max_h=16, max_v=8)

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		if self.is_dead:
			return

		if self.attack_anim_time > 0:
			self.attack_anim_time = max(0.0, self.attack_anim_time - dt)

		if self.teleport_cooldown > 0:
			self.teleport_cooldown = max(0.0, self.teleport_cooldown - dt)

		# 1. WATER REACTION: Taking water damage and immediately teleporting away
		curr_bx = int(math.floor(self.position[0]))
		curr_by = int(math.floor(self.position[1]))
		curr_bz = int(math.floor(self.position[2]))
		b_feet = world.get_block_number((curr_bx, curr_by, curr_bz))
		b_body = world.get_block_number((curr_bx, curr_by + 1, curr_bz))

		if is_water_block(b_feet) or is_water_block(b_body):
			self.take_damage(1, world=world)
			self.teleport_randomly(world, max_h=32, max_v=16)

		# 2. EYE CONTACT AGGRO DETECTION
		if not self.is_angry and player_pos and camera:
			if self.check_player_stare(world, player_pos, camera):
				self.become_angry(player_pos)

		# 3. ANGER & COMBAT / PURSUIT
		if self.is_angry:
			self.anger_timer = max(0.0, self.anger_timer - dt)

			# Distance to player
			dist_to_player = float('inf')
			if player_pos:
				pdx = player_pos[0] - self.position[0]
				pdy = player_pos[1] - self.position[1]
				pdz = player_pos[2] - self.position[2]
				dist_to_player = math.sqrt(pdx * pdx + pdy * pdy + pdz * pdz)

			is_creative = getattr(camera, 'flying', False) or (camera and getattr(camera, 'health', 1) <= 0)

			# Calm down if anger timer expired, player died/in creative, or player moved far away (>36 blocks)
			if self.anger_timer <= 0.0 or is_creative or dist_to_player > 36.0:
				self.is_angry = False
				self.is_screaming = False
				self.speed = 0.30
				self.target = None
			else:
				self.target = tuple(player_pos) if player_pos else None

				# Stare countdown before charging
				if self.stare_timer > 0:
					self.stare_timer -= dt
					self.is_moving = False
					self.velocity[0] = 0.0
					self.velocity[2] = 0.0
					if player_pos:
						dx = player_pos[0] - self.position[0]
						dz = player_pos[2] - self.position[2]
						self.target_yaw = math.atan2(dx, dz)
				else:
					# Tactical Combat Teleportation during pursuit (only when in active combat within 24m)
					self.combat_teleport_timer -= dt
					if self.combat_teleport_timer <= 0:
						self.combat_teleport_timer = random.uniform(5.0, 9.0)
						if player_pos and 3.0 < dist_to_player <= 24.0 and random.random() < 0.40 and self.teleport_cooldown <= 0:
							# Flank behind or near player
							px, py, pz = player_pos
							flank_angle = camera.rotation[0] + math.pi if camera else random.uniform(0, math.tau)
							flank_x = px + math.cos(flank_angle) * random.uniform(3.0, 6.0)
							flank_z = pz + math.sin(flank_angle) * random.uniform(3.0, 6.0)
							self.teleport_randomly(world, max_h=8, max_v=4, near_pos=(flank_x, py, flank_z))

					# Melee pursuit & attack
					self.melee_goal.update(dt, world, player_pos, camera=camera, gui=gui, flying=flying)
		else:
			# Neutral idle wander
			self.is_screaming = False
			self.stroll_goal.update(dt, world)

		# Base mob physics, gravity, and terrain collisions
		super(HostileEntity, self).update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)

	def get_loot_drops(self, is_on_fire=False, looting_level=None):
		if looting_level is None:
			looting_level = getattr(self, "last_looting_level", 0)
		pearl_chance = 0.50 + 0.15 * looting_level
		pearl_count = random.randint(0, 1 + looting_level) if random.random() < pearl_chance else 0
		xp = 5
		drops = []
		if pearl_count > 0:
			drops.append((176, pearl_count))  # Ender Pearl (176)
		return drops, xp


class SilverfishEntity(HostileEntity):
	"""
	Minecraft Java Edition Silverfish Mob
	- Health: 8 HP (4 hearts)
	- Hitbox: 0.4 x 0.3
	- Damage: 1 HP (0.5 hearts)
	- Speed: 0.25 (wander), 0.35 (chasing)
	- XP: 5 XP
	- Calls nearby Silverfish and awakens Infested Blocks when damaged
	"""
	def __init__(self, entity_id, position):
		super().__init__(entity_id, position, mob_type="silverfish", max_health=8, speed=0.25, width=0.4, height=0.3)
		self.attack_damage = 1
		self.attack_cooldown = 1.0
		self.melee_goal = MeleeAttackGoal(self, attack_range=1.2, damage=1, cooldown=1.0)

	def take_damage(self, damage, attacker_pos=None, is_fire=False, is_drowning=False, is_fall=False, world=None, mob_manager=None, *args, **kwargs):
		res = super().take_damage(damage, attacker_pos=attacker_pos, is_fire=is_fire, is_drowning=is_drowning, is_fall=is_fall, world=world, mob_manager=mob_manager, *args, **kwargs)
		if attacker_pos:
			self.target = tuple(attacker_pos)
		# Alert nearby Silverfish & Infested Blocks when damaged
		if mob_manager and self.target:
			for mob in mob_manager.mobs:
				if mob.mob_type == "silverfish" and mob is not self:
					dx = mob.position[0] - self.position[0]
					dz = mob.position[2] - self.position[2]
					if math.sqrt(dx * dx + dz * dz) <= 16.0:
						mob.target = self.target

		# Awaken nearby Infested Blocks (184, 185, 186, 187)
		if world and mob_manager and random.random() < 0.35:
			px, py, pz = int(self.position[0]), int(self.position[1]), int(self.position[2])
			for dx in range(-3, 4):
				for dy in range(-2, 3):
					for dz in range(-3, 4):
						b_pos = (px + dx, py + dy, pz + dz)
						b_num = world.get_block_number(b_pos)
						if b_num in (184, 185, 186, 187):
							world.set_block(b_pos, 0)
							spawn_pos = (b_pos[0] + 0.5, b_pos[1] + 0.1, b_pos[2] + 0.5)
							new_sf = mob_manager.spawn_mob("silverfish", spawn_pos)
							new_sf.target = self.target
							break
		return res

	def update(self, dt, world, player_pos, camera=None, gui=None, arrow_manager=None, time_of_day=0.5, flying=False, *args, **kwargs):
		super().update(dt, world, player_pos, camera=camera, gui=gui, arrow_manager=arrow_manager, time_of_day=time_of_day, flying=flying, *args, **kwargs)
		if not self.is_dead:
			self.melee_goal.update(dt, world, player_pos, camera=camera, gui=gui, flying=flying)

	def get_loot_drops(self, is_on_fire=False):
		return [], 5



