"""
Minecraft Java Edition Arrow Entity, Physics Simulation & OpenGL 3.3 Core Profile 3D Renderer
----------------------------------------------------------------------------------------------
Implements authentic Minecraft Java Edition (1.16 - 1.20) projectile physics:
- 0.05 blocks/tick^2 gravity
- 0.99 air drag (0.60 water drag)
- Speed-based damage formula: ceil(speed * 2.0) + [random(0..floor(dmg/2)+1) if critical]
- Swept segment raycasting against voxels and entity AABBs
- Block face embedding and player pickup collision
- Modern OpenGL 3.3 Core Profile VAO/VBO rendering with 3D shaft, fletching fins, arrowhead, and sparkle particles
"""

import math
import random
import ctypes
import pyglet
import pyglet.gl as gl
import block_state


ARROW_VERT_SHADER = """
#version 330
layout(location = 0) in vec3 vertex_position;
layout(location = 1) in vec4 vertex_color;

out vec4 interpolated_color;

uniform mat4 matrix;

void main(void) {
	interpolated_color = vertex_color;
	gl_Position = matrix * vec4(vertex_position, 1.0);
}
"""

ARROW_FRAG_SHADER = """
#version 330
in vec4 interpolated_color;
out vec4 fragment_colour;

void main(void) {
	if (interpolated_color.a < 0.05) discard;
	fragment_colour = interpolated_color;
}
"""


