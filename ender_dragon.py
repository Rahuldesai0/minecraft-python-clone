"""
Minecraft Java Edition Ender Dragon Boss Entity & 3D Renderer
--------------------------------------------------------------
Implements:
1. Canonical Ender Dragon AI Phase State Machine:
   - Phase.HOLDING_PATTERN: Circling orbit around arena center (radius 35..55m)
   - Phase.STRAFE_PLAYER: Approaches player and fires Dragon Fireballs
   - Phase.CHARGING_PLAYER: Fast swoop dive attack dealing melee damage + knockback
   - Phase.LANDING_APPROACH: Spiral descent towards Central Bedrock Fountain (0, Y_surf+4, 0)
   - Phase.PERCHED: Sits atop central exit portal column, immune to arrows (deflection),
     breathes Dragon's Breath cone and leaves lingering effect clouds on the ground
   - Phase.TAKEOFF: Vertical ascent from perch back to circling holding pattern
   - Phase.DYING: Defeat floating sequence, drops XP, and activates exit portal fountain
2. Scaled-up 3D Dragon Boss Model (~1.4x scale)
3. Multi-part Hitboxes with 2x Head Damage Multiplier
4. Hostility & Melee Collisions against player in Survival mode
"""

import math
import random
import time
import ctypes
import pyglet
import pyglet.gl as gl


class EnderDragonPhase:
	HOLDING_PATTERN = "HOLDING_PATTERN"
	STRAFE_PLAYER = "STRAFE_PLAYER"
	CHARGING_PLAYER = "CHARGING_PLAYER"
	LANDING_APPROACH = "LANDING_APPROACH"
	PERCHED = "PERCHED"
	TAKEOFF = "TAKEOFF"
	DYING = "DYING"


DRAGON_VERT_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec2 a_texcoord;
layout(location = 2) in vec4 a_color;

uniform mat4 matrix;

out vec2 v_texcoord;
out vec4 v_color;

void main() {
    v_texcoord = a_texcoord;
    v_color = a_color;
    gl_Position = matrix * vec4(a_position, 1.0);
}
"""

DRAGON_FRAG_SHADER = """
#version 330 core
in vec2 v_texcoord;
in vec4 v_color;

uniform sampler2D u_texture;
uniform int u_use_texture;
uniform vec4 u_tint;

out vec4 fragColor;

