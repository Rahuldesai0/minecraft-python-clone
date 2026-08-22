"""
Minecraft Java Edition Mob Models & Pixel Atlas System (Pig & Cow)
------------------------------------------------------------------
Implements exact 3D models, pivots, hierarchy, pixel-space UV mapping,
and quadruped limb animations for Minecraft Pig and Cow passive mobs.

Scale: 1 block = 1.0 unit = 16 model pixels (scale factor = 0.0625).
"""

import os
import math
import ctypes
import pyglet
import pyglet.gl as gl


def transform_point(x, y, z, rx=0.0, ry=0.0, rz=0.0, pivot=(0.0, 0.0, 0.0)):
	"""Applies 3D rotation (rx, ry, rz in radians) around pivot point (px, py, pz)."""
	px, py, pz = pivot
	x -= px; y -= py; z -= pz

	# Pitch (X-axis)
	if rx != 0.0:
		c, s = math.cos(rx), math.sin(rx)
		y, z = y * c - z * s, y * s + z * c

	# Yaw (Y-axis)
	if ry != 0.0:
		c, s = math.cos(ry), math.sin(ry)
		x, z = x * c + z * s, -x * s + z * c

	# Roll (Z-axis)
	if rz != 0.0:
		c, s = math.cos(rz), math.sin(rz)
		x, y = x * c - y * s, x * s + y * c

	return x + px, y + py, z + pz


def get_face_uv_rect(x0, y0, x1, y1, tex_w=64, tex_h=32, mirror=False):
	"""
	Converts 2D image pixel rectangle (x0, y0) -> (x1, y1) into 4 normalized OpenGL UV corners.
	Image origin: Top-Left (0, 0).
	OpenGL UV origin: Bottom-Left (0.0, 0.0).
	"""
	if mirror:
		u0 = x1 / float(tex_w)
		u1 = x0 / float(tex_w)
	else:
		u0 = x0 / float(tex_w)
		u1 = x1 / float(tex_w)

	v0 = (tex_h - y1) / float(tex_h) # Bottom edge in OpenGL V
	v1 = (tex_h - y0) / float(tex_h) # Top edge in OpenGL V

	return [
		(u0, v1), # Top-Left
		(u1, v1), # Top-Right
		(u1, v0), # Bottom-Right
		(u0, v0)  # Bottom-Left
	]


def build_cuboid_uv_atlas(x, y, w, h, d, tex_w=64, tex_h=32, mirror=False):
	"""
	Computes the 6 canonical face UV rectangles for a cuboid of size (w, h, d) at origin (x, y).
	Faces: top, bottom, right, left, front, back.
	"""
	return {
		"top":    get_face_uv_rect(x + d, y, x + d + w, y + d, tex_w, tex_h, mirror),
		"bottom": get_face_uv_rect(x + d + w, y, x + 2 * d + w, y + d, tex_w, tex_h, mirror),
		"right":  get_face_uv_rect(x, y + d, x + d, y + d + h, tex_w, tex_h, mirror),
		"front":  get_face_uv_rect(x + d, y + d, x + d + w, y + d + h, tex_w, tex_h, mirror),
		"left":   get_face_uv_rect(x + d + w, y + d, x + 2 * d + w, y + d + h, tex_w, tex_h, mirror),
		"back":   get_face_uv_rect(x + 2 * d + w, y + d, x + 2 * d + 2 * w, y + d + h, tex_w, tex_h, mirror)
	}


MOB_VERT_SHADER = """
#version 330
layout(location = 0) in vec3 vertex_position;
layout(location = 1) in vec2 tex_coords;
layout(location = 2) in float shading_value;

out vec2 interpolated_tex_coords;
out float interpolated_shading_value;

uniform mat4 matrix;

void main(void) {
	interpolated_tex_coords = tex_coords;
	interpolated_shading_value = shading_value;
	gl_Position = matrix * vec4(vertex_position, 1.0);
}
"""

MOB_FRAG_SHADER = """
#version 330
out vec4 fragment_colour;

uniform sampler2D mob_sampler;
uniform vec4 hurt_color;

in vec2 interpolated_tex_coords;
in float interpolated_shading_value;

void main(void) {
	vec4 col = texture(mob_sampler, interpolated_tex_coords);
	if (col.a < 0.1) discard;
	vec3 final_rgb = mix(col.rgb * interpolated_shading_value, hurt_color.rgb, hurt_color.a);
	fragment_colour = vec4(final_rgb, col.a);
}
"""


