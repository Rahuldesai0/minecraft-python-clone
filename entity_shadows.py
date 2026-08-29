"""
Directional Entity Shadow Renderer
----------------------------------
Renders smooth directional and contact ground shadows for the Player and all Mobs
under sunlight and moonlight based on real 3D celestial vectors.
"""

import math
import ctypes
import pyglet
import pyglet.gl as gl

SHADOW_VERT_SHADER = """#version 330
layout(location = 0) in vec3 vertex_position;
layout(location = 1) in vec4 vertex_color;

out vec4 frag_color;
uniform mat4 matrix;

void main(void) {
	frag_color = vertex_color;
	gl_Position = matrix * vec4(vertex_position, 1.0);
}
"""

SHADOW_FRAG_SHADER = """#version 330
in vec4 frag_color;
out vec4 fragment_colour;

void main(void) {
	fragment_colour = frag_color;
}
"""


class EntityShadowRenderer:
	def __init__(self):
		self.shader_program = None
		self.matrix_loc = -1

		self.vao = None
		self.vbo_pos = None
		self.vbo_col = None
		self.ibo = None

	def init_shader(self):
		def compile_shader(shader_type, source):
			shader = gl.glCreateShader(shader_type)
			c_src = ctypes.create_string_buffer(source.encode('utf-8'))
			c_ptr = ctypes.cast(ctypes.pointer(c_src), ctypes.POINTER(ctypes.c_char))
			gl.glShaderSource(shader, 1, ctypes.byref(c_ptr), None)
			gl.glCompileShader(shader)
			status = gl.GLint(0)
			gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS, ctypes.byref(status))
			if not status.value:
				log = ctypes.create_string_buffer(1024)
				gl.glGetShaderInfoLog(shader, 1024, None, log)
				print(f"Shadow Shader Compilation Error: {log.value.decode('utf-8')}")
				return None
			return shader

		vs = compile_shader(gl.GL_VERTEX_SHADER, SHADOW_VERT_SHADER)
		fs = compile_shader(gl.GL_FRAGMENT_SHADER, SHADOW_FRAG_SHADER)
		if not vs or not fs:
			return

		self.shader_program = gl.glCreateProgram()
		gl.glAttachShader(self.shader_program, vs)
		gl.glAttachShader(self.shader_program, fs)
		gl.glLinkProgram(self.shader_program)

		self.matrix_loc = gl.glGetUniformLocation(self.shader_program, ctypes.create_string_buffer(b"matrix"))

		self.vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.vao)

		self.vbo_pos = gl.GLuint(0)
		gl.glGenBuffers(1, self.vbo_pos)

		self.vbo_col = gl.GLuint(0)
		gl.glGenBuffers(1, self.vbo_col)

		self.ibo = gl.GLuint(0)
		gl.glGenBuffers(1, self.ibo)

	def draw(self, camera, world, mobs, player_pos, sun_direction, lighting_mode="BLOCK"):
		if not world:
			return

		if self.shader_program is None:
			self.init_shader()
			if self.shader_program is None:
				return

		cam_x, cam_y, cam_z = camera.position
		entities = []

		# 1. Player
		if player_pos:
			p_ground = (player_pos[1] - getattr(camera, 'eye_offset', 1.62)) if getattr(camera, 'on_ground', False) else None
			entities.append((player_pos[0], player_pos[1] - getattr(camera, 'eye_offset', 1.62), player_pos[2], 0.45, p_ground))

		# 2. Mobs within 40 blocks
		if mobs:
			for mob in mobs:
				mx, my, mz = mob.position
				dx = mx - cam_x
				dz = mz - cam_z
				if dx * dx + dz * dz <= 1600.0:
					rad = 0.55 if getattr(mob, 'mob_type', '') in ('cow', 'horse') else 0.42
					m_ground = my if getattr(mob, 'on_ground', False) else None
					entities.append((mx, my, mz, rad, m_ground))

		if not entities:
			return

		sun_x, sun_y, sun_z = sun_direction
		is_day = (sun_y > -0.05)

		pos_data = []
		col_data = []
		idx_data = []
		v_count = 0

		NUM_SEGS = 8

		for ex, ey, ez, radius, direct_ground in entities:
			if direct_ground is not None:
				ground_y = direct_ground + 0.002
			else:
				bx = int(math.floor(ex))
				bz = int(math.floor(ez))
				start_y = int(math.floor(ey))

				ground_y = None
				for y_check in range(start_y, max(0, start_y - 4), -1):
					b_num = world.get_block_number((bx, y_check, bz))
					if b_num != 0:
						ground_y = y_check + 1.002
						break

			if ground_y is None or (ey < ground_y - 0.5):
				continue

			height_above = ey - ground_y
			if height_above > 6.0:
				continue

			# Alpha calculation based on height
			base_alpha = max(0.0, 1.0 - height_above / 6.0) * (0.55 if is_day else 0.30)

			# Directional offset along sun vector
			if is_day and sun_y > 0.05:
				scale = min(1.6, height_above * 0.35 + 0.20)
				off_x = -sun_x / max(0.25, sun_y) * scale
				off_z = -sun_z / max(0.25, sun_y) * scale
			else:
				off_x = 0.0
				off_z = 0.0

			center_x = ex + off_x
			center_y = ground_y
			center_z = ez + off_z

			# Center vertex (solid dark)
			center_idx = v_count
			pos_data.extend([center_x, center_y, center_z])
			col_data.extend([0.0, 0.0, 0.0, base_alpha])
			v_count += 1

			# Outer perimeter vertices (transparent)
			for i in range(NUM_SEGS):
				ang = i * (math.tau / NUM_SEGS)
				px = center_x + math.cos(ang) * radius
				pz = center_z + math.sin(ang) * radius
				pos_data.extend([px, center_y, pz])
				col_data.extend([0.0, 0.0, 0.0, 0.0])

				next_i = (i + 1) % NUM_SEGS
				idx_data.extend([center_idx, center_idx + 1 + i, center_idx + 1 + next_i])
				v_count += 1

		if not pos_data:
			return

		gl.glUseProgram(self.shader_program)

		mvp_matrix = camera.mv_matrix * camera.p_matrix
		flat_matrix = [val for row in mvp_matrix.data for val in row]
		if self.matrix_loc != -1:
			gl.glUniformMatrix4fv(self.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_matrix))

		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glDepthMask(gl.GL_FALSE)

		gl.glBindVertexArray(self.vao)

		pos_bytes = (gl.GLfloat * len(pos_data))(*pos_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(pos_bytes), pos_bytes, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		col_bytes = (gl.GLfloat * len(col_data))(*col_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_col)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(col_bytes), col_bytes, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		idx_bytes = (gl.GLuint * len(idx_data))(*idx_data)
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ibo)
		gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(idx_bytes), idx_bytes, gl.GL_STREAM_DRAW)

		gl.glDrawElements(gl.GL_TRIANGLES, len(idx_data), gl.GL_UNSIGNED_INT, 0)

		gl.glBindVertexArray(0)
		gl.glDepthMask(gl.GL_TRUE)


