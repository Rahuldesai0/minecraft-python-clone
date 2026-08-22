import math
import pyglet
import matrix
import block_state

class Camera:
	def __init__(self, shader, width, height):
		self.width = width
		self.height = height
		self.mv_matrix = matrix.Matrix()
		self.p_matrix = matrix.Matrix()
		self.shader = shader
		self.shader_matrix_location = self.shader.find_uniform(b"matrix")
		self.input = [0, 0, 0]
		self.position = [0, 81.5, 0]
		self.rotation = [-math.tau / 4, 0]
        
		self.velocity_y = 0.0
		self.on_ground = False
		self.sneaking = False
		self.eye_offset = 1.62

		# Survival Mode Health (20 HP = 10 Hearts) & Damage Tracking
		self.health = 20
		self.max_health = 20
		self.fall_start_y = None
		self.hurt_time = 0.0
		self.last_damage_time = 0.0
		self.fire_timer = 0.0
		self.fire_damage_timer = 0.0

		# Survival Mode Hunger (20 points = 10 Drumsticks), Saturation & Exhaustion Tracking
		self.hunger = 20
		self.max_hunger = 20
		self.saturation = 5.0
		self.exhaustion = 0.0

		# Oxygen & Drowning Tracking (10 bubbles = 10.0s air underwater)
		self.air = 10.0
		self.max_air = 10.0
		self.drown_damage_timer = 0.0

		self.fov_zoom = 0.0
		self.absorption = 0.0
		self.gui = None

		# Nether Portal Transition Tracking
		self.portal_timer = 0.0
		self.portal_cooldown = 0.0
		self.is_inside_portal = False

	def eat_food(self, hunger_points, saturation_points, absorption_points=0.0):
		"""Restores hunger and saturation (saturation is capped at current hunger level) and grants absorption hearts."""
		self.hunger = min(self.max_hunger, self.hunger + hunger_points)
		self.saturation = min(float(self.hunger), self.saturation + saturation_points)
		if absorption_points > 0:
			self.absorption = max(getattr(self, "absorption", 0.0), float(absorption_points))

	def add_exhaustion(self, amount):
		"""Adds exhaustion and processes hunger/saturation depletion when reaching 4.0."""
		self.exhaustion += amount
		while self.exhaustion >= 4.0:
			self.exhaustion -= 4.0
			if self.saturation > 0:
				self.saturation = max(0.0, self.saturation - 1.0)
			else:
				self.hunger = max(0, self.hunger - 1)

	def take_damage(self, damage, flying=False, gui=None, world=None):
		import time
		is_creative = flying or getattr(self, "flying", False) or getattr(getattr(self, "window", None), "flying", False)
		if is_creative or damage <= 0 or self.health <= 0:
			return

		gui_ref = gui or self.gui
		if gui_ref and hasattr(gui_ref, "get_total_armor_protection"):
			defense = gui_ref.get_total_armor_protection()
			if defense > 0:
				reduction = min(0.80, defense * 0.04)
				damage = max(1.0, damage * (1.0 - reduction))
		
		# Absorption hearts absorb damage first
		if getattr(self, "absorption", 0.0) > 0:
			if damage <= self.absorption:
				self.absorption -= damage
				damage = 0.0
			else:
				damage -= self.absorption
				self.absorption = 0.0

		if damage > 0:
			self.health = max(0, self.health - damage)
		self.hurt_time = 0.4
		self.last_damage_time = time.time()

		if self.health == 0:
			death_pos = list(self.position)
			gui_ref = gui or self.gui
			id_mgr = getattr(world, 'item_drop_manager', None)
			window_ref = getattr(self, 'window', None)
			if not id_mgr and gui_ref and hasattr(gui_ref, 'window'):
				id_mgr = getattr(gui_ref.window, 'item_drop_manager', None)
			if not window_ref and gui_ref and hasattr(gui_ref, 'window'):
				window_ref = gui_ref.window

			# 1. Drop all player items at death position in current dimension
			if gui_ref and hasattr(gui_ref, 'drop_all_on_death'):
				gui_ref.drop_all_on_death(death_pos, id_mgr)

			# 2. Respawn at Overworld (0, 0) via Window or direct respawn
			if window_ref and hasattr(window_ref, 'respawn_player'):
				window_ref.respawn_player()
			else:
				self.respawn(world)

	def respawn(self, world=None):
		self.health = self.max_health
		self.hunger = self.max_hunger
		self.saturation = 5.0
		self.exhaustion = 0.0
		self.absorption = 0.0

		spawn_y = None
		if world:
			# Ensure chunk (0, 0) is generated if needed
			if hasattr(world, 'chunks') and (0, 0, 0) not in world.chunks and hasattr(world, 'generate_chunk'):
				try:
					world.chunks[(0, 0, 0)] = world.generate_chunk(0, 0)
				except Exception:
					pass

			for y in range(255, 0, -1):
				b = world.get_block_number((0, y, 0))
				if b != 0 and b not in (9, 19, 15, 20):
					spawn_y = y
					break

		if spawn_y is None:
			spawn_y = 64

		# Position player right on the ground surface at (0, 0) in Overworld
		eye_h = getattr(self, 'eye_offset', 1.62)
		self.position = [0.5, spawn_y + 1.0 + eye_h, 0.5]
		self.velocity_y = 0.0
		self.fall_start_y = None
		self.fire_timer = 0.0
		self.fire_damage_timer = 0.0
		self.air = self.max_air
		self.drown_damage_timer = 0.0
		self.portal_timer = 0.0
		self.portal_cooldown = 4.0

	def round_position(self, position):
		return [round(coord) for coord in position]

	def is_head_underwater(self, world):
		"""Checks if the player's head / eyes are submerged in water (9 or 19)."""
		head_bx = int(round(self.position[0]))
		head_by = int(round(self.position[1]))
		head_bz = int(round(self.position[2]))
		return world.get_block_number((head_bx, head_by, head_bz)) in (9, 19)

	def is_touching_fire(self, world):
		"""Checks if the player's bounding box intersects a Fire block (78)."""
		half_width = 0.3
		eye_h = getattr(self, 'eye_offset', 1.62)
		standing_height = 1.5 if getattr(self, 'sneaking', False) else 1.75

		body_min_x = self.position[0] - half_width
		body_max_x = self.position[0] + half_width
		body_min_y = self.position[1] - eye_h
		body_max_y = body_min_y + standing_height
		body_min_z = self.position[2] - half_width
		body_max_z = self.position[2] + half_width

		min_bx = int(math.floor(body_min_x + 0.5))
		max_bx = int(math.floor(body_max_x + 0.5))
		min_by = int(math.floor(body_min_y + 0.5))
		max_by = int(math.floor(body_max_y + 0.5))
		min_bz = int(math.floor(body_min_z + 0.5))
		max_bz = int(math.floor(body_max_z + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num == 78 or (bx, by, bz) in getattr(world, 'active_fires', {}):
						return True
		return False

	def is_in_water(self, world):
		"""Checks if the player's bounding box touches water (9 or 19)."""
		half_width = 0.3
		eye_h = getattr(self, 'eye_offset', 1.62)
		standing_height = 1.5 if getattr(self, 'sneaking', False) else 1.75

		body_min_x = self.position[0] - half_width
		body_max_x = self.position[0] + half_width
		body_min_y = self.position[1] - eye_h
		body_max_y = body_min_y + standing_height
		body_min_z = self.position[2] - half_width
		body_max_z = self.position[2] + half_width

		min_bx = int(math.floor(body_min_x + 0.5))
		max_bx = int(math.floor(body_max_x + 0.5))
		min_by = int(math.floor(body_min_y + 0.5))
		max_by = int(math.floor(body_max_y + 0.5))
		min_bz = int(math.floor(body_min_z + 0.5))
		max_bz = int(math.floor(body_max_z + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num in (9, 19):
						return True
		return False

	def is_in_lava(self, world):
		"""Checks if the player's bounding box touches lava (15 or 20)."""
		half_width = 0.3
		eye_h = getattr(self, 'eye_offset', 1.62)
		standing_height = 1.5 if getattr(self, 'sneaking', False) else 1.75

		body_min_x = self.position[0] - half_width
		body_max_x = self.position[0] + half_width
		body_min_y = self.position[1] - eye_h
		body_max_y = body_min_y + standing_height
		body_min_z = self.position[2] - half_width
		body_max_z = self.position[2] + half_width

		min_bx = int(math.floor(body_min_x + 0.5))
		max_bx = int(math.floor(body_max_x + 0.5))
		min_by = int(math.floor(body_min_y + 0.5))
		max_by = int(math.floor(body_max_y + 0.5))
		min_bz = int(math.floor(body_min_z + 0.5))
		max_bz = int(math.floor(body_max_z + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num in (15, 20):
						return True
		return False

	def is_in_liquid(self, world):
		bx = int(round(self.position[0]))
		by = int(round(self.position[1]))
		bz = int(round(self.position[2]))
		eye_b = world.get_block_number((bx, by, bz))
		feet_b = world.get_block_number((bx, by - 1, bz))
		return eye_b in (9, 19, 15, 20) or feet_b in (9, 19, 15, 20)

	def is_in_portal(self, world):
		"""Checks if the player's bounding box intersects Nether Portal blocks (88 or 89)."""
		half_width = 0.3
		eye_h = getattr(self, 'eye_offset', 1.62)
		standing_height = 1.5 if getattr(self, 'sneaking', False) else 1.75

		body_min_x = self.position[0] - half_width
		body_max_x = self.position[0] + half_width
		body_min_y = self.position[1] - eye_h
		body_max_y = body_min_y + standing_height
		body_min_z = self.position[2] - half_width
		body_max_z = self.position[2] + half_width

		min_bx = int(math.floor(body_min_x + 0.5))
		max_bx = int(math.floor(body_max_x + 0.5))
		min_by = int(math.floor(body_min_y + 0.5))
		max_by = int(math.floor(body_max_y + 0.5))
		min_bz = int(math.floor(body_min_z + 0.5))
		max_bz = int(math.floor(body_max_z + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num in (88, 89):
						return True
		return False

	def is_in_end_portal(self, world):
		"""Checks if the player's bounding box intersects End Portal blocks (183)."""
		half_width = 0.3
		eye_h = getattr(self, 'eye_offset', 1.62)
		standing_height = 1.5 if getattr(self, 'sneaking', False) else 1.75

		body_min_x = self.position[0] - half_width
		body_max_x = self.position[0] + half_width
		body_min_y = self.position[1] - eye_h
		body_max_y = body_min_y + standing_height
		body_min_z = self.position[2] - half_width
		body_max_z = self.position[2] + half_width

		min_bx = int(math.floor(body_min_x + 0.5))
		max_bx = int(math.floor(body_max_x + 0.5))
		min_by = int(math.floor(body_min_y + 0.5))
		max_by = int(math.floor(body_max_y + 0.5))
		min_bz = int(math.floor(body_min_z + 0.5))
		max_bz = int(math.floor(body_max_z + 0.5))

		for bx in range(min_bx, max_bx + 1):
			for by in range(min_by, max_by + 1):
				for bz in range(min_bz, max_bz + 1):
					b_num = world.get_block_number((bx, by, bz))
					if b_num == 183:
						return True
		return False

	def update_camera(self, delta_time, sprinting, world, flying, keys_down):
		import time
		import random

		# Cap delta_time to prevent huge displacement on lag spikes
		delta_time = min(delta_time, 0.05)

		# Decay hurt time red flash overlay
		if self.hurt_time > 0:
			self.hurt_time = max(0.0, self.hurt_time - delta_time)

		# Fire, Lava & Water physics / damage
		if self.is_in_water(world):
			self.fire_timer = 0.0
			self.fire_damage_timer = 0.0
		elif not flying:
			in_lava = self.is_in_lava(world)
			touching_fire = self.is_touching_fire(world)

			if in_lava or touching_fire:
				# Refresh / set burn timer to 5 to 6 seconds
				self.fire_timer = max(self.fire_timer, random.uniform(5.0, 6.0))

			if in_lava:
				# Lava deals heavy damage (4 HP / 2 hearts every 0.5s)
				self.fire_damage_timer += delta_time
				if self.fire_damage_timer >= 0.5:
					self.fire_damage_timer = 0.0
					self.take_damage(4, flying=flying, world=world)
			elif self.fire_timer > 0.0:
				# Fire / Afterburn damage (1 HP every 0.8s in fire block, 1.0s outside)
				self.fire_timer = max(0.0, self.fire_timer - delta_time)
				self.fire_damage_timer += delta_time
				damage_interval = 0.8 if touching_fire else 1.0
				if self.fire_damage_timer >= damage_interval:
					self.fire_damage_timer = 0.0
					self.take_damage(1, flying=flying, world=world)
			else:
				self.fire_damage_timer = 0.0

		# Oxygen & Drowning Mechanics
		head_underwater = self.is_head_underwater(world)
		if head_underwater and not flying:
			# Depletes 1 bubble per second in water (10.0s total air)
			self.air = max(0.0, self.air - delta_time)
			if self.air <= 0.0:
				self.drown_damage_timer += delta_time
				# Drowning damage (2 HP / 1 heart per second once bubbles run out)
				if self.drown_damage_timer >= 1.0:
					self.drown_damage_timer = 0.0
					self.take_damage(2, flying=flying, world=world)
			else:
				self.drown_damage_timer = 0.0
		else:
			self.drown_damage_timer = 0.0
			# When player is out of water, bubbles replenish one per second
			if self.air < self.max_air:
				self.air = min(self.max_air, self.air + delta_time * 1.0)

		# Passive Health Regeneration in Survival Mode (Requires Hunger >= 18 points / 9 drumsticks)
		if not flying and self.hunger >= 18 and 0 < self.health < self.max_health:
			if (time.time() - self.last_damage_time) >= 4.0:
				self.health = min(self.max_health, self.health + 1)
				self.last_damage_time = time.time()
				self.add_exhaustion(6.0)

		in_liquid = self.is_in_liquid(world)

		# Ground check: verify if player's feet are resting on a solid block
		is_grounded = not self.check_collision(world, [self.position[0], self.position[1] - 0.05, self.position[2]])
		self.on_ground = is_grounded

		# Survival Mode Fall Damage Physics:
		# Safe fall distance is 3 blocks. Landing in water/lava resets fall distance to 0.
		if flying or in_liquid:
			self.fall_start_y = None
		else:
			if not self.on_ground:
				if self.fall_start_y is None or self.position[1] > self.fall_start_y:
					self.fall_start_y = self.position[1]
			else:
				if self.fall_start_y is not None:
					fall_dist = self.fall_start_y - self.position[1]
					if fall_dist > 3.0:
						dmg = int(round(fall_dist - 3.0))
						if dmg > 0:
							self.take_damage(dmg, flying=flying, world=world)
					self.fall_start_y = None

		# Sneak check: Shift pressed while on ground, not flying, not swimming
		is_shift_down = keys_down.get(pyglet.window.key.LSHIFT, False)
		self.sneaking = is_shift_down and self.on_ground and not flying and not in_liquid

		# Smooth eye height lowering when sneaking (1.28 when sneaking vs 1.62 standing)
		target_eye = 1.28 if self.sneaking else 1.62
		old_eye = self.eye_offset
		self.eye_offset += (target_eye - self.eye_offset) * min(1.0, 18.0 * delta_time)
		if self.on_ground:
			self.position[1] += (self.eye_offset - old_eye)
		self.flying = flying
		base_speed = 4.3  # Minecraft walking speed (~4.3 m/s)
		if self.sneaking:
			speed = 1.3  # Sneak walking speed (~1.3 m/s)
		else:
			sprint_multiplier = 1.3 if sprinting else 1.0
			speed = base_speed * sprint_multiplier

		# Soul Sand Slowdown (Block 85 under player reduces walking speed by 60%)
		if self.on_ground and not flying and not in_liquid:
			bx = int(math.floor(self.position[0]))
			by = int(math.floor(self.position[1] - self.eye_offset - 0.1))
			bz = int(math.floor(self.position[2]))
			if world.get_block_number((bx, by, bz)) == 85:
				speed *= 0.40

		# Nether & End Portal Timer & Cooldown Tracking
		self.portal_cooldown = max(0.0, self.portal_cooldown - delta_time)
		self.is_inside_portal = self.is_in_portal(world)
		self.is_inside_end_portal = self.is_in_end_portal(world)
		if self.is_inside_portal:
			self.portal_timer += delta_time
		else:
			self.portal_timer = 0.0

		# Void Damage (Y < -10)
		if self.position[1] < -10.0 and not flying:
			if not hasattr(self, "_last_void_damage_time") or time.time() - self._last_void_damage_time >= 0.5:
				self._last_void_damage_time = time.time()
				self.take_damage(4, world=world)

		movement_vector = [0.0, 0.0, 0.0]

		if flying:
			# Flying Mode: move up with Space, down with Shift
			up_down = 0.0
			if keys_down.get(pyglet.window.key.SPACE, False):
				up_down += 10.0
			if keys_down.get(pyglet.window.key.LSHIFT, False):
				up_down -= 10.0
			movement_vector[1] = up_down * delta_time
			self.velocity_y = 0.0
		elif in_liquid:
			# Liquid Mode: swim up with Space. Near surface gives strong water jump impulse (v_y = 7.8 m/s) onto shore!
			bx = int(round(self.position[0]))
			by = int(round(self.position[1]))
			bz = int(round(self.position[2]))
			eye_b = world.get_block_number((bx, by, bz))
			above_eye_b = world.get_block_number((bx, by + 1, bz))

			near_surface = (eye_b not in (9, 19, 15, 20)) or (above_eye_b not in (9, 19, 15, 20))

			if keys_down.get(pyglet.window.key.SPACE, False):
				if near_surface:
					# Launch out of water onto shore (7.8 m/s impulse & full walking speed)
					self.velocity_y = 7.8
					movement_vector[1] = self.velocity_y * delta_time
					speed = base_speed
				else:
					# Deep swimming upward
					speed *= 0.75
					movement_vector[1] = 5.5 * delta_time
					self.velocity_y = 0.0
			else:
				speed *= 0.65
				movement_vector[1] = -2.0 * delta_time
				self.velocity_y = 0.0
		else:
			# Normal Minecraft Ground & Gravity Physics
			if self.on_ground:
				if keys_down.get(pyglet.window.key.SPACE, False):
					# Jump impulse: v0 = 8.5 m/s yields an exact 1.25-block jump height with g = 28.5 m/s^2
					self.velocity_y = 8.5
					self.on_ground = False
					self.add_exhaustion(0.2 if sprinting else 0.05)
				else:
					self.velocity_y = 0.0
			else:
				# Apply gravity (28.5 m/s^2)
				self.velocity_y -= 28.5 * delta_time
				self.velocity_y = max(-35.0, self.velocity_y)  # Terminal velocity

			movement_vector[1] = self.velocity_y * delta_time

		# Horizontal Movement (X, Z)
		if self.input[0] != 0 or self.input[2] != 0:
			angle = self.rotation[0] - math.atan2(self.input[2], self.input[0]) + math.tau / 4
			movement_vector[0] = math.cos(angle) * speed * delta_time
			movement_vector[2] = math.sin(angle) * speed * delta_time

		# Sneak Ledge Protection: prevent stepping off block edges into air
		if self.sneaking and self.on_ground:
			test_x_pos = [self.position[0] + movement_vector[0], self.position[1] - 0.05, self.position[2]]
			if self.check_collision(world, test_x_pos):
				movement_vector[0] = 0.0

			test_z_pos = [self.position[0], self.position[1] - 0.05, self.position[2] + movement_vector[2]]
			if self.check_collision(world, test_z_pos):
				movement_vector[2] = 0.0

		next_position = [
			self.position[0] + movement_vector[0],
			self.position[1] + movement_vector[1],
			self.position[2] + movement_vector[2],
		]

		# X-axis collision
		if self.check_collision(world, [next_position[0], self.position[1], self.position[2]]):
			self.position[0] = next_position[0]

		# Y-axis incremental collision resolution
		dy = movement_vector[1]
		if dy != 0:
			step_size = 0.4
			remaining = dy
			sign = 1 if dy > 0 else -1
			while abs(remaining) > 0.001:
				step = sign * min(step_size, abs(remaining))
				test_y = self.position[1] + step
				if self.check_collision(world, [self.position[0], test_y, self.position[2]]):
					self.position[1] = test_y
					remaining -= step
				else:
					# Hit a ceiling or floor
					if dy < 0:
						self.velocity_y = 0.0
						self.on_ground = True
					elif dy > 0:
						self.velocity_y = 0.0
					break

		# Z-axis collision
		if self.check_collision(world, [self.position[0], self.position[1], next_position[2]]):
			self.position[2] = next_position[2]

	def get_block_boxes(self, block_x, block_y, block_z, block_num, world=None):
		"""Returns list of AABB bounding boxes (min_x, min_y, min_z, max_x, max_y, max_z) for block_num."""
		if block_num == 0 or block_num in (9, 19, 15, 20, 10, 12, 31, 33, 78, 88, 89, 94, 183):
			return []

		# Oak Fence (51), Nether Brick Fence (91) & Stone Wall (52) - 1.5 blocks tall collision height
		if block_num in (51, 52, 91):
			r = 0.25 if block_num in (51, 91) else 0.3
			return [(block_x - r, block_y - 0.5, block_z - r, block_x + r, block_y + 1.0, block_z + r)]

		if block_num in (75, 76):
			st = world.get_block_state((block_x, block_y, block_z)) if world else None
			gate_open = getattr(st, 'open_state', False) or (block_num == 76)
			if not gate_open:
				facing = getattr(st, 'facing', 'NORTH') if st else 'NORTH'
				if facing in ('NORTH', 'SOUTH'):
					return [(block_x - 0.5, block_y - 0.5, block_z - 0.125, block_x + 0.5, block_y + 1.0, block_z + 0.125)]
				else:
					return [(block_x - 0.125, block_y - 0.5, block_z - 0.5, block_x + 0.125, block_y + 1.0, block_z + 0.5)]

		return block_state.get_block_hitboxes(world, (block_x, block_y, block_z), block_num)

	def check_collision(self, world, position):
		"""Return True when the camera's player body is unobstructed.
		Liquid blocks (water & lava) are passable and do not cause collision.
		"""
		x, y, z = position

		half_width = 0.3
		eye_h = getattr(self, 'eye_offset', 1.62)
		standing_height = 1.5 if getattr(self, 'sneaking', False) else 1.75

		body_min_x = x - half_width
		body_max_x = x + half_width
		body_min_y = y - eye_h
		body_max_y = body_min_y + standing_height
		body_min_z = z - half_width
		body_max_z = z + half_width

		epsilon = 0.001

		min_bx = round(body_min_x + epsilon)
		max_bx = round(body_max_x - epsilon)
		min_by = round(body_min_y + epsilon)
		max_by = round(body_max_y - epsilon)
		min_bz = round(body_min_z + epsilon)
		max_bz = round(body_max_z - epsilon)

		for block_x in range(min_bx, max_bx + 1):
			for block_y in range(min_by - 1, max_by + 2):
				for block_z in range(min_bz, max_bz + 1):
					block_num = world.get_block_number((block_x, block_y, block_z))
					boxes = self.get_block_boxes(block_x, block_y, block_z, block_num, world=world)
					for min_x, min_y, min_z, max_x, max_y, max_z in boxes:
						if (body_min_x < max_x and body_max_x > min_x and
							body_min_y < max_y and body_max_y > min_y and
							body_min_z < max_z and body_max_z > min_z):
							return False
		return True

	def intersects_player(self, block_position):
		"""Return True if placing a block at block_position (bx, by, bz)
		would intersect the player's body bounding box.
		Allows sneaking edge block placement while preventing block entrapment.
		"""
		px, py, pz = self.position
		bx, by, bz = block_position

		half_width = 0.22
		eye_h = getattr(self, 'eye_offset', 1.62)
		body_h = 1.4 if getattr(self, 'sneaking', False) else 1.65

		p_min_x, p_max_x = px - half_width, px + half_width
		p_min_y = py - eye_h + 0.01  # Feet bottom + epsilon
		p_max_y = p_min_y + body_h
		p_min_z, p_max_z = pz - half_width, pz + half_width

		b_min_x, b_max_x = bx - 0.5, bx + 0.5
		b_min_y, b_max_y = by - 0.5, by + 0.5
		b_min_z, b_max_z = bz - 0.5, bz + 0.5

		overlap_x = (p_min_x < b_max_x) and (p_max_x > b_min_x)
		overlap_y = (p_min_y < b_max_y) and (p_max_y > b_min_y)
		overlap_z = (p_min_z < b_max_z) and (p_max_z > b_min_z)

		return overlap_x and overlap_y and overlap_z




	def get_view_position_and_rotation(self, perspective=0, world=None):
		"""
		Returns (cam_pos, cam_rot) based on perspective mode:
		0: First Person (camera at eye level)
		1: Third Person Back (camera behind player looking forward)
		2: Third Person Front (camera in front of player looking backward)
		"""
		px, py, pz = self.position
		yaw, pitch = self.rotation

		if perspective == 0:
			return (px, py, pz), (yaw, pitch)

		elif perspective == 1:
			# Third Person Back
			dx = math.sin(yaw) * math.cos(pitch)
			dy = math.sin(pitch)
			dz = -math.cos(yaw) * math.cos(pitch)
			dist = 3.5

			if world:
				steps = 20
				for i in range(1, steps + 1):
					step_d = (dist * i) / steps
					tx, ty, tz = px - dx * step_d, py - dy * step_d, pz - dz * step_d
					bx, by, bz = int(round(tx)), int(round(ty)), int(round(tz))
					b_num = world.get_block_number((bx, by, bz))
					if b_num != 0 and b_num not in (9, 19, 15, 20):
						dist = max(0.5, step_d - 0.3)
						break

			cx = px - dx * dist
			cy = py - dy * dist
			cz = pz - dz * dist
			return (cx, cy, cz), (yaw, pitch)

		elif perspective == 2:
			# Third Person Front: Camera positioned in front of player (+D * 3.5), looking back at player's face!
			dx = math.sin(yaw) * math.cos(pitch)
			dy = math.sin(pitch)
			dz = -math.cos(yaw) * math.cos(pitch)
			dist = 3.5

			if world:
				steps = 20
				for i in range(1, steps + 1):
					step_d = (dist * i) / steps
					tx, ty, tz = px + dx * step_d, py + dy * step_d, pz + dz * step_d
					bx, by, bz = int(round(tx)), int(round(ty)), int(round(tz))
					b_num = world.get_block_number((bx, by, bz))
					if b_num != 0 and b_num not in (9, 19, 15, 20):
						dist = max(0.5, step_d - 0.3)
						break

			cx = px + dx * dist
			cy = py + dy * dist
			cz = pz + dz * dist

			front_yaw = yaw + math.pi
			front_pitch = -pitch
			return (cx, cy, cz), (front_yaw, front_pitch)

		return (px, py, pz), (yaw, pitch)

	def update_matrices(self, perspective=0, world=None):
		cam_pos, cam_rot = self.get_view_position_and_rotation(perspective, world)

		# Projection matrix (with dynamic FOV zoom when drawing bow)
		fov = 90.0 * (1.0 - getattr(self, "fov_zoom", 0.0))
		self.p_matrix.load_identity()
		self.p_matrix.perspective(fov, float(self.width) / self.height, 0.1, 500)

		# Modelview matrix
		self.mv_matrix.load_identity()
		self.mv_matrix.rotate_2d(cam_rot[0] + math.tau / 4, cam_rot[1])
		self.mv_matrix.translate(-cam_pos[0], -cam_pos[1], -cam_pos[2])

		# Modelviewprojection matrix
		mvp_matrix = self.mv_matrix * self.p_matrix
		self.shader.uniform_matrix(self.shader_matrix_location, mvp_matrix)