class BaseMobModel:
	def __init__(self, texture_path):
		self.texture_path = texture_path
		self.texture_id = None
		self.tex_w = 64
		self.tex_h = 32

		self.shader_program = None
		self.matrix_loc = -1
		self.sampler_loc = -1
		self.hurt_color_loc = -1

		self.vao = None
		self.vbo_pos = None
		self.vbo_tex = None
		self.vbo_shd = None

	def ensure_initialized(self):
		if self.texture_id is None:
			self.load_texture(self.texture_path)
		if self.shader_program is None:
			self.init_shader()

	def load_texture(self, texture_path):
		candidates = [texture_path]
		if not os.path.exists(texture_path):
			base = os.path.basename(texture_path)
			candidates.extend([
				os.path.join("textures", "entity", os.path.splitext(base)[0], base),
				os.path.join("textures", "entity", base),
				os.path.join("textures", base),
				os.path.join("textures", "entities", base)
			])

		valid_path = None
		for cand in candidates:
			if os.path.exists(cand):
				valid_path = cand
				break

		if valid_path:
			try:
				img = pyglet.image.load(valid_path)
				raw_data = img.get_image_data().get_data("RGBA", img.width * 4)
				c_data = (gl.GLubyte * len(raw_data)).from_buffer_copy(raw_data)

				tex_id = gl.GLuint(0)
				gl.glGenTextures(1, tex_id)
				gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id.value)

				gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

				gl.glTexImage2D(
					gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
					img.width, img.height, 0,
					gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, c_data
				)
				self.texture_id = tex_id.value
			except Exception as e:
				print(f"Error loading mob texture {valid_path}: {e}")

	def init_shader(self):
		try:
			def compile_shader_stage(target, source_code):
				b_code = source_code.encode('utf-8')
				s_len = ctypes.c_int(len(b_code))
				s_buf = ctypes.create_string_buffer(b_code)
				ptr = ctypes.cast(ctypes.pointer(ctypes.pointer(s_buf)), ctypes.POINTER(ctypes.POINTER(ctypes.c_char)))
				gl.glShaderSource(target, 1, ptr, ctypes.byref(s_len))
				gl.glCompileShader(target)

				log_len = gl.GLint(0)
				gl.glGetShaderiv(target, gl.GL_INFO_LOG_LENGTH, ctypes.byref(log_len))
				if log_len.value > 1:
					log_buf = ctypes.create_string_buffer(log_len.value)
					gl.glGetShaderInfoLog(target, log_len, None, log_buf)
					print(f"Mob Shader Stage Log: {log_buf.value.decode('utf-8', errors='ignore')}")

			v_shader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
			compile_shader_stage(v_shader, MOB_VERT_SHADER)

			f_shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
			compile_shader_stage(f_shader, MOB_FRAG_SHADER)

			prog = gl.glCreateProgram()
			gl.glAttachShader(prog, v_shader)
			gl.glAttachShader(prog, f_shader)
			gl.glLinkProgram(prog)

			link_status = gl.GLint(0)
			gl.glGetProgramiv(prog, gl.GL_LINK_STATUS, ctypes.byref(link_status))
			if link_status.value != gl.GL_TRUE:
				log_len = gl.GLint(0)
				gl.glGetProgramiv(prog, gl.GL_INFO_LOG_LENGTH, ctypes.byref(log_len))
				log_buf = ctypes.create_string_buffer(log_len.value)
				gl.glGetProgramInfoLog(prog, log_len, None, log_buf)
				print(f"Mob Shader Link Error: {log_buf.value.decode('utf-8', errors='ignore')}")

			self.shader_program = prog
			self.matrix_loc = gl.glGetUniformLocation(prog, ctypes.create_string_buffer(b"matrix"))
			self.sampler_loc = gl.glGetUniformLocation(prog, ctypes.create_string_buffer(b"mob_sampler"))
			self.hurt_color_loc = gl.glGetUniformLocation(prog, ctypes.create_string_buffer(b"hurt_color"))
		except Exception as e:
			print(f"Error initializing Mob shader: {e}")

	def _add_cuboid(self, pos_data, tex_data, shd_data, center, size, uvs, local_rot=(0,0,0), local_pivot=(0,0,0), body_pos=(0,0,0), body_yaw=0.0):
		"""
		Generates 3D cuboid quad faces (6 faces x 4 corners x 3 coordinates).
		Applies local limb rotation around local_pivot, then applies body orientation around mob origin, and translates to body_pos.
		"""
		cx, cy, cz = center
		w, h, d = size
		hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
		bx, by, bz = body_pos

		faces = [
			# Front Face (-Z)
			([cx - hw, cy + hh, cz - hd], [cx + hw, cy + hh, cz - hd], [cx + hw, cy - hh, cz - hd], [cx - hw, cy - hh, cz - hd], uvs["front"], 0.95),
			# Back Face (+Z)
			([cx + hw, cy + hh, cz + hd], [cx - hw, cy + hh, cz + hd], [cx - hw, cy - hh, cz + hd], [cx + hw, cy - hh, cz + hd], uvs["back"],  0.80),
			# Top Face (+Y)
			([cx - hw, cy + hh, cz + hd], [cx + hw, cy + hh, cz + hd], [cx + hw, cy + hh, cz - hd], [cx - hw, cy + hh, cz - hd], uvs["top"],   1.00),
			# Bottom Face (-Y)
			([cx - hw, cy - hh, cz - hd], [cx + hw, cy - hh, cz - hd], [cx + hw, cy - hh, cz + hd], [cx - hw, cy - hh, cz + hd], uvs["bottom"],0.50),
			# Right Face (+X)
			([cx + hw, cy + hh, cz - hd], [cx + hw, cy + hh, cz + hd], [cx + hw, cy - hh, cz + hd], [cx + hw, cy - hh, cz - hd], uvs["right"], 0.85),
			# Left Face (-X)
			([cx - hw, cy + hh, cz + hd], [cx - hw, cy + hh, cz - hd], [cx - hw, cy - hh, cz - hd], [cx - hw, cy - hh, cz + hd], uvs["left"],  0.85)
		]

		for p1, p2, p3, p4, uv_coords, shading in faces:
			corners = [p1, p2, p3, p4]
			transformed = []
			for x, y, z in corners:
				# 1. Rotate locally around part pivot
				x, y, z = transform_point(x, y, z, rx=local_rot[0], ry=local_rot[1], rz=local_rot[2], pivot=local_pivot)
				# 2. Rotate by body yaw around mob origin
				x, y, z = transform_point(x, y, z, ry=body_yaw, pivot=(0.0, 0.0, 0.0))
				# 3. Translate to world mob position
				transformed.append((x + bx, y + by, z + bz))

			for idx in (0, 1, 2, 0, 2, 3):
				pos_data.extend(transformed[idx])
				tex_data.extend([uv_coords[idx][0], uv_coords[idx][1]])
				shd_data.append(shading)

	def _draw_mesh(self, camera, pos_data, tex_data, shd_data, hurt_time=0.0):
		if not self.shader_program:
			return

		gl.glUseProgram(self.shader_program)

		mvp_matrix = camera.mv_matrix * camera.p_matrix
		flat_matrix = [val for row in mvp_matrix.data for val in row]
		if self.matrix_loc != -1:
			gl.glUniformMatrix4fv(self.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_matrix))
		if self.sampler_loc != -1:
			gl.glUniform1i(self.sampler_loc, 0)
		if self.hurt_color_loc != -1:
			alpha = 0.6 if hurt_time > 0.0 else 0.0
			gl.glUniform4f(self.hurt_color_loc, 1.0, 0.2, 0.2, alpha)

		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)

		if self.vao is None:
			self.vao = gl.GLuint(0); gl.glGenVertexArrays(1, self.vao)
			self.vbo_pos = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_pos)
			self.vbo_tex = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_tex)
			self.vbo_shd = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_shd)

		gl.glBindVertexArray(self.vao)

		c_pos = (gl.GLfloat * len(pos_data))(*pos_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_pos), c_pos, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		c_tex = (gl.GLfloat * len(tex_data))(*tex_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_tex), c_tex, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		c_shd = (gl.GLfloat * len(shd_data))(*shd_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shd)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_shd), c_shd, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(pos_data) // 3)
		gl.glBindVertexArray(0)


