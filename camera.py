import math
import pyglet
import matrix

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

		# Survival Mode Hunger (20 points = 10 Drumsticks), Saturation & Exhaustion Tracking
		self.hunger = 20
		self.max_hunger = 20
		self.saturation = 5.0
		self.exhaustion = 0.0
		self.gui = None

	def eat_food(self, hunger_points, saturation_points):
		"""Restores hunger and saturation (saturation is capped at current hunger level)."""
		self.hunger = min(self.max_hunger, self.hunger + hunger_points)
		self.saturation = min(float(self.hunger), self.saturation + saturation_points)

	def add_exhaustion(self, amount):
		"""Adds exhaustion and processes hunger/saturation depletion when reaching 4.0."""
		self.exhaustion += amount
		while self.exhaustion >= 4.0:
			self.exhaustion -= 4.0
			if self.saturation > 0:
				self.saturation = max(0.0, self.saturation - 1.0)
			else:
				self.hunger = max(0, self.hunger - 1)

	def take_damage(self, damage, flying=False, gui=None):
		import time
		if flying or damage <= 0 or self.health <= 0:
			return

		gui_ref = gui or self.gui
		if gui_ref and hasattr(gui_ref, "get_total_armor_protection"):
			defense = gui_ref.get_total_armor_protection()
			if defense > 0:
				reduction = min(0.80, defense * 0.04)
				damage = max(1.0, damage * (1.0 - reduction))
		
		self.health = max(0, self.health - damage)
		self.hurt_time = 0.4
		self.last_damage_time = time.time()

		if self.health == 0:
			self.respawn()

	def respawn(self):
		self.health = self.max_health
		self.hunger = self.max_hunger
		self.saturation = 5.0
		self.exhaustion = 0.0
		self.position = [0, 85, 0]
		self.velocity_y = 0.0
		self.fall_start_y = None

	def round_position(self, position):
		return [round(coord) for coord in position]

	def is_in_liquid(self, world):
		bx = int(round(self.position[0]))
		by = int(round(self.position[1]))
		bz = int(round(self.position[2]))
		eye_b = world.get_block_number((bx, by, bz))
		feet_b = world.get_block_number((bx, by - 1, bz))
		return eye_b in (9, 19, 15, 20) or feet_b in (9, 19, 15, 20)

	def update_camera(self, delta_time, sprinting, world, flying, keys_down):
		import time

		# Cap delta_time to prevent huge displacement on lag spikes
		delta_time = min(delta_time, 0.05)

		# Decay hurt time red flash overlay
		if self.hurt_time > 0:
			self.hurt_time = max(0.0, self.hurt_time - delta_time)

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
							self.take_damage(dmg, flying=flying)
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

		base_speed = 4.3  # Minecraft walking speed (~4.3 m/s)
		if self.sneaking:
			speed = 1.3  # Sneak walking speed (~1.3 m/s)
		else:
			sprint_multiplier = 1.3 if sprinting else 1.0
			speed = base_speed * sprint_multiplier

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
			for block_y in range(min_by, max_by + 1):
				for block_z in range(min_bz, max_bz + 1):
					block_num = world.get_block_number((block_x, block_y, block_z))
					if block_num != 0 and block_num not in (9, 19, 15, 20):
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

		# Projection matrix
		self.p_matrix.load_identity()
		self.p_matrix.perspective(90, float(self.width) / self.height, 0.1, 500)

		# Modelview matrix
		self.mv_matrix.load_identity()
		self.mv_matrix.rotate_2d(cam_rot[0] + math.tau / 4, cam_rot[1])
		self.mv_matrix.translate(-cam_pos[0], -cam_pos[1], -cam_pos[2])

		# Modelviewprojection matrix
		mvp_matrix = self.mv_matrix * self.p_matrix
		self.shader.uniform_matrix(self.shader_matrix_location, mvp_matrix)