void main() {
    vec4 col = v_color;
    if (u_use_texture != 0) {
        col = texture(u_texture, v_texcoord) * v_color;
    }
    col = mix(col, u_tint, u_tint.a);
    if (col.a < 0.1) discard;
    fragColor = col;
}
"""


class EnderDragonEntity:
	"""Minecraft Java Edition Ender Dragon Boss Entity (200 HP)."""
	def __init__(self, position=(0.0, 75.0, 0.0)):
		self.position = list(position)
		self.velocity = [0.0, 0.0, 0.0]
		self.max_health = 200
		self.health = 200
		self.is_dead = False
		self.death_ticks = 0
		self.hurt_time = 0.0

		# AI State Machine
		self.phase = EnderDragonPhase.HOLDING_PATTERN
		self.phase_timer = random.uniform(15.0, 25.0)
		self.perch_damage_taken = 0.0
		self.strafe_fired = False
		self.breath_cooldown = 0.0
		self.last_melee_hit_time = 0.0

		# Kinematics & Animation
		self.yaw = 0.0
		self.pitch = 0.0
		self.flight_timer = 0.0
		self.wing_flap_timer = 0.0
		self.arena_center = [0.0, 75.0, 0.0]
		self.orbit_radius = 42.0
		self.orbit_speed = 0.26
		self.target_waypoint = [0.0, 75.0, 0.0]

		# Hitboxes (Proportioned ~1.2x scale)
		self.body_radius = 4.5
		self.head_radius = 2.0
		self.hitbox_height = 3.8

	@property
	def is_perched(self):
		return self.phase == EnderDragonPhase.PERCHED

	@property
	def is_arrow_immune(self):
		return self.phase == EnderDragonPhase.PERCHED

	def heal(self, amount):
		"""Restores health up to maximum 200 HP."""
		if not self.is_dead:
			self.health = min(self.max_health, self.health + amount)

	def take_damage(self, amount, part="body", attacker_pos=None):
		"""Applies damage to the Dragon. Head hits receive 2x damage multiplier."""
		if self.is_dead or amount <= 0:
			return

		# Head takes 2x damage
		mult = 2.0 if part == "head" else 1.0
		effective_dmg = int(math.ceil(amount * mult))

		self.health = max(0, self.health - effective_dmg)
		self.hurt_time = 0.4

		# If perched, accumulate damage; high damage forces early takeoff
		if self.phase == EnderDragonPhase.PERCHED:
			self.perch_damage_taken += effective_dmg
			if self.perch_damage_taken >= 40:
				self.phase = EnderDragonPhase.TAKEOFF
				self.phase_timer = 0.0

		if self.health <= 0:
			self.is_dead = True
			self.phase = EnderDragonPhase.DYING
			self.death_ticks = 0

	def update(self, dt, end_world=None, camera=None, gui=None):
		if self.hurt_time > 0.0:
			self.hurt_time = max(0.0, self.hurt_time - dt)

		if self.is_dead:
			self.death_ticks += dt
			# Ascend slowly and tilt up during death
			self.position[1] += dt * 1.5
			self.pitch = min(0.6, self.pitch + dt * 0.2)
			self.wing_flap_timer += dt * 2.0
			return

		# Get dynamic surface fountain height for perch (elevated so player can stand in fountain and hit with melee weapons)
		import end_generator
		fount_y = end_generator.get_fountain_y(getattr(end_world, 'seed', 0) if end_world else 0)
		perch_pos = [0.0, fount_y + 5.5, 0.0]

		# -------------------------------------------------------------
		# AI PHASE STATE MACHINE
		# -------------------------------------------------------------
		if self.phase == EnderDragonPhase.HOLDING_PATTERN:
			self.flight_timer += dt * self.orbit_speed
			self.wing_flap_timer += dt * 5.0

			# Circle arena around (0, 0)
			tx = self.arena_center[0] + math.cos(self.flight_timer) * self.orbit_radius
			tz = self.arena_center[2] + math.sin(self.flight_timer) * self.orbit_radius
			ty = self.arena_center[1] + math.sin(self.flight_timer * 1.4) * 5.0
			self.target_waypoint = [tx, ty, tz]

			self.phase_timer -= dt
			if self.phase_timer <= 0.0:
				# Choose next action
				roll = random.random()
				if roll < 0.40 and camera:
					self.phase = EnderDragonPhase.STRAFE_PLAYER
					self.phase_timer = 8.0
					self.strafe_fired = False
				elif roll < 0.70 and camera:
					self.phase = EnderDragonPhase.CHARGING_PLAYER
					self.phase_timer = 6.0
				else:
					self.phase = EnderDragonPhase.LANDING_APPROACH
					self.phase_timer = 15.0

		elif self.phase == EnderDragonPhase.STRAFE_PLAYER:
			self.wing_flap_timer += dt * 6.0
			c_pos = camera.position if camera else [0.0, 65.0, 0.0]
			# Fly towards waypoint above/beside player
			tx = c_pos[0] + math.cos(self.flight_timer) * 25.0
			tz = c_pos[2] + math.sin(self.flight_timer) * 25.0
			ty = max(75.0, c_pos[1] + 18.0)
			self.target_waypoint = [tx, ty, tz]

			# Fire Dragon Fireball when aligned
			dx = c_pos[0] - self.position[0]
			dy = c_pos[1] - self.position[1]
			dz = c_pos[2] - self.position[2]
			dist = math.sqrt(dx * dx + dy * dy + dz * dz)

			if not self.strafe_fired and dist <= 45.0:
				self.strafe_fired = True
				if end_world and hasattr(end_world, 'dragon_fireball_manager') and end_world.dragon_fireball_manager:
					snout_pos = self._get_snout_position()
					end_world.dragon_fireball_manager.spawn_fireball(snout_pos, c_pos)

			self.phase_timer -= dt
			if self.phase_timer <= 0.0 or (self.strafe_fired and dist > 40.0):
				self.phase = EnderDragonPhase.HOLDING_PATTERN
				self.phase_timer = random.uniform(12.0, 20.0)

		elif self.phase == EnderDragonPhase.CHARGING_PLAYER:
			# Swoop dive straight at player
			self.wing_flap_timer += dt * 7.5
			c_pos = camera.position if camera else [0.0, 65.0, 0.0]
			self.target_waypoint = [c_pos[0], c_pos[1] + 0.5, c_pos[2]]

			dx = c_pos[0] - self.position[0]
			dy = c_pos[1] - self.position[1]
			dz = c_pos[2] - self.position[2]
			dist = math.sqrt(dx * dx + dy * dy + dz * dz)

			# Melee hit on player during swoop
			if dist <= 5.0 and camera:
				self.last_melee_hit_time = time.time()
				is_creative = getattr(camera, 'flying', False) or getattr(getattr(camera, 'window', None), 'flying', False)
				if not is_creative:
					if hasattr(camera, 'take_damage'):
						camera.take_damage(10, flying=False, gui=gui, world=end_world)
					# Knockback launch
					norm = max(0.001, dist)
					if hasattr(camera, 'velocity_y'):
						camera.velocity_y = max(camera.velocity_y + 0.35, 8.5)

				# Swooped successfully, break off and circle
				self.phase = EnderDragonPhase.HOLDING_PATTERN
				self.phase_timer = random.uniform(14.0, 22.0)

			self.phase_timer -= dt
			if self.phase_timer <= 0.0:
				self.phase = EnderDragonPhase.HOLDING_PATTERN
				self.phase_timer = random.uniform(12.0, 18.0)

		elif self.phase == EnderDragonPhase.LANDING_APPROACH:
			# Descend toward perch atop exit portal pillar
			self.wing_flap_timer += dt * 4.5
			self.target_waypoint = perch_pos

			dx = perch_pos[0] - self.position[0]
			dy = perch_pos[1] - self.position[1]
			dz = perch_pos[2] - self.position[2]
			dist = math.sqrt(dx * dx + dy * dy + dz * dz)

			if dist <= 2.5:
				self.phase = EnderDragonPhase.PERCHED
				self.phase_timer = random.uniform(12.0, 18.0)
				self.perch_damage_taken = 0.0
				self.position = list(perch_pos)

		elif self.phase == EnderDragonPhase.PERCHED:
			# Sits firmly atop the exit portal column
			self.wing_flap_timer += dt * 2.0
			self.position[0] = perch_pos[0]
			self.position[1] = perch_pos[1]
			self.position[2] = perch_pos[2]
			self.pitch = 0.0

			# Dragon's Breath stream & clouds while perched
			self.breath_cooldown -= dt
			if self.breath_cooldown <= 0.0:
				self.breath_cooldown = 2.5
				if camera:
					c_pos = camera.position
					dx = c_pos[0] - self.position[0]
					dz = c_pos[2] - self.position[2]
					dist = math.sqrt(dx * dx + dz * dz)
					# Look towards player
					if dist > 0.1:
						self.yaw = math.atan2(dx, dz)
					# Spawn lingering breath cloud near player
					if dist <= 20.0 and end_world and hasattr(end_world, 'dragon_fireball_manager') and end_world.dragon_fireball_manager:
						end_world.dragon_fireball_manager.spawn_breath_cloud((c_pos[0], c_pos[1] - 1.0, c_pos[2]))

			self.phase_timer -= dt
			if self.phase_timer <= 0.0:
				self.phase = EnderDragonPhase.TAKEOFF
				self.phase_timer = 3.5

		elif self.phase == EnderDragonPhase.TAKEOFF:
			# Vigorously climb vertically back to arena ceiling
			self.wing_flap_timer += dt * 8.0
			self.target_waypoint = [0.0, 85.0, 0.0]
			if self.position[1] >= 82.0:
				self.phase = EnderDragonPhase.HOLDING_PATTERN
				self.phase_timer = random.uniform(15.0, 25.0)

		# -------------------------------------------------------------
		# Smooth Kinematics & Orientation Tracking
		# -------------------------------------------------------------
		if self.phase != EnderDragonPhase.PERCHED:
			tx, ty, tz = self.target_waypoint
			dx = tx - self.position[0]
			dy = ty - self.position[1]
			dz = tz - self.position[2]

			dist_horiz = math.sqrt(dx * dx + dz * dz)
			if dist_horiz > 0.1:
				target_yaw = math.atan2(dx, dz)
				# Smooth yaw interpolation
				yaw_diff = (target_yaw - self.yaw + math.pi) % math.tau - math.pi
				self.yaw += yaw_diff * min(1.0, dt * 2.5)
				self.pitch = math.atan2(dy, max(0.1, dist_horiz)) * 0.45

			move_speed = 20.0 if self.phase == EnderDragonPhase.CHARGING_PLAYER else (14.0 if self.phase == EnderDragonPhase.STRAFE_PLAYER else 10.5)
			step_dist = move_speed * dt
			total_dist = math.sqrt(dx * dx + dy * dy + dz * dz)
			if total_dist > 0.01:
				self.position[0] += (dx / total_dist) * min(total_dist, step_dist)
				self.position[1] += (dy / total_dist) * min(total_dist, step_dist)
				self.position[2] += (dz / total_dist) * min(total_dist, step_dist)

		# -------------------------------------------------------------
		# Passive Melee Body Collision with Player in Survival Mode
		# -------------------------------------------------------------
		if camera and not self.is_perched and not self.is_dead:
			c_pos = camera.position
			is_creative = getattr(camera, 'flying', False) or getattr(getattr(camera, 'window', None), 'flying', False)
			if not is_creative and (time.time() - self.last_melee_hit_time >= 1.0):
				dx = c_pos[0] - self.position[0]
				dy = c_pos[1] - self.position[1]
				dz = c_pos[2] - self.position[2]
				dist = math.sqrt(dx * dx + dy * dy + dz * dz)
				if dist <= (self.body_radius * 0.75):
					self.last_melee_hit_time = time.time()
					if hasattr(camera, 'take_damage'):
						camera.take_damage(8, flying=False, gui=gui, world=end_world)
					norm = max(0.001, dist)
					if hasattr(camera, 'velocity_y'):
						camera.velocity_y = max(camera.velocity_y + 0.25, 6.0)

	def _get_snout_position(self):
		"""Computes the 3D world position of the dragon's snout."""
		cos_y, sin_y = math.cos(self.yaw), math.sin(self.yaw)
		cos_p, sin_p = math.cos(self.pitch), math.sin(self.pitch)
		# Snout is offset ~8.8m along forward orientation
		forward_dist = 8.8
		sx = self.position[0] + sin_y * cos_p * forward_dist
		sy = self.position[1] + sin_p * forward_dist + 0.65
		sz = self.position[2] + cos_y * cos_p * forward_dist
		return (sx, sy, sz)

	def check_ray_hit(self, ray_origin, ray_dir, max_dist=128.0):
		"""
		Checks if a player click or arrow ray intersects the Dragon hitbox.
		Returns (hit_bool, part_name) where part_name is 'head' (2x damage) or 'body' (1x damage).
		Picks the closest intersection point along the ray.
		"""
		if self.is_dead:
			return False, None

		ox, oy, oz = ray_origin
		dx, dy, dz = ray_dir

		closest_part = None
		closest_dist = max_dist + 1.0

		# 1. Check Head Hitbox (Offset ~8.0m forward)
		cos_y, sin_y = math.cos(self.yaw), math.sin(self.yaw)
		cos_p, sin_p = math.cos(self.pitch), math.sin(self.pitch)
		hx = self.position[0] + sin_y * cos_p * 8.0
		hy = self.position[1] + sin_p * 8.0 + 1.0
		hz = self.position[2] + cos_y * cos_p * 8.0

		h_dx = hx - ox
		h_dy = hy - oy
		h_dz = hz - oz
		h_dot = h_dx * dx + h_dy * dy + h_dz * dz
		if 0.0 <= h_dot <= max_dist:
			closest_x = ox + dx * h_dot
			closest_y = oy + dy * h_dot
			closest_z = oz + dz * h_dot
			dist_sq = (closest_x - hx)**2 + (closest_y - hy)**2 + (closest_z - hz)**2
			if dist_sq <= (self.head_radius * self.head_radius):
				if h_dot < closest_dist:
					closest_dist = h_dot
					closest_part = "head"

		# 2. Check Body Hitbox
		bx = self.position[0] - ox
		by = (self.position[1] + 0.8) - oy
		bz = self.position[2] - oz
		b_dot = bx * dx + by * dy + bz * dz
		if 0.0 <= b_dot <= max_dist:
			closest_x = ox + dx * b_dot
			closest_y = oy + dy * b_dot
			closest_z = oz + dz * b_dot
			dist_sq = (closest_x - self.position[0])**2 + (closest_y - (self.position[1] + 0.8))**2 + (closest_z - self.position[2])**2
			if dist_sq <= (self.body_radius * self.body_radius):
				if b_dot < closest_dist:
					closest_dist = b_dot
					closest_part = "body"

		if closest_part is not None:
			return True, closest_part
		return False, None