class PigModel(BaseMobModel):
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "pig", "pig.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		# Canonical Minecraft Pig UV Rectangles
		self.uv_head  = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_snout = build_cuboid_uv_atlas(16, 16, 4, 3, 1, tw, th)
		self.uv_body  = build_cuboid_uv_atlas(28, 8, 10, 16, 8, tw, th)
		self.uv_leg   = build_cuboid_uv_atlas(0, 16, 4, 6, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		# Quadruped leg swing animation
		swing = math.sin(walk_time) * 0.65 if is_moving else 0.0
		leg_fl = swing
		leg_fr = -swing
		leg_bl = -swing
		leg_br = swing

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (Trunk: 10 wide, 16 long, 8 tall. Center y = 13 px = 0.8125, pivot (0, 13, 2) horizontal)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.8125, 0.0), (0.625, 0.5, 1.0), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 0.8125, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD & SNOUT (Pivot at neck y = 12 px = 0.75, z = -6 px = -0.375)
		head_pivot = (0.0, 0.75, -0.375)
		head_rot = (pitch, 0.0, 0.0)

		# Head: 8x8x8 px (0.5 x 0.5 x 0.5 units), Center (0, 12 px, -8 px) -> (0, 0.75, -0.5)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.75, -0.5), (0.5, 0.5, 0.5), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Snout: 4x3x1 px (0.25 x 0.1875 x 0.0625 units), Center (0, 10.5 px, -10.5 px) -> (0, 0.65625, -0.65625)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.65625, -0.65625), (0.25, 0.1875, 0.0625), self.uv_snout,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. LEGS (4x6x4 px = 0.25 x 0.375 x 0.25 units, height = 6 px, pivot y = 6 px = 0.375, center y = 3 px = 0.1875)
		leg_h = 0.375
		leg_y_center = 0.1875
		leg_x = 0.1875  # ±3 px = ±0.1875
		leg_z_front = -0.3125 # -5 px = -0.3125
		leg_z_back = 0.3125   # +5 px = +0.3125

		# Front Left Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (-leg_x, leg_y_center, leg_z_front), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_fl, 0, 0), local_pivot=(-leg_x, leg_h, leg_z_front), body_pos=pos, body_yaw=yaw)
		# Front Right Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (leg_x, leg_y_center, leg_z_front), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_fr, 0, 0), local_pivot=(leg_x, leg_h, leg_z_front), body_pos=pos, body_yaw=yaw)
		# Back Left Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (-leg_x, leg_y_center, leg_z_back), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_bl, 0, 0), local_pivot=(-leg_x, leg_h, leg_z_back), body_pos=pos, body_yaw=yaw)
		# Back Right Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (leg_x, leg_y_center, leg_z_back), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_br, 0, 0), local_pivot=(leg_x, leg_h, leg_z_back), body_pos=pos, body_yaw=yaw)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class CowModel(BaseMobModel):
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "cow", "cow.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		# Canonical Minecraft Cow UV Rectangles
		self.uv_head   = build_cuboid_uv_atlas(0, 0, 8, 8, 6, tw, th)
		self.uv_muzzle = build_cuboid_uv_atlas(0, 14, 6, 4, 3, tw, th)
		self.uv_horn   = build_cuboid_uv_atlas(22, 0, 1, 3, 1, tw, th)
		self.uv_body   = build_cuboid_uv_atlas(18, 4, 12, 18, 10, tw, th)
		self.uv_leg    = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		swing = math.sin(walk_time) * 0.65 if is_moving else 0.0
		leg_fl = swing
		leg_fr = -swing
		leg_bl = -swing
		leg_br = swing

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (Trunk: 12 wide, 18 long, 10 tall. Center y = 14 px = 0.875, pivot (0, 14, 2) horizontal)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.875, 0.0), (0.75, 0.625, 1.125), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 0.875, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD, MUZZLE, & HORNS (Pivot at neck y = 16 px = 1.0, z = -8 px = -0.5)
		head_pivot = (0.0, 1.0, -0.5)
		head_rot = (pitch, 0.0, 0.0)

		# Head: 8x8x6 px (0.5 x 0.5 x 0.375 units), Center (0, 16 px, -10 px) -> (0, 1.0, -0.625)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.0, -0.625), (0.5, 0.5, 0.375), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Muzzle: 6x4x3 px (0.375 x 0.25 x 0.1875 units), Center (0, 14 px, -12.5 px) -> (0, 0.875, -0.78125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.875, -0.78125), (0.375, 0.25, 0.1875), self.uv_muzzle,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Left Horn: 1x3x1 px (0.0625 x 0.1875 x 0.0625 units), Center (-4.5 px, 18.5 px, -8.5 px) -> (-0.28125, 1.15625, -0.53125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-0.28125, 1.15625, -0.53125), (0.0625, 0.1875, 0.0625), self.uv_horn,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Right Horn: 1x3x1 px (0.0625 x 0.1875 x 0.0625 units), Center (4.5 px, 18.5 px, -8.5 px) -> (0.28125, 1.15625, -0.53125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.28125, 1.15625, -0.53125), (0.0625, 0.1875, 0.0625), self.uv_horn,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. LEGS (4x12x4 px = 0.25 x 0.75 x 0.25 units, height = 12 px, pivot y = 12 px = 0.75, center y = 6 px = 0.375)
		leg_h = 0.75
		leg_y_center = 0.375
		leg_x = 0.25          # ±4 px = ±0.25
		leg_z_front = -0.375  # -6 px = -0.375
		leg_z_back = 0.375    # +6 px = +0.375

		# Front Left Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (-leg_x, leg_y_center, leg_z_front), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_fl, 0, 0), local_pivot=(-leg_x, leg_h, leg_z_front), body_pos=pos, body_yaw=yaw)
		# Front Right Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (leg_x, leg_y_center, leg_z_front), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_fr, 0, 0), local_pivot=(leg_x, leg_h, leg_z_front), body_pos=pos, body_yaw=yaw)
		# Back Left Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (-leg_x, leg_y_center, leg_z_back), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_bl, 0, 0), local_pivot=(-leg_x, leg_h, leg_z_back), body_pos=pos, body_yaw=yaw)
		# Back Right Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (leg_x, leg_y_center, leg_z_back), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_br, 0, 0), local_pivot=(leg_x, leg_h, leg_z_back), body_pos=pos, body_yaw=yaw)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class SheepModel(BaseMobModel):
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "sheep", "sheep.png"))
		self.build_uv_atlas()

	def load_texture(self, texture_path):
		super().load_texture(texture_path)
		# Also composite sheep_fur.png on top for fluffy white wool coat
		fur_path = os.path.join("textures", "entity", "sheep", "sheep_fur.png")
		if os.path.exists(fur_path) and self.texture_id:
			try:
				base_img = pyglet.image.load(texture_path if os.path.exists(texture_path) else os.path.join("textures", "entity", "sheep", "sheep.png"))
				fur_img = pyglet.image.load(fur_path)
				raw1 = bytearray(base_img.get_image_data().get_data("RGBA", base_img.width * 4))
				raw2 = bytearray(fur_img.get_image_data().get_data("RGBA", fur_img.width * 4))

				for i in range(0, len(raw1), 4):
					if raw2[i + 3] > 10:
						raw1[i] = raw2[i]
						raw1[i + 1] = raw2[i + 1]
						raw1[i + 2] = raw2[i + 2]
						raw1[i + 3] = 255

				c_data = (gl.GLubyte * len(raw1)).from_buffer_copy(raw1)
				gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
				gl.glTexImage2D(
					gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
					base_img.width, base_img.height, 0,
					gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, c_data
				)
			except Exception as e:
				print(f"Error compositing sheep fur texture: {e}")

	def build_uv_atlas(self):
		tw, th = 64, 32
		# Canonical Minecraft Sheep UV Rectangles
		self.uv_head = build_cuboid_uv_atlas(0, 0, 6, 6, 8, tw, th)
		self.uv_body = build_cuboid_uv_atlas(28, 8, 12, 16, 10, tw, th)
		self.uv_leg  = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, is_grazing=False, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		swing = math.sin(walk_time) * 0.65 if is_moving else 0.0
		leg_fl = swing
		leg_fr = -swing
		leg_bl = -swing
		leg_br = swing

		# Grazing head tilt animation
		effective_pitch = pitch + (0.75 if is_grazing else 0.0)

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (12 wide, 16 long, 10 tall. Center y = 14 px = 0.875)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.875, 0.0), (0.75, 0.625, 1.0), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 0.875, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD (Pivot at neck y = 14 px = 0.875, z = -8 px = -0.5)
		head_pivot = (0.0, 0.875, -0.5)
		head_rot = (effective_pitch, 0.0, 0.0)

		# Head: 6x6x8 px (0.375 x 0.375 x 0.5 units), Center (0, 14 px, -9 px) -> (0, 0.875, -0.5625)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.875, -0.5625), (0.375, 0.375, 0.5), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. LEGS (4x12x4 px, height = 0.75 units, center y = 0.375)
		leg_h = 0.75
		leg_y_center = 0.375
		leg_x = 0.1875        # ±3 px
		leg_z_front = -0.3125 # -5 px
		leg_z_back = 0.3125   # +5 px

		# Front Left Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (-leg_x, leg_y_center, leg_z_front), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_fl, 0, 0), local_pivot=(-leg_x, leg_h, leg_z_front), body_pos=pos, body_yaw=yaw)
		# Front Right Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (leg_x, leg_y_center, leg_z_front), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_fr, 0, 0), local_pivot=(leg_x, leg_h, leg_z_front), body_pos=pos, body_yaw=yaw)
		# Back Left Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (-leg_x, leg_y_center, leg_z_back), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_bl, 0, 0), local_pivot=(-leg_x, leg_h, leg_z_back), body_pos=pos, body_yaw=yaw)
		# Back Right Leg
		self._add_cuboid(pos_data, tex_data, shd_data, (leg_x, leg_y_center, leg_z_back), (0.25, leg_h, 0.25), self.uv_leg, local_rot=(leg_br, 0, 0), local_pivot=(leg_x, leg_h, leg_z_back), body_pos=pos, body_yaw=yaw)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class ChickenModel(BaseMobModel):
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "chicken.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		# Canonical Minecraft Chicken UV Rectangles
		self.uv_head   = build_cuboid_uv_atlas(0, 0, 4, 6, 3, tw, th)
		self.uv_bill   = build_cuboid_uv_atlas(14, 0, 4, 2, 2, tw, th)
		self.uv_chin   = build_cuboid_uv_atlas(14, 4, 2, 2, 2, tw, th)
		self.uv_body   = build_cuboid_uv_atlas(0, 9, 6, 8, 6, tw, th)
		self.uv_wing_l = build_cuboid_uv_atlas(24, 13, 1, 4, 6, tw, th)
		self.uv_wing_r = build_cuboid_uv_atlas(24, 13, 1, 4, 6, tw, th, mirror=True)
		self.uv_leg    = build_cuboid_uv_atlas(26, 0, 3, 5, 3, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, wing_flap=0.0, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		# Bipedal leg swing
		leg_swing = math.sin(walk_time * 1.4) * 0.7 if is_moving else 0.0
		leg_l = leg_swing
		leg_r = -leg_swing

		# Wing flapping (flaps outward when gliding or walking fast)
		flap_angle = math.sin(wing_flap) * 0.55 if wing_flap > 0 else 0.0

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (6 wide, 8 long, 6 tall. Center y = 6 px = 0.375, size = 0.375, 0.375, 0.5)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.375, 0.0), (0.375, 0.375, 0.5), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 0.375, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD, BILL & WATTLE (Pivot at neck y = 9 px = 0.5625, z = -4 px = -0.25)
		head_pivot = (0.0, 0.5625, -0.25)
		head_rot = (pitch, 0.0, 0.0)

		# Head: 4x6x3 px (0.25 x 0.375 x 0.1875 units), Center (0, 0.5625, -0.25)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.5625, -0.25), (0.25, 0.375, 0.1875), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Bill (Beak): 4x2x2 px (0.25 x 0.125 x 0.125 units), Center (0, 0.50, -0.375)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.50, -0.375), (0.25, 0.125, 0.125), self.uv_bill,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Chin (Wattle): 2x2x2 px (0.125 x 0.125 x 0.125 units), Center (0, 0.375, -0.3125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.375, -0.3125), (0.125, 0.125, 0.125), self.uv_chin,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. WINGS (1x4x6 px = 0.0625 x 0.25 x 0.375 units)
		wing_pivot_y = 0.4375
		wing_center_y = 0.375

		# Left Wing
		wing_l_pivot = (-0.1875, wing_pivot_y, 0.0)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-0.21875, wing_center_y, 0.0), (0.0625, 0.25, 0.375), self.uv_wing_l,
			local_rot=(0.0, 0.0, -flap_angle), local_pivot=wing_l_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# Right Wing
		wing_r_pivot = (0.1875, wing_pivot_y, 0.0)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.21875, wing_center_y, 0.0), (0.0625, 0.25, 0.375), self.uv_wing_r,
			local_rot=(0.0, 0.0, flap_angle), local_pivot=wing_r_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 4. LEGS (3x5x3 px = 0.1875 x 0.3125 x 0.1875 units, pivot y = 5 px = 0.3125)
		leg_h = 0.3125
		leg_y_center = 0.15625
		leg_x = 0.09375
		leg_z = 0.0625

		# Left Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-leg_x, leg_y_center, leg_z), (0.1875, leg_h, 0.1875), self.uv_leg,
			local_rot=(leg_l, 0, 0), local_pivot=(-leg_x, leg_h, leg_z),
			body_pos=pos, body_yaw=yaw
		)

		# Right Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(leg_x, leg_y_center, leg_z), (0.1875, leg_h, 0.1875), self.uv_leg,
			local_rot=(leg_r, 0, 0), local_pivot=(leg_x, leg_h, leg_z),
			body_pos=pos, body_yaw=yaw
		)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class ZombieModel(BaseMobModel):
	"""3D Bipedal Zombie Model with forward-reaching arms and canonical 64x64 texture atlas."""
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "zombie", "zombie.png"))
		self.tex_w = 64
		self.tex_h = 64
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 64
		self.uv_head  = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_body  = build_cuboid_uv_atlas(16, 16, 8, 12, 4, tw, th)
		self.uv_arm_l = build_cuboid_uv_atlas(40, 16, 4, 12, 4, tw, th, mirror=True)
		self.uv_arm_r = build_cuboid_uv_atlas(40, 16, 4, 12, 4, tw, th)
		self.uv_leg_l = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th, mirror=True)
		self.uv_leg_r = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, attack_anim_time=0.0, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		swing = math.sin(walk_time) * 0.65 if is_moving else 0.0
		leg_l = swing
		leg_r = -swing

		# Classic Zombie Forward Arm Pose
		base_arm_pitch = -1.50
		if is_moving:
			base_arm_pitch += math.sin(walk_time * 2.0) * 0.08
		if attack_anim_time > 0.0:
			base_arm_pitch -= 0.25

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (8x12x4 px = 0.5 x 0.75 x 0.25 units, center y = 18 px = 1.125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.125, 0.0), (0.50, 0.75, 0.25), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 1.125, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD (8x8x8 px = 0.5 x 0.5 x 0.5 units, pivot y = 24 px = 1.50)
		head_pivot = (0.0, 1.50, 0.0)
		head_rot = (pitch, 0.0, 0.0)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.75, 0.0), (0.50, 0.50, 0.50), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. ARMS (4x12x4 px = 0.25 x 0.75 x 0.25 units, pivot y = 23 px = 1.4375)
		arm_pivot_y = 1.4375
		arm_y_center = 1.0625
		arm_x = 0.375

		# Left Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-arm_x, arm_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_arm_l,
			local_rot=(base_arm_pitch, 0.0, -0.05), local_pivot=(-arm_x, arm_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)
		# Right Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(arm_x, arm_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_arm_r,
			local_rot=(base_arm_pitch, 0.0, 0.05), local_pivot=(arm_x, arm_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 4. LEGS (4x12x4 px = 0.25 x 0.75 x 0.25 units, pivot y = 12 px = 0.75)
		leg_pivot_y = 0.75
		leg_y_center = 0.375
		leg_x = 0.125

		# Left Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-leg_x, leg_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_leg_l,
			local_rot=(leg_l, 0.0, 0.0), local_pivot=(-leg_x, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)
		# Right Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(leg_x, leg_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_leg_r,
			local_rot=(leg_r, 0.0, 0.0), local_pivot=(leg_x, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class ZombiePigmanModel(BaseMobModel):
	"""3D Bipedal Zombie Pigman (Zombified Piglin) Model with 64x64 texture atlas and sword arm pose."""
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "zombie_pigman.png"))
		self.tex_w = 64
		self.tex_h = 64
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 64
		self.uv_head  = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_body  = build_cuboid_uv_atlas(16, 16, 8, 12, 4, tw, th)
		self.uv_arm_l = build_cuboid_uv_atlas(40, 16, 4, 12, 4, tw, th, mirror=True)
		self.uv_arm_r = build_cuboid_uv_atlas(40, 16, 4, 12, 4, tw, th)
		self.uv_leg_l = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th, mirror=True)
		self.uv_leg_r = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, is_angry=False, attack_anim_time=0.0, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		swing = math.sin(walk_time) * (0.80 if is_angry else 0.60) if is_moving else 0.0
		leg_l = swing
		leg_r = -swing

		# Arm poses: neutral walk vs aggressive forward-reaching chase
		if is_angry:
			arm_pitch_r = -1.45 + math.sin(walk_time * 2.0) * 0.10
			arm_pitch_l = -1.45 - math.sin(walk_time * 2.0) * 0.10
		else:
			arm_pitch_r = -swing * 0.7 - 0.20
			arm_pitch_l = swing * 0.7 - 0.20

		if attack_anim_time > 0.0:
			arm_pitch_r -= 0.40

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (8x12x4 px = 0.50 x 0.75 x 0.25 units, center y = 18 px = 1.125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.125, 0.0), (0.50, 0.75, 0.25), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 1.125, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD (8x8x8 px = 0.50 x 0.50 x 0.50 units, pivot y = 24 px = 1.50)
		head_pivot = (0.0, 1.50, 0.0)
		head_rot = (pitch, 0.0, 0.0)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.75, 0.0), (0.50, 0.50, 0.50), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. ARMS (4x12x4 px = 0.25 x 0.75 x 0.25 units, pivot y = 23 px = 1.4375)
		arm_pivot_y = 1.4375
		arm_y_center = 1.0625
		arm_x = 0.375

		# Left Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-arm_x, arm_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_arm_l,
			local_rot=(arm_pitch_l, 0.0, -0.05), local_pivot=(-arm_x, arm_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)
		# Right Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(arm_x, arm_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_arm_r,
			local_rot=(arm_pitch_r, 0.0, 0.05), local_pivot=(arm_x, arm_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 4. LEGS (4x12x4 px = 0.25 x 0.75 x 0.25 units, pivot y = 12 px = 0.75)
		leg_pivot_y = 0.75
		leg_y_center = 0.375
		leg_x = 0.125

		# Left Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-leg_x, leg_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_leg_l,
			local_rot=(leg_l, 0.0, 0.0), local_pivot=(-leg_x, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)
		# Right Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(leg_x, leg_y_center, 0.0), (0.25, 0.75, 0.25), self.uv_leg_r,
			local_rot=(leg_r, 0.0, 0.0), local_pivot=(leg_x, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class SkeletonModel(BaseMobModel):
	"""3D Bipedal Skeleton Model with thin 2x2 bone limbs and bow aiming arm pose."""
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "skeleton", "skeleton.png"))
		self.tex_w = 64
		self.tex_h = 32
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		self.uv_head  = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_body  = build_cuboid_uv_atlas(16, 16, 8, 12, 4, tw, th)
		self.uv_arm_l = build_cuboid_uv_atlas(40, 16, 2, 12, 2, tw, th, mirror=True)
		self.uv_arm_r = build_cuboid_uv_atlas(40, 16, 2, 12, 2, tw, th)
		self.uv_leg_l = build_cuboid_uv_atlas(0, 16, 2, 12, 2, tw, th, mirror=True)
		self.uv_leg_r = build_cuboid_uv_atlas(0, 16, 2, 12, 2, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, is_aiming=False, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		swing = math.sin(walk_time) * 0.65 if is_moving else 0.0
		leg_l = swing
		leg_r = -swing

		# Skeleton Arm Aiming vs Walking Pose
		if is_aiming:
			arm_l_rot = (-1.45, 0.20, 0.0)
			arm_r_rot = (-1.45, -0.20, 0.0)
		else:
			arm_l_rot = (-swing, 0.0, 0.0)
			arm_r_rot = (swing, 0.0, 0.0)

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY (8x12x4 px = 0.5 x 0.75 x 0.25 units, center y = 1.125)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.125, 0.0), (0.50, 0.75, 0.25), self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 1.125, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD (8x8x8 px = 0.5 x 0.5 x 0.5 units, pivot y = 1.50)
		head_pivot = (0.0, 1.50, 0.0)
		head_rot = (pitch, 0.0, 0.0)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.75, 0.0), (0.50, 0.50, 0.50), self.uv_head,
			local_rot=head_rot, local_pivot=head_pivot,
			body_pos=pos, body_yaw=yaw
		)

		# 3. ARMS (2x12x2 px = 0.125 x 0.75 x 0.125 units, pivot y = 1.4375)
		arm_pivot_y = 1.4375
		arm_y_center = 1.0625
		arm_x = 0.3125

		# Left Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-arm_x, arm_y_center, 0.0), (0.125, 0.75, 0.125), self.uv_arm_l,
			local_rot=arm_l_rot, local_pivot=(-arm_x, arm_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)
		# Right Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(arm_x, arm_y_center, 0.0), (0.125, 0.75, 0.125), self.uv_arm_r,
			local_rot=arm_r_rot, local_pivot=(arm_x, arm_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 4. LEGS (2x12x2 px = 0.125 x 0.75 x 0.125 units, pivot y = 12 px = 0.75)
		leg_pivot_y = 0.75
		leg_y_center = 0.375
		leg_x = 0.125

		# Left Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-leg_x, leg_y_center, 0.0), (0.125, 0.75, 0.125), self.uv_leg_l,
			local_rot=(leg_l, 0.0, 0.0), local_pivot=(-leg_x, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)
		# Right Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(leg_x, leg_y_center, 0.0), (0.125, 0.75, 0.125), self.uv_leg_r,
			local_rot=(leg_r, 0.0, 0.0), local_pivot=(leg_x, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 5. 3D HELD BOW MODEL
		bow_uv = self.uv_arm_l
		if is_aiming:
			bow_pivot = (-0.20, 1.35, 0.0)
			bow_rot = (-1.45, 0.20, 0.0)
			bow_offset = (-0.20, 1.35, 0.55)
		else:
			bow_pivot = (-arm_x, arm_pivot_y, 0.0)
			bow_rot = arm_l_rot
			bow_offset = (-arm_x, 0.72, 0.10)

		# Center Grip (1x5x1 px = 0.0625 x 0.3125 x 0.0625)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			bow_offset, (0.0625, 0.3125, 0.0625), bow_uv,
			local_rot=bow_rot, local_pivot=bow_pivot,
			body_pos=pos, body_yaw=yaw
		)
		# Upper Limb (1x4x2 px = 0.0625 x 0.25 x 0.08)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(bow_offset[0], bow_offset[1] + 0.22, bow_offset[2] - 0.05), (0.0625, 0.25, 0.08), bow_uv,
			local_rot=bow_rot, local_pivot=bow_pivot,
			body_pos=pos, body_yaw=yaw
		)
		# Lower Limb (1x4x2 px = 0.0625 x 0.25 x 0.08)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(bow_offset[0], bow_offset[1] - 0.22, bow_offset[2] - 0.05), (0.0625, 0.25, 0.08), bow_uv,
			local_rot=bow_rot, local_pivot=bow_pivot,
			body_pos=pos, body_yaw=yaw
		)
		# Bowstring (thin line = 0.02 x 0.60 x 0.02)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(bow_offset[0], bow_offset[1], bow_offset[2] - 0.09), (0.02, 0.60, 0.02), self.uv_leg_l,
			local_rot=bow_rot, local_pivot=bow_pivot,
			body_pos=pos, body_yaw=yaw
		)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)

