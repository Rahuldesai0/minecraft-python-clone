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
		if os.path.exists(texture_path):
			try:
				img = pyglet.image.load(texture_path)
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
				print(f"Error loading mob texture {texture_path}: {e}")

	def init_shader(self):
		try:
			v_shader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
			v_src = ctypes.create_string_buffer(MOB_VERT_SHADER.encode('utf-8'))
			v_len = ctypes.c_int(len(v_src.value) + 1)
			v_ptr = ctypes.cast(ctypes.pointer(ctypes.pointer(v_src)), ctypes.POINTER(ctypes.POINTER(ctypes.c_char)))
			gl.glShaderSource(v_shader, 1, v_ptr, ctypes.byref(v_len))
			gl.glCompileShader(v_shader)

			f_shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
			f_src = ctypes.create_string_buffer(MOB_FRAG_SHADER.encode('utf-8'))
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
		super().__init__(os.path.join("textures", "entities", "pig.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		# Canonical Minecraft Pig UV Rectangles
		self.uv_head  = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)
		self.uv_snout = build_cuboid_uv_atlas(16, 16, 4, 3, 1, tw, th)
		self.uv_body  = build_cuboid_uv_atlas(28, 8, 10, 16, 8, tw, th)
		self.uv_leg   = build_cuboid_uv_atlas(0, 16, 4, 6, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0):
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
		super().__init__(os.path.join("textures", "entities", "cow.png"))
		self.build_uv_atlas()

	def build_uv_atlas(self):
		tw, th = 64, 32
		# Canonical Minecraft Cow UV Rectangles
		self.uv_head   = build_cuboid_uv_atlas(0, 0, 8, 8, 6, tw, th)
		self.uv_muzzle = build_cuboid_uv_atlas(0, 14, 6, 4, 3, tw, th)
		self.uv_horn   = build_cuboid_uv_atlas(22, 0, 1, 3, 1, tw, th)
		self.uv_body   = build_cuboid_uv_atlas(18, 4, 12, 18, 10, tw, th)
		self.uv_leg    = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th)

	def render(self, camera, pos, yaw, pitch, walk_time, is_moving, hurt_time=0.0):
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