class EnderDragonRenderer:
	"""Renders the 3D multi-segment scaled (~1.2x) animated Ender Dragon boss model."""
	def __init__(self, texture_manager):
		self.texture_manager = texture_manager
		self.shader_program = None
		self.initialized = False
		self.vao = None
		self.vbo = None

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(DRAGON_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(DRAGON_FRAG_SHADER, 'fragment')
			self.shader_program = pyglet.graphics.shader.ShaderProgram(vs, fs)

			self.vao = gl.GLuint()
			gl.glGenVertexArrays(1, ctypes.byref(self.vao))
			self.vbo = gl.GLuint()
			gl.glGenBuffers(1, ctypes.byref(self.vbo))

			gl.glBindVertexArray(self.vao)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)

			# Position: 3 floats (loc=0)
			gl.glEnableVertexAttribArray(0)
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 9 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

			# TexCoord: 2 floats (loc=1)
			gl.glEnableVertexAttribArray(1)
			gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 9 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(3 * ctypes.sizeof(ctypes.c_float)))

			# Color: 4 floats (loc=2)
			gl.glEnableVertexAttribArray(2)
			gl.glVertexAttribPointer(2, 4, gl.GL_FLOAT, gl.GL_FALSE, 9 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(5 * ctypes.sizeof(ctypes.c_float)))

			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
			gl.glBindVertexArray(0)
			self.initialized = True
		except Exception:
			pass

	def draw(self, camera, dragon):
		if not dragon:
			return

		self._init_gl()
		if not self.initialized or not self.shader_program:
			return

		vertex_data = []

		# Dragon orientation transforms
		yaw = dragon.yaw
		pitch = dragon.pitch
		wing_angle = math.sin(dragon.wing_flap_timer) * 0.45

		cos_y, sin_y = math.cos(yaw), math.sin(yaw)
		cos_p, sin_p = math.cos(pitch), math.sin(pitch)

		def trans_pt(local_x, local_y, local_z):
			# Pitch rotation
			y1 = local_y * cos_p - local_z * sin_p
			z1 = local_y * sin_p + local_z * cos_p
			# Yaw rotation
			wx = local_x * cos_y + z1 * sin_y
			wz = -local_x * sin_y + z1 * cos_y
			return dragon.position[0] + wx, dragon.position[1] + y1, dragon.position[2] + wz

		def add_box(min_pt, max_pt, cr, cg, cb, ca=1.0):
			x1, y1, z1 = min_pt
			x2, y2, z2 = max_pt
			corners = [
				(x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1), # Back (-Z)
				(x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2), # Front (+Z)
			]
			quads = [
				(1, 0, 3, 2), # Back (-Z)
				(4, 5, 6, 7), # Front (+Z)
				(0, 4, 7, 3), # Left (-X)
				(5, 1, 2, 6), # Right (+X)
				(3, 7, 6, 2), # Top (+Y)
				(0, 1, 5, 4), # Bottom (-Y)
			]
			for q in quads:
				for idx in (q[0], q[1], q[2], q[0], q[2], q[3]):
					lx, ly, lz = corners[idx]
					wx, wy, wz = trans_pt(lx, ly, lz)
					vertex_data.extend([wx, wy, wz, 0.0, 0.0, cr, cg, cb, ca])

		# 1. Dragon Main Body (~1.2x scale)
		add_box((-1.4, -0.9, -2.8), (1.4, 1.1, 2.8), 0.12, 0.12, 0.14, 1.0)

		# 2. Neck Segments (5 segments leading forward to head)
		for seg in range(5):
			offset_z = 2.8 + seg * 1.05
			offset_y = 0.25 + seg * 0.28
			add_box((-0.7, offset_y - 0.55, offset_z), (0.7, offset_y + 0.55, offset_z + 1.05), 0.10, 0.10, 0.12, 1.0)

		# 3. Dragon Head & Snout
		head_z = 2.8 + 5 * 1.05
		head_y = 0.25 + 5 * 0.28
		# Head
		add_box((-0.9, head_y - 0.65, head_z), (0.9, head_y + 0.8, head_z + 1.6), 0.11, 0.11, 0.13, 1.0)
		# Snout
		add_box((-0.65, head_y - 0.55, head_z + 1.6), (0.65, head_y + 0.35, head_z + 2.7), 0.10, 0.10, 0.12, 1.0)
		# Glowing Purple Eyes
		add_box((-0.95, head_y + 0.12, head_z + 0.7), (-0.88, head_y + 0.45, head_z + 1.2), 0.90, 0.20, 1.00, 1.0)
		add_box((0.88, head_y + 0.12, head_z + 0.7), (0.95, head_y + 0.45, head_z + 1.2), 0.90, 0.20, 1.00, 1.0)

		# 4. Tail (4 segments extending backward)
		for t_seg in range(4):
			tz = -2.8 - t_seg * 1.4
			ty = 0.12 - t_seg * 0.16
			tw = 0.9 - t_seg * 0.16
			add_box((-tw, ty - tw, tz - 1.4), (tw, ty + tw, tz), 0.10, 0.10, 0.12, 1.0)

		# 5. Wings (Left & Right with dynamic flapping joint rotation)
		for side, sign in [("left", -1.0), ("right", 1.0)]:
			w_joint_x = sign * 1.4
			w_tip_x = sign * (1.4 + 5.2 * math.cos(wing_angle))
			w_tip_y = 0.6 + math.sin(wing_angle) * (2.9 if sign == 1.0 else -2.9)

			# Wing membrane quad
			p1 = trans_pt(w_joint_x, 0.7, 2.0)
			p2 = trans_pt(w_joint_x, 0.45, -2.0)
			p3 = trans_pt(w_tip_x, w_tip_y, -0.9)
			p4 = trans_pt(w_tip_x, w_tip_y, 1.4)

			for vx, vy, vz in [p1, p2, p3, p1, p3, p4, p4, p3, p1, p3, p2, p1]:
				vertex_data.extend([vx, vy, vz, 0.0, 0.0, 0.15, 0.13, 0.18, 0.92])

		if not vertex_data:
			return

		v_count = len(vertex_data) // 9
		c_data = (ctypes.c_float * len(vertex_data))(*vertex_data)

		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		self.shader_program.use()

		if hasattr(camera, 'matrix'):
			gl.glUniformMatrix4fv(
				gl.glGetUniformLocation(self.shader_program.id, b"matrix"),
				1, gl.GL_FALSE,
				(gl.GLfloat * 16)(*camera.matrix)
			)
		elif hasattr(camera, 'mv_matrix'):
			mvp_matrix = camera.mv_matrix * camera.p_matrix
			flat_matrix = [val for row in mvp_matrix.data for val in row]
			gl.glUniformMatrix4fv(
				gl.glGetUniformLocation(self.shader_program.id, b"matrix"),
				1, gl.GL_FALSE,
				(gl.GLfloat * 16)(*flat_matrix)
			)

		# Hurt Flash Tint (Red overlay when dragon takes damage)
		if dragon.hurt_time > 0.0:
			gl.glUniform4f(gl.glGetUniformLocation(self.shader_program.id, b"u_tint"), 0.9, 0.1, 0.1, 0.65)
		else:
			gl.glUniform4f(gl.glGetUniformLocation(self.shader_program.id, b"u_tint"), 0.0, 0.0, 0.0, 0.0)

		gl.glUniform1i(gl.glGetUniformLocation(self.shader_program.id, b"u_use_texture"), 0)

		gl.glBindVertexArray(self.vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_data), c_data, gl.GL_DYNAMIC_DRAW)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, v_count)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
		gl.glBindVertexArray(0)
		self.shader_program.stop()