class SpiderModel(BaseMobModel):
	"""3D Spider Model with 8 multi-jointed crawling legs, thorax, abdomen, and wall climb tilt."""
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "spider", "spider.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		self.uv_head    = build_cuboid_uv_atlas(32, 4, 8, 8, 8, tw, th)
		self.uv_thorax  = build_cuboid_uv_atlas(0, 0, 6, 6, 6, tw, th)
		self.uv_abdomen = build_cuboid_uv_atlas(0, 12, 10, 12, 8, tw, th)
		self.uv_leg     = build_cuboid_uv_atlas(18, 0, 16, 2, 2, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, is_climbing=False, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		crawl = math.sin(walk_time * 1.5) * 0.45 if is_moving else 0.0

		pos_data, tex_data, shd_data = [], [], []

		# 1. THORAX (6x6x6 px = 0.375 x 0.375 x 0.375 units, center y = 0.45)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.45, 0.0), (0.375, 0.375, 0.375), self.uv_thorax,
			local_rot=(pitch, 0.0, 0.0), local_pivot=(0.0, 0.45, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD (8x8x8 px = 0.5 x 0.5 x 0.5 units, center y = 0.45, z = -0.4375)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.45, -0.4375), (0.50, 0.50, 0.50), self.uv_head,
			local_rot=(pitch, 0.0, 0.0), local_pivot=(0.0, 0.45, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 3. ABDOMEN (10x8x12 px = 0.625 x 0.50 x 0.75 units, center y = 0.50, z = 0.50)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.50, 0.50), (0.625, 0.50, 0.75), self.uv_abdomen,
			local_rot=(pitch, 0.0, 0.0), local_pivot=(0.0, 0.45, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 4. EIGHT LEGS (16x2x2 px = 1.0 x 0.125 x 0.125 units)
		# 4 left legs & 4 right legs spread across thorax
		leg_z_offsets = [-0.15, -0.05, 0.05, 0.15]
		leg_yaw_spreads = [0.70, 0.25, -0.25, -0.70]
		leg_phases = [1.0, -1.0, 1.0, -1.0]

		for i in range(4):
			lz = leg_z_offsets[i]
			base_leg_yaw = leg_yaw_spreads[i]
			l_crawl = crawl * leg_phases[i]

			# Left Leg (extends to negative X)
			pivot_l = (-0.1875, 0.45, lz)
			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(-0.6875, 0.45, lz), (1.0, 0.125, 0.125), self.uv_leg,
				local_rot=(pitch, base_leg_yaw + l_crawl, -0.35), local_pivot=pivot_l,
				body_pos=pos, body_yaw=yaw
			)

			# Right Leg (extends to positive X)
			pivot_r = (0.1875, 0.45, lz)
			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(0.6875, 0.45, lz), (1.0, 0.125, 0.125), self.uv_leg,
				local_rot=(pitch, -base_leg_yaw - l_crawl, 0.35), local_pivot=pivot_r,
				body_pos=pos, body_yaw=yaw
			)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class CreeperModel(BaseMobModel):
	"""3D Creeper Model with 4-legged diagonal walking, head pitch, and swelling fuse pulse."""
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "creeper", "creeper.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		self.uv_head = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_body = build_cuboid_uv_atlas(16, 16, 8, 12, 4, tw, th)
		self.uv_leg  = build_cuboid_uv_atlas(0, 16, 4, 6, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, fuse_progress=0.0, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		# Walking leg swing
		swing = math.sin(walk_time) * 0.65 if is_moving else 0.0
		leg_fl = swing
		leg_br = swing
		leg_fr = -swing
		leg_bl = -swing

		# Swell effect when fuse is charging (expands up to +25%)
		swell = 1.0 + max(0.0, min(1.0, fuse_progress)) * 0.25

		# White flashing overlay during fuse
		is_flashing = False
		if fuse_progress > 0.0:
			if fuse_progress > 0.80 or int(fuse_progress * 16.0) % 2 == 1:
				is_flashing = True

		pos_data, tex_data, shd_data = [], [], []

		# 1. BODY / TORSO (8x12x4 px = 0.50 x 0.75 x 0.25 units, center y = 0.75)
		body_size = (0.50 * swell, 0.75 * swell, 0.25 * swell)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 0.75, 0.0), body_size, self.uv_body,
			local_rot=(0.0, 0.0, 0.0), local_pivot=(0.0, 0.75, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. HEAD (8x8x8 px = 0.50 x 0.50 x 0.50 units, center y = 1.375, pivot y = 1.125)
		head_size = (0.50 * swell, 0.50 * swell, 0.50 * swell)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, 1.375, 0.0), head_size, self.uv_head,
			local_rot=(pitch, 0.0, 0.0), local_pivot=(0.0, 1.125, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 3. FOUR LEGS (4x6x4 px = 0.25 x 0.375 x 0.25 units, pivot y = 0.375, center y = 0.1875)
		leg_size = (0.25, 0.375, 0.25)
		leg_pivot_y = 0.375
		leg_y_center = 0.1875
		lx = 0.125
		lz = 0.1875

		# Front-Left Leg (-X, -Z)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-lx, leg_y_center, -lz), leg_size, self.uv_leg,
			local_rot=(leg_fl, 0.0, 0.0), local_pivot=(-lx, leg_pivot_y, -lz),
			body_pos=pos, body_yaw=yaw
		)
		# Front-Right Leg (+X, -Z)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(lx, leg_y_center, -lz), leg_size, self.uv_leg,
			local_rot=(leg_fr, 0.0, 0.0), local_pivot=(lx, leg_pivot_y, -lz),
			body_pos=pos, body_yaw=yaw
		)
		# Back-Left Leg (-X, +Z)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-lx, leg_y_center, lz), leg_size, self.uv_leg,
			local_rot=(leg_bl, 0.0, 0.0), local_pivot=(-lx, leg_pivot_y, lz),
			body_pos=pos, body_yaw=yaw
		)
		# Back-Right Leg (+X, +Z)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(lx, leg_y_center, lz), leg_size, self.uv_leg,
			local_rot=(leg_br, 0.0, 0.0), local_pivot=(lx, leg_pivot_y, lz),
			body_pos=pos, body_yaw=yaw
		)

		if not pos_data:
			return

		# Apply white flash shading if hissing
		if is_flashing:
			shd_data = [s * 1.6 for s in shd_data]

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class BlazeModel(BaseMobModel):
	"""3D Blaze Model with head and 12 rotating floating rods in 3 orbital tiers."""
	def __init__(self):
		super().__init__(os.path.join("textures", "entity", "blaze.png"))
		self.tex_w = 64
		self.tex_h = 32
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		self.uv_head = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_rod  = build_cuboid_uv_atlas(0, 16, 2, 8, 2, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, is_charging=False, **kwargs):
		self.ensure_initialized()
		if not self.texture_id or not self.shader_program:
			return

		pos_data, tex_data, shd_data = [], [], []

		# Gentle vertical hover bobbing
		hover_y = math.sin(walk_time * 3.0) * 0.08

		# 1. HEAD (8x8x8 px = 0.5x0.5x0.5 units at Y = 1.45)
		head_y = 1.45 + hover_y
		head_rot = (pitch, 0.0, 0.0)
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, head_y, 0.0), (0.50, 0.50, 0.50), self.uv_head,
			local_rot=head_rot, local_pivot=(0.0, head_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. 12 ROTATING FLOATING RODS (2x8x2 px = 0.125x0.50x0.125 units)
		rod_size = (0.125, 0.50, 0.125)
		rot_speed = 3.5 if is_charging else 2.0

		# Upper Tier: 4 rods (Y = 1.40, radius = 0.44)
		tier1_y = 1.40 + hover_y
		r1 = 0.55 if is_charging else 0.44
		for i in range(4):
			angle = (walk_time * rot_speed) + i * (math.pi / 2.0)
			rx = math.cos(angle) * r1
			rz = math.sin(angle) * r1
			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(rx, tier1_y, rz), rod_size, self.uv_rod,
				local_rot=(0.0, -angle, 0.0), local_pivot=(rx, tier1_y, rz),
				body_pos=pos, body_yaw=yaw
			)

		# Middle Tier: 4 rods (Y = 0.90, radius = 0.52, reverse orbit)
		tier2_y = 0.90 + hover_y
		r2 = 0.65 if is_charging else 0.52
		for i in range(4):
			angle = (-walk_time * rot_speed) + i * (math.pi / 2.0) + (math.pi / 4.0)
			rx = math.cos(angle) * r2
			rz = math.sin(angle) * r2
			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(rx, tier2_y, rz), rod_size, self.uv_rod,
				local_rot=(0.0, -angle, 0.0), local_pivot=(rx, tier2_y, rz),
				body_pos=pos, body_yaw=yaw
			)

		# Lower Tier: 4 rods (Y = 0.40, radius = 0.38)
		tier3_y = 0.40 + hover_y
		r3 = 0.48 if is_charging else 0.38
		for i in range(4):
			angle = (walk_time * rot_speed) + i * (math.pi / 2.0) + (math.pi / 3.0)
			rx = math.cos(angle) * r3
			rz = math.sin(angle) * r3
			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(rx, tier3_y, rz), rod_size, self.uv_rod,
				local_rot=(0.0, -angle, 0.0), local_pivot=(rx, tier3_y, rz),
				body_pos=pos, body_yaw=yaw
			)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class EndermanModel(BaseMobModel):
	"""
	Minecraft Java Edition Enderman 3D Model:
	Tall slender 2.9-block biped with long limbs, openable jaw, and glowing eyes.
	Texture atlas: textures/entity/enderman/enderman.png (64x32).
	"""
	def __init__(self):
		super().__init__("textures/entity/enderman/enderman.png")
		# Cuboid UV Atlas mappings (64x32)
		self.uv_head = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tex_w=64, tex_h=32)
		self.uv_jaw = build_cuboid_uv_atlas(0, 16, 8, 4, 8, tex_w=64, tex_h=32)
		self.uv_body = build_cuboid_uv_atlas(32, 16, 8, 12, 4, tex_w=64, tex_h=32)
		self.uv_arm = build_cuboid_uv_atlas(56, 0, 2, 30, 2, tex_w=64, tex_h=32)
		self.uv_leg = build_cuboid_uv_atlas(56, 0, 2, 30, 2, tex_w=64, tex_h=32)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0, target_yaw=None, is_screaming=False, **kwargs):
		pos_data, tex_data, shd_data = [], [], []
		t_yaw = target_yaw if target_yaw is not None else yaw

		# Leg animation
		leg_swing = math.sin(walk_time * 1.4) * 0.7 if is_moving else 0.0
		arm_swing = math.sin(walk_time * 1.4) * 0.7 if is_moving else 0.0

		# 1. LEGS (2x30x2 px = 0.125x1.875x0.125 units)
		leg_size = (0.125, 1.875, 0.125)
		leg_pivot_y = 1.875
		leg_center_y = 0.9375

		# Right Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-0.125, leg_center_y, 0.0), leg_size, self.uv_leg,
			local_rot=(-leg_swing, 0.0, 0.0), local_pivot=(-0.125, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# Left Leg
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.125, leg_center_y, 0.0), leg_size, self.uv_leg,
			local_rot=(leg_swing, 0.0, 0.0), local_pivot=(0.125, leg_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 2. TORSO / BODY (8x12x4 px = 0.50x0.75x0.25 units)
		body_size = (0.50, 0.75, 0.25)
		body_center_y = 2.25
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, body_center_y, 0.0), body_size, self.uv_body,
			body_pos=pos, body_yaw=yaw
		)

		# 3. ARMS (2x30x2 px = 0.125x1.875x0.125 units)
		arm_size = (0.125, 1.875, 0.125)
		shoulder_y = 2.5625
		arm_center_y = shoulder_y - 0.9375

		if is_screaming:
			# Aggro / screaming state: arms raised menacingly forward
			r_arm_rot = (-0.6 + arm_swing * 0.4, 0.0, 0.1)
			l_arm_rot = (-0.6 - arm_swing * 0.4, 0.0, -0.1)
		else:
			r_arm_rot = (arm_swing, 0.0, 0.0)
			l_arm_rot = (-arm_swing, 0.0, 0.0)

		# Right Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(-0.3125, arm_center_y, 0.0), arm_size, self.uv_arm,
			local_rot=r_arm_rot, local_pivot=(-0.3125, shoulder_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# Left Arm
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.3125, arm_center_y, 0.0), arm_size, self.uv_arm,
			local_rot=l_arm_rot, local_pivot=(0.3125, shoulder_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# 4. HEAD & JAW (8x8x8 px = 0.50x0.50x0.50 units)
		head_size = (0.50, 0.50, 0.50)
		neck_pivot_y = 2.625
		head_center_y = 2.875

		yaw_diff = (t_yaw - yaw + math.pi) % math.tau - math.pi
		shudder = math.sin(walk_time * 25.0) * 0.06 if is_screaming else 0.0
		head_rot = (pitch + shudder, yaw_diff, 0.0)

		# Main Head
		self._add_cuboid(
			pos_data, tex_data, shd_data,
			(0.0, head_center_y, 0.0), head_size, self.uv_head,
			local_rot=head_rot, local_pivot=(0.0, neck_pivot_y, 0.0),
			body_pos=pos, body_yaw=yaw
		)

		# Openable Jaw (Lower Mouth) - drops down when screaming
		if is_screaming:
			jaw_size = (0.50, 0.25, 0.50)
			jaw_center_y = head_center_y - 0.20
			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(0.0, jaw_center_y, 0.0), jaw_size, self.uv_jaw,
				local_rot=head_rot, local_pivot=(0.0, neck_pivot_y, 0.0),
				body_pos=pos, body_yaw=yaw
			)

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