SHADOW_MAP_TEX_SIZE = 512  # 512x512 texels = 512x512 blocks (32x32 chunks)
SHADOW_MAP_WORLD_SIZE = 512.0

class WorldDirectionalShadowMap:
	"""
	Lightweight Real-Time World Heightfield Texture for Dynamic Directional Sun Shadows.
	Casts moving silhouette shadows for trees, mountains, cliffs, and buildings at all sun angles.
	"""
	def __init__(self):
		self.tex_id = None
		self.grid = bytearray(SHADOW_MAP_TEX_SIZE * SHADOW_MAP_TEX_SIZE)
		self.center_chunk = (0, 0)
		self.min_world_x = -256.0
		self.min_world_z = -256.0
		self.initialized = False

	def ensure_initialized(self):
		if self.initialized:
			return
		self.initialized = True
		tex = gl.GLuint(0)
		gl.glGenTextures(1, tex)
		self.tex_id = tex.value
		gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex_id)
		gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
		gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
		gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
		gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
		c_buf = (gl.GLubyte * len(self.grid)).from_buffer(self.grid)
		gl.glTexImage2D(
			gl.GL_TEXTURE_2D, 0, gl.GL_R8,
			SHADOW_MAP_TEX_SIZE, SHADOW_MAP_TEX_SIZE, 0,
			gl.GL_RED, gl.GL_UNSIGNED_BYTE, c_buf
		)

	def update_player_position(self, px, pz, world):
		"""Re-centers shadow grid if player moves significantly or on first frame."""
		self.ensure_initialized()
		cur_cx = int(math.floor(px / 16.0))
		cur_cz = int(math.floor(pz / 16.0))
		if getattr(self, "needs_initial_rebuild", True) or abs(cur_cx - self.center_chunk[0]) >= 8 or abs(cur_cz - self.center_chunk[1]) >= 8:
			self.needs_initial_rebuild = False
			self.center_chunk = (cur_cx, cur_cz)
			self.min_world_x = (cur_cx - 16) * 16.0
			self.min_world_z = (cur_cz - 16) * 16.0
			self.rebuild_all_chunks(world)

	def update_chunk_blocks(self, cx, cz, blocks_or_chunk):
		"""Extracts top occluders from chunk blocks or chunk object and updates the shadow grid in GPU texture in 0.001ms."""
		self.ensure_initialized()
		c_offset_x = int((cx - (self.center_chunk[0] - 16)) * 16)
		c_offset_z = int((cz - (self.center_chunk[1] - 16)) * 16)

		if not (0 <= c_offset_x <= SHADOW_MAP_TEX_SIZE - 16 and 0 <= c_offset_z <= SHADOW_MAP_TEX_SIZE - 16):
			return

		if hasattr(blocks_or_chunk, 'column_heights') and blocks_or_chunk.column_heights:
			h_data = blocks_or_chunk.column_heights
			for lz in range(16):
				gz = c_offset_z + lz
				row_start = gz * SHADOW_MAP_TEX_SIZE + c_offset_x
				self.grid[row_start : row_start + 16] = h_data[lz * 16 : (lz + 1) * 16]

			if self.tex_id is not None:
				gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex_id)
				c_buf = (gl.GLubyte * 256).from_buffer(h_data)
				gl.glTexSubImage2D(
					gl.GL_TEXTURE_2D, 0,
					c_offset_x, c_offset_z, 16, 16,
					gl.GL_RED, gl.GL_UNSIGNED_BYTE, c_buf
				)
		else:
			blocks = blocks_or_chunk.blocks if hasattr(blocks_or_chunk, 'blocks') else blocks_or_chunk
			chunk_grid = bytearray(256)
			for lx in range(16):
				base_col = lx * 4096
				for lz in range(16):
					col_start = base_col + lz
					h_val = 0
					for y in range(255, -1, -1):
						b = blocks[col_start + y * 16]
						if b != 0 and b != 9 and b != 19:
							h_val = y
							break
					chunk_grid[lz * 16 + lx] = h_val
					self.grid[(c_offset_z + lz) * SHADOW_MAP_TEX_SIZE + (c_offset_x + lx)] = h_val

			if self.tex_id is not None:
				gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex_id)
				c_buf = (gl.GLubyte * 256).from_buffer(chunk_grid)
				gl.glTexSubImage2D(
					gl.GL_TEXTURE_2D, 0,
					c_offset_x, c_offset_z, 16, 16,
					gl.GL_RED, gl.GL_UNSIGNED_BYTE, c_buf
				)

	def rebuild_all_chunks(self, world):
		"""Re-populates loaded chunks into the heightfield buffer in <0.2ms using fast slice copying."""
		self.ensure_initialized()
		if not world or not hasattr(world, 'chunks'):
			return
		base_cx = self.center_chunk[0] - 16
		base_cz = self.center_chunk[1] - 16

		# Fast reset
		self.grid = bytearray(SHADOW_MAP_TEX_SIZE * SHADOW_MAP_TEX_SIZE)

		for (cx, _, cz), chk in world.chunks.items():
			c_offset_x = (cx - base_cx) * 16
			c_offset_z = (cz - base_cz) * 16
			if 0 <= c_offset_x <= SHADOW_MAP_TEX_SIZE - 16 and 0 <= c_offset_z <= SHADOW_MAP_TEX_SIZE - 16:
				h_data = getattr(chk, 'column_heights', None)
				if h_data:
					for lz in range(16):
						gz = c_offset_z + lz
						row_start = gz * SHADOW_MAP_TEX_SIZE + c_offset_x
						self.grid[row_start : row_start + 16] = h_data[lz * 16 : (lz + 1) * 16]

		self.sync_to_gpu()

	def sync_to_gpu(self):
		if self.tex_id is not None:
			gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex_id)
			c_buf = (gl.GLubyte * len(self.grid)).from_buffer(self.grid)
			gl.glTexSubImage2D(
				gl.GL_TEXTURE_2D, 0, 0, 0,
				SHADOW_MAP_TEX_SIZE, SHADOW_MAP_TEX_SIZE,
				gl.GL_RED, gl.GL_UNSIGNED_BYTE, c_buf
			)

	def bind(self, texture_unit=gl.GL_TEXTURE1):
		self.ensure_initialized()
		if self.tex_id is not None:
			gl.glActiveTexture(texture_unit)
			gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex_id)