class ArrowEntity:
	def __init__(self, position, velocity, is_critical=False, shooter=None, damage_multiplier=1.0):
		self.position = list(position)      # [x, y, z] in world coordinates
		self.velocity = list(velocity)      # [vx, vy, vz] in blocks/tick (1 tick = 0.05s)
		self.is_critical = is_critical
		self.shooter = shooter
		self.damage_multiplier = float(damage_multiplier)
		self.in_ground = False
		self.embedded_block = None          # (bx, by, bz)
		self.ticks_alive = 0
		self.in_ground_ticks = 0
		self.despawn = False
		self.pickup_allowed = (shooter == "player")  # Skeleton arrows cannot be picked up by player
		self.trail_particles = []           # [[x, y, z, life], ...]

		# Orientation angles (in degrees)
		self.yaw = 0.0
		self.pitch = 0.0
		self.update_rotation()

	def update_rotation(self):
		vx, vy, vz = self.velocity
		horiz_speed = math.sqrt(vx * vx + vz * vz)
		if horiz_speed > 0.0001 or abs(vy) > 0.0001:
			self.pitch = math.degrees(math.atan2(vy, max(0.0001, horiz_speed)))
			self.yaw = math.degrees(math.atan2(vx, vz))

	def update(self, dt, world, mob_manager=None, camera=None, gui=None):
		dt_ticks = dt * 20.0

		# 1. Embedded in ground behavior
		if self.in_ground:
			self.in_ground_ticks += dt_ticks
			# Despawn embedded arrows after 2 minutes (2400 ticks = 120 seconds)
			if self.in_ground_ticks >= 2400:
				self.despawn = True
				return

			if self.embedded_block:
				b_num = world.get_block_number(self.embedded_block)
				if b_num == 0:
					self.in_ground = False
					self.embedded_block = None
					self.velocity = [0.0, -0.05, 0.0]

			# Player Pickup Check (within 1.2 blocks of arrow, only for player-shot arrows)
			if self.pickup_allowed and camera:
				px, py, pz = camera.position
				dist_sq = (self.position[0] - px)**2 + (self.position[1] - (py - 0.8))**2 + (self.position[2] - pz)**2
				if dist_sq <= 1.5 * 1.5:
					if gui:
						added = gui.add_item_to_inventory(158, 1)  # 158 = Arrow
						if added > 0:
							self.despawn = True
							return
			return

		# 2. In-Flight Physics & Continuous Swept Collision
		self.ticks_alive += dt_ticks
		if self.ticks_alive >= 2400:
			self.despawn = True
			return

		step_vx = self.velocity[0] * dt_ticks
		step_vy = self.velocity[1] * dt_ticks
		step_vz = self.velocity[2] * dt_ticks
		step_dist = math.sqrt(step_vx * step_vx + step_vy * step_vy + step_vz * step_vz)

		# Check Mob Collisions along segment
		hit_mob = None
		min_mob_dist = float('inf')

		if mob_manager and hasattr(mob_manager, "mobs"):
			for mob in mob_manager.mobs:
				if mob.is_dead:
					continue
				# Ignore the mob entity that fired this arrow
				if mob is self.shooter or getattr(mob, 'entity_id', -1) == getattr(self.shooter, 'entity_id', -2):
					continue
				if (self.shooter == "skeleton" or getattr(self.shooter, 'mob_type', '') == 'skeleton') and mob.mob_type == "skeleton" and getattr(self, "life_ticks", 0) < 10:
					continue
				mx, my, mz = mob.position
				half_w = (mob.width / 2.0) + 0.3
				h = mob.height + 0.3
				box = (mx - half_w, mx + half_w, my, my + h, mz - half_w, mz + half_w)
				
				t = self._ray_intersect_box(self.position, (step_vx, step_vy, step_vz), box)
				if t is not None and 0.0 <= t <= 1.0:
					if t < min_mob_dist:
						min_mob_dist = t
						hit_mob = mob

		# Check Player Collision along segment if arrow was fired by a hostile mob
		hit_player = False
		min_player_dist = float('inf')
		if self.shooter != "player" and camera and not getattr(camera, 'flying', False) and getattr(camera, 'gamemode', 'survival') != 'creative':
			px, py, pz = camera.position
			half_w = 0.4
			player_box = (px - half_w, px + half_w, py - 1.65, py + 0.2, pz - half_w, pz + half_w)
			t_p = self._ray_intersect_box(self.position, (step_vx, step_vy, step_vz), player_box)
			if t_p is not None and 0.0 <= t_p <= 1.0:
				min_player_dist = t_p
				hit_player = True

		# Check Block Collisions along segment
		hit_block_pos = None
		min_block_dist = float('inf')

		num_samples = max(2, int(math.ceil(step_dist * 4.0)))
		for i in range(1, num_samples + 1):
			frac = i / float(num_samples)
			sample_x = self.position[0] + step_vx * frac
			sample_y = self.position[1] + step_vy * frac
			sample_z = self.position[2] + step_vz * frac
			
			bx = int(math.floor(sample_x))
			by = int(math.floor(sample_y))
			bz = int(math.floor(sample_z))
			
			b_num = world.get_block_number((bx, by, bz))
			if b_num != 0 and b_num not in block_state.PASSABLE_BLOCKS:
				hit_block_pos = (bx, by, bz)
				min_block_dist = frac
				break

		# Check End Crystal Collision
		crystal_mgr = getattr(world, "end_crystal_manager", None)
		if crystal_mgr:
			spd = math.sqrt(self.velocity[0]**2 + self.velocity[1]**2 + self.velocity[2]**2)
			if spd > 0.001:
				step_dist = spd * dt
				norm_dir = (self.velocity[0] / spd, self.velocity[1] / spd, self.velocity[2] / spd)
				if crystal_mgr.check_attack_hit(
					self.position, norm_dir, max_dist=step_dist * 1.5, damage=1,
					dragon=getattr(world, "ender_dragon", None),
					mob_manager=mob_manager or getattr(world, "mob_manager", None),
					camera=camera, gui=gui,
					tnt_manager=getattr(world, "tnt_manager", None),
					item_drop_manager=getattr(world, "item_drop_manager", None)
				):
					self.despawn = True
					return

		# Check Ender Dragon Collision
		dragon = getattr(world, "ender_dragon", None)
		if dragon and not getattr(dragon, "is_dead", False):
			spd = math.sqrt(self.velocity[0]**2 + self.velocity[1]**2 + self.velocity[2]**2)
			if spd > 0.001:
				step_dist = spd * dt
				norm_dir = (self.velocity[0] / spd, self.velocity[1] / spd, self.velocity[2] / spd)
				hit, part = dragon.check_ray_hit(self.position, norm_dir, max_dist=step_dist * 1.5)
				if hit:
					if getattr(dragon, "is_arrow_immune", False):
						# Deflect arrow while perched (bounce off without damaging)
						self.velocity[0] = -self.velocity[0] * 0.4 + random.uniform(-2.0, 2.0)
						self.velocity[1] = random.uniform(3.0, 6.5)
						self.velocity[2] = -self.velocity[2] * 0.4 + random.uniform(-2.0, 2.0)
						return
					else:
						dmg = int(math.ceil(spd * 2.0 * getattr(self, "damage_multiplier", 1.0)))
						dragon.take_damage(dmg, part=part, attacker_pos=self.position)
						self.despawn = True
						return

		# Resolve Closest Collision (Player vs Mob vs Block)
		if hit_player and min_player_dist <= min_block_dist and (not hit_mob or min_player_dist <= min_mob_dist):
			impact_speed = math.sqrt(self.velocity[0]**2 + self.velocity[1]**2 + self.velocity[2]**2)
			base_damage = int(math.ceil(impact_speed * 2.0))
			total_damage = base_damage
			camera.take_damage(total_damage, flying=getattr(camera, 'flying', False), gui=gui, world=world)
			self.despawn = True
			return

		elif hit_mob and min_mob_dist <= min_block_dist:
			impact_speed = math.sqrt(self.velocity[0]**2 + self.velocity[1]**2 + self.velocity[2]**2)
			base_damage = int(math.ceil(impact_speed * 2.0))
			if self.is_critical:
				crit_extra = random.randint(0, (base_damage // 2) + 1)
				total_damage = base_damage + crit_extra
			else:
				total_damage = base_damage

			mult = getattr(self, "damage_multiplier", 1.0)
			if mult > 1.0:
				total_damage = int(math.ceil(total_damage * mult))

			hit_mob.take_damage(total_damage, attacker_pos=self.position)
			
			norm_spd = max(0.001, impact_speed)
			hit_mob.velocity[0] += (self.velocity[0] / norm_spd) * 0.45
			hit_mob.velocity[1] += 0.22
			hit_mob.velocity[2] += (self.velocity[2] / norm_spd) * 0.45
			
			self.despawn = True
			return

		elif hit_block_pos:
			b_hit = world.get_block_number(hit_block_pos)
			if b_hit == 25 and (getattr(self, "fire_timer", 0.0) > 0 or getattr(self, "is_critical", False)):
				world.set_block(hit_block_pos, 0)
				if hasattr(world, "tnt_manager") and world.tnt_manager:
					world.tnt_manager.spawn_primed_tnt(
						(hit_block_pos[0] + 0.5, hit_block_pos[1], hit_block_pos[2] + 0.5),
						fuse_ticks=80
					)
				self.despawn = True
				return

			self.position[0] += step_vx * min_block_dist
			self.position[1] += step_vy * min_block_dist
			self.position[2] += step_vz * min_block_dist
			self.in_ground = True
			self.embedded_block = hit_block_pos
			self.velocity = [0.0, 0.0, 0.0]
			return

		# 3. Step Position & Apply Physics Drag / Gravity
		self.position[0] += step_vx
		self.position[1] += step_vy
		self.position[2] += step_vz

		if self.is_critical:
			self.trail_particles.append([self.position[0], self.position[1], self.position[2], 0.35])

		cur_b = world.get_block_number((int(math.floor(self.position[0])), int(math.floor(self.position[1])), int(math.floor(self.position[2]))))
		drag = 0.60 if cur_b in (9, 19, 15, 20) else 0.99

		self.velocity[0] *= (drag ** dt_ticks)
		self.velocity[1] *= (drag ** dt_ticks)
		self.velocity[2] *= (drag ** dt_ticks)

		self.velocity[1] -= 0.05 * dt_ticks
		self.update_rotation()

		for p in self.trail_particles:
			p[3] -= dt
		self.trail_particles = [p for p in self.trail_particles if p[3] > 0]

	def _ray_intersect_box(self, origin, dir_vec, box):
		min_x, max_x, min_y, max_y, min_z, max_z = box
		ox, oy, oz = origin
		dx, dy, dz = dir_vec

		tmin = -float('inf')
		tmax = float('inf')

		for o, d, bmin, bmax in [(ox, dx, min_x, max_x), (oy, dy, min_y, max_y), (oz, dz, min_z, max_z)]:
			if abs(d) < 1e-6:
				if o < bmin or o > bmax:
					return None
			else:
				t1 = (bmin - o) / d
				t2 = (bmax - o) / d
				if t1 > t2: t1, t2 = t2, t1
				tmin = max(tmin, t1)
				tmax = min(tmax, t2)
				if tmin > tmax:
					return None

		return tmin if tmin >= 0 else (tmax if tmax >= 0 else None)


class ArrowManager:
	def __init__(self, world):
		self.world = world
		self.arrows = []
		self.shader_program = None
		self.matrix_loc = -1
		self.vao = None
		self.vbo_pos = None
		self.vbo_col = None

	def ensure_initialized(self):
		if self.shader_program is None:
			self.init_shader()

	def init_shader(self):
		try:
			v_shader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
			v_src = ctypes.create_string_buffer(ARROW_VERT_SHADER.encode('utf-8'))
			v_len = ctypes.c_int(len(v_src.value) + 1)
			v_ptr = ctypes.cast(ctypes.pointer(ctypes.pointer(v_src)), ctypes.POINTER(ctypes.POINTER(ctypes.c_char)))
			gl.glShaderSource(v_shader, 1, v_ptr, ctypes.byref(v_len))
			gl.glCompileShader(v_shader)

			f_shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
			f_src = ctypes.create_string_buffer(ARROW_FRAG_SHADER.encode('utf-8'))
			f_len = ctypes.c_int(len(f_src.value) + 1)
			f_ptr = ctypes.cast(ctypes.pointer(ctypes.pointer(f_src)), ctypes.POINTER(ctypes.POINTER(ctypes.c_char)))
			gl.glShaderSource(f_shader, 1, f_ptr, ctypes.byref(f_len))
			gl.glCompileShader(f_shader)

			prog = gl.glCreateProgram()
			gl.glAttachShader(prog, v_shader)
			gl.glAttachShader(prog, f_shader)
			gl.glLinkProgram(prog)

			self.shader_program = prog
			self.matrix_loc = gl.glGetUniformLocation(prog, ctypes.create_string_buffer(b"matrix"))

			vao = gl.GLuint(0)
			gl.glGenVertexArrays(1, vao)
			self.vao = vao.value

			vbos = (gl.GLuint * 2)()
			gl.glGenBuffers(2, vbos)
			self.vbo_pos = vbos[0]
			self.vbo_col = vbos[1]
		except Exception as e:
			print(f"Error initializing Arrow shader: {e}")

	def shoot_arrow(self, camera, power, is_critical=False, damage_multiplier=1.0):
		px, py, pz = camera.position
		spawn_pos = (px, py - 0.1, pz)

		yaw_rad, pitch_rad = camera.rotation
		dir_x = math.cos(yaw_rad) * math.cos(pitch_rad)
		dir_y = math.sin(pitch_rad)
		dir_z = math.sin(yaw_rad) * math.cos(pitch_rad)

		inaccuracy = 1.0
		dir_x += random.gauss(0, 1) * 0.0075 * inaccuracy
		dir_y += random.gauss(0, 1) * 0.0075 * inaccuracy
		dir_z += random.gauss(0, 1) * 0.0075 * inaccuracy

		mag = math.sqrt(dir_x * dir_x + dir_y * dir_y + dir_z * dir_z)
		if mag > 0:
			dir_x /= mag
			dir_y /= mag
			dir_z /= mag

		speed = power * 3.0
		vel = (dir_x * speed, dir_y * speed, dir_z * speed)

		arrow = ArrowEntity(spawn_pos, vel, is_critical=is_critical, shooter="player", damage_multiplier=damage_multiplier)
		self.arrows.append(arrow)
		return arrow

	def spawn_arrow(self, position, velocity, is_critical=False, shooter="skeleton"):
		"""Spawns an arrow projectile from hostile mobs (e.g. Skeletons)."""
		arrow = ArrowEntity(position, velocity, is_critical=is_critical, shooter=shooter)
		self.arrows.append(arrow)
		return arrow

	def update(self, dt, world, mob_manager, camera, gui):
		for arrow in self.arrows:
			arrow.update(dt, world, mob_manager, camera, gui)
		self.arrows = [a for a in self.arrows if not a.despawn]

	def draw(self, camera):
		"""Renders all flying and embedded arrows and sparkle trails using modern OpenGL 3.3 Core Profile."""
		if not self.arrows:
			return

		self.ensure_initialized()
		if not self.shader_program:
			return

		pos_data = []
		col_data = []

		def add_quad(p1, p2, p3, p4, color):
			corners = [p1, p2, p3, p4]
			for idx in (0, 1, 2, 0, 2, 3):
				pos_data.extend(corners[idx])
				col_data.extend(color)

		for arrow in self.arrows:
			ax, ay, az = arrow.position
			pitch_r = math.radians(arrow.pitch)
			yaw_r = math.radians(arrow.yaw)

			# Compute forward direction vector
			dx = math.cos(pitch_r) * math.sin(yaw_r)
			dy = math.sin(pitch_r)
			dz = math.cos(pitch_r) * math.cos(yaw_r)

			# Compute right and up orthogonal basis vectors
			rx = -dz
			ry = 0.0
			rz = dx
			r_mag = math.sqrt(rx * rx + rz * rz)
			if r_mag > 0.0001:
				rx /= r_mag
				rz /= r_mag
			else:
				rx, rz = 1.0, 0.0

			# Up = Forward x Right
			ux = dy * rz - dz * ry
			uy = dz * rx - dx * rz
			uz = dx * ry - dy * rx
			u_mag = math.sqrt(ux * ux + uy * uy + uz * uz)
			if u_mag > 0.0001:
				ux /= u_mag; uy /= u_mag; uz /= u_mag
			else:
				ux, uy, uz = 0.0, 1.0, 0.0

			# Tail and Tip positions (Length = 0.7m)
			tail_x, tail_y, tail_z = ax - dx * 0.35, ay - dy * 0.35, az - dz * 0.35
			tip_x, tip_y, tip_z = ax + dx * 0.35, ay + dy * 0.35, az + dz * 0.35

			# 1. Wooden Shaft (Brown)
			sh_w = 0.02
			sh_col = (0.55, 0.35, 0.15, 1.0)
			p1 = (tail_x + rx * sh_w, tail_y + ry * sh_w, tail_z + rz * sh_w)
			p2 = (tail_x - rx * sh_w, tail_y - ry * sh_w, tail_z - rz * sh_w)
			p3 = (tip_x - rx * sh_w, tip_y - ry * sh_w, tip_z - rz * sh_w)
			p4 = (tip_x + rx * sh_w, tip_y + ry * sh_w, tip_z + rz * sh_w)
			add_quad(p1, p2, p3, p4, sh_col)

			p1_u = (tail_x + ux * sh_w, tail_y + uy * sh_w, tail_z + uz * sh_w)
			p2_u = (tail_x - ux * sh_w, tail_y - uy * sh_w, tail_z - uz * sh_w)
			p3_u = (tip_x - ux * sh_w, tip_y - uy * sh_w, tip_z - uz * sh_w)
			p4_u = (tip_x + ux * sh_w, tip_y + uy * sh_w, tip_z + uz * sh_w)
			add_quad(p1_u, p2_u, p3_u, p4_u, sh_col)

			# 2. Arrowhead (Iron Grey)
			head_col = (0.85, 0.85, 0.90, 1.0)
			head_base_x = tip_x - dx * 0.10
			head_base_y = tip_y - dy * 0.10
			head_base_z = tip_z - dz * 0.10
			hw = 0.05
			h1 = (head_base_x + rx * hw, head_base_y + ry * hw, head_base_z + rz * hw)
			h2 = (head_base_x - rx * hw, head_base_y - ry * hw, head_base_z - rz * hw)
			h3 = (tip_x + dx * 0.05, tip_y + dy * 0.05, tip_z + dz * 0.05)
			add_quad(h1, h2, h3, h1, head_col)

			h1_u = (head_base_x + ux * hw, head_base_y + uy * hw, head_base_z + uz * hw)
			h2_u = (head_base_x - ux * hw, head_base_y - uy * hw, head_base_z - uz * hw)
			add_quad(h1_u, h2_u, h3, h1_u, head_col)

			# 3. Feather Fletching Fins (White)
			fin_col = (0.95, 0.95, 0.98, 0.95)
			f_len = 0.15
			f_w = 0.06
			f_tail_x = tail_x + dx * 0.02
			f_tail_y = tail_y + dy * 0.02
			f_tail_z = tail_z + dz * 0.02
			f_front_x = f_tail_x + dx * f_len
			f_front_y = f_tail_y + dy * f_len
			f_front_z = f_tail_z + dz * f_len

			# Horizontal fin
			f1 = (f_tail_x + rx * f_w, f_tail_y + ry * f_w, f_tail_z + rz * f_w)
			f2 = (f_tail_x - rx * f_w, f_tail_y - ry * f_w, f_tail_z - rz * f_w)
			f3 = (f_front_x - rx * f_w * 0.4, f_front_y - ry * f_w * 0.4, f_front_z - rz * f_w * 0.4)
			f4 = (f_front_x + rx * f_w * 0.4, f_front_y + ry * f_w * 0.4, f_front_z + rz * f_w * 0.4)
			add_quad(f1, f2, f3, f4, fin_col)

			# Vertical fin
			f1_v = (f_tail_x + ux * f_w, f_tail_y + uy * f_w, f_tail_z + uz * f_w)
			f2_v = (f_tail_x - ux * f_w, f_tail_y - uy * f_w, f_tail_z - uz * f_w)
			f3_v = (f_front_x - ux * f_w * 0.4, f_front_y - uy * f_w * 0.4, f_front_z - uz * f_w * 0.4)
			f4_v = (f_front_x + ux * f_w * 0.4, f_front_y + uy * f_w * 0.4, f_front_z + uz * f_w * 0.4)
			add_quad(f1_v, f2_v, f3_v, f4_v, fin_col)

			# 4. Critical Sparkle Particles
			if arrow.is_critical and arrow.trail_particles:
				for px, py, pz, life in arrow.trail_particles:
					alpha = min(1.0, life / 0.35)
					p_col = (1.0, 0.9, 0.2, alpha)
					pw = 0.03
					p_a = (px - pw, py, pz)
					p_b = (px + pw, py, pz)
					p_c = (px, py + pw, pz)
					p_d = (px, py - pw, pz)
					add_quad(p_a, p_b, p_c, p_d, p_col)

		if not pos_data:
			return

		# Render mesh with ArrowShader
		gl.glUseProgram(self.shader_program)

		mvp_matrix = camera.mv_matrix * camera.p_matrix
		flat_matrix = [val for row in mvp_matrix.data for val in row]
		if self.matrix_loc != -1:
			gl.glUniformMatrix4fv(self.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_matrix))

		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glDisable(gl.GL_CULL_FACE)

		vertex_count = len(pos_data) // 3
		c_pos_data = (gl.GLfloat * len(pos_data))(*pos_data)
		c_col_data = (gl.GLfloat * len(col_data))(*col_data)

		gl.glBindVertexArray(self.vao)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(pos_data) * 4, c_pos_data, gl.GL_DYNAMIC_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_col)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(col_data) * 4, c_col_data, gl.GL_DYNAMIC_DRAW)
		gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertex_count)

		gl.glBindVertexArray(0)
		gl.glEnable(gl.GL_CULL_FACE)