class SilverfishModel(BaseMobModel):
	"""
	Minecraft Java Edition Silverfish 3D Model & Wriggling Animation
	- Segmented body (7 body segments)
	- Texture atlas: 64x32
	- Animated undulating sinusoidal crawling motion
	"""
	def __init__(self, texture_path="textures/entity/silverfish.png"):
		super().__init__(texture_path)
		# Build segment UVs (x, y, w, h, d, tex_w=64, tex_h=32)
		self.segment_sizes = [
			(0.1875, 0.125, 0.125),   # 0: Head (3x2x2 px)
			(0.25, 0.1875, 0.125),    # 1: 4x3x2 px
			(0.375, 0.25, 0.1875),    # 2: 6x4x3 px
			(0.375, 0.25, 0.1875),    # 3: 6x4x3 px
			(0.3125, 0.1875, 0.125),  # 4: 5x3x2 px
			(0.25, 0.125, 0.125),     # 5: 4x2x2 px
			(0.1875, 0.0625, 0.0625), # 6: 3x1x1 px
		]
		self.segment_uvs = [
			build_cuboid_uv_atlas(0, 0, 3, 2, 2, 64, 32),
			build_cuboid_uv_atlas(0, 4, 4, 3, 2, 64, 32),
			build_cuboid_uv_atlas(0, 9, 6, 4, 3, 64, 32),
			build_cuboid_uv_atlas(0, 16, 6, 4, 3, 64, 32),
			build_cuboid_uv_atlas(0, 23, 5, 3, 2, 64, 32),
			build_cuboid_uv_atlas(11, 0, 4, 2, 2, 64, 32),
			build_cuboid_uv_atlas(11, 4, 3, 1, 1, 64, 32),
		]

	def draw(self, camera, pos, yaw, pitch, target_yaw=None, walk_time=0.0, hurt_time=0.0, is_moving=False):
		pos_data = []
		tex_data = []
		shd_data = []

		# Segment Z offsets along length (from front +Z to back -Z)
		# Silverfish height is ~0.3 blocks above ground
		current_z = 0.25
		base_y = 0.12

		for i, (size, uvs) in enumerate(zip(self.segment_sizes, self.segment_uvs)):
			w, h, d = size
			seg_z = current_z - (d * 0.5)
			seg_y = base_y + (h * 0.5)

			# Sinusoidal wriggling animation
			anim_freq = 12.0 if is_moving else 3.0
			anim_amp = 0.35 if is_moving else 0.10
			seg_yaw = math.sin(walk_time * anim_freq - i * 0.7) * anim_amp

			self._add_cuboid(
				pos_data, tex_data, shd_data,
				(0.0, seg_y, seg_z), size, uvs,
				local_rot=(0.0, seg_yaw, 0.0), local_pivot=(0.0, seg_y, current_z),
				body_pos=pos, body_yaw=yaw
			)

			current_z -= d

		if not pos_data:
			return

		self._draw_mesh(camera, pos_data, tex_data, shd_data, hurt_time)


