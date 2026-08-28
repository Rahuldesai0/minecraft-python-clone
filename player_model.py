"""
Minecraft Player Model & Skin UV Atlas System
----------------------------------------------
Implements Minecraft's exact player model, hierarchical bone transforms,
canonical 64x64 / 64x32 base skin UV atlas mapping, and dedicated 1st-person arm & held item rendering.

Base Skin UV Atlas Specification (64x64 PNG):
----------------------------------------------
Image Origin: Top-Left (0, 0) in PNG space.
Normalized OpenGL UV: u = x / tex_w, v = (tex_h - y) / tex_h.

1. HEAD (8x8x8 cuboid):
   - top:    ( 8,  0) -> (16,  8)
   - bottom: (16,  0) -> (24,  8)
   - right:  ( 0,  8) -> ( 8, 16)
   - front:  ( 8,  8) -> (16, 16)
   - left:   (16,  8) -> (24, 16)
   - back:   (24,  8) -> (32, 16)

2. RIGHT LEG (4x12x4 cuboid):
   - top:    ( 4, 16) -> ( 8, 20)
   - bottom: ( 8, 16) -> (12, 20)
   - right:  ( 0, 20) -> ( 4, 32)
   - front:  ( 4, 20) -> ( 8, 32)
   - left:   ( 8, 20) -> (12, 32)
   - back:   (12, 20) -> (16, 32)

3. BODY / TORSO (8x12x4 cuboid):
   - top:    (20, 16) -> (28, 20)
   - bottom: (28, 16) -> (36, 20)
   - right:  (16, 20) -> (20, 32)
   - front:  (20, 20) -> (28, 32)
   - left:   (28, 20) -> (32, 32)
   - back:   (32, 20) -> (40, 32)

4. RIGHT ARM (Steve 4x12x4 / Alex 3x12x4):
   - Steve (4w): top (44,16)->(48,20), bottom (48,16)->(52,20), right (40,20)->(44,32), front (44,20)->(48,32), left (48,20)->(52,32), back (52,20)->(56,32)
   - Alex  (3w): top (44,16)->(47,20), bottom (47,16)->(50,20), right (40,20)->(44,32), front (44,20)->(47,32), left (47,20)->(51,32), back (51,20)->(54,32)

5. LEFT LEG (4x12x4 cuboid):
   - 64x64 format (v1.8+): top (20,48)->(24,52), bottom (24,48)->(28,52), right (16,52)->(20,64), front (20,52)->(24,64), left (24,52)->(28,64), back (28,52)->(32,64)
   - 64x32 format (classic): Mirrors Right Leg UVs.

6. LEFT ARM (Steve 4x12x4 / Alex 3x12x4):
   - 64x64 format (v1.8+):
     Steve (4w): top (36,48)->(40,52), bottom (40,48)->(44,52), right (32,52)->(36,64), front (36,52)->(40,64), left (40,52)->(44,64), back (44,52)->(48,64)
     Alex  (3w): top (36,48)->(39,52), bottom (39,48)->(42,52), right (32,52)->(36,64), front (36,52)->(39,64), left (39,52)->(43,64), back (43,52)->(46,64)
   - 64x32 format (classic): Mirrors Right Arm UVs.

Model Dimensions & Pivots (1 block = 1.0 unit = 16 model pixels, scale = 0.0625):
----------------------------------------------------------------------------------
- Head:      8x8x8 px   (0.5 x 0.5 x 0.5 units),    Pivot: (0.0, 1.5, 0.0)
- Body:      8x12x4 px  (0.5 x 0.75 x 0.25 units),  Pivot: (0.0, 1.5, 0.0)
- Right Leg: 4x12x4 px  (0.25 x 0.75 x 0.25 units), Pivot: (-0.125, 0.75, 0.0)
- Left Leg:  4x12x4 px  (0.25 x 0.75 x 0.25 units), Pivot: (0.125, 0.75, 0.0)
- Right Arm: Steve: 4x12x4 px (0.25 x 0.75 x 0.25), Pivot: (-0.375, 1.375, 0.0)
             Alex:  3x12x4 px (0.1875 x 0.75 x 0.25), Pivot: (-0.34375, 1.375, 0.0)
- Left Arm:  Steve: 4x12x4 px (0.25 x 0.75 x 0.25), Pivot: (0.375, 1.375, 0.0)
             Alex:  3x12x4 px (0.1875 x 0.75 x 0.25), Pivot: (0.34375, 1.375, 0.0)
"""

import os
import math
import ctypes
import pyglet
import pyglet.gl as gl


BLOCK_FACE_TEXTURES = {
	2:  {"top": "grass", "bottom": "dirt", "front": "grass_side", "back": "grass_side", "left": "grass_side", "right": "grass_side"},
	8:  {"top": "log_top", "bottom": "log_top", "front": "log_side", "back": "log_side", "left": "log_side", "right": "log_side"},
	11: {"top": "cactus_top", "bottom": "cactus_bottom", "front": "cactus_side", "back": "cactus_side", "left": "cactus_side", "right": "cactus_side"},
	23: {"top": "planks", "bottom": "planks", "front": "bookshelf", "back": "bookshelf", "left": "bookshelf", "right": "bookshelf"},
	25: {"top": "tnt_top", "bottom": "tnt_bottom", "front": "tnt_side", "back": "tnt_side", "left": "tnt_side", "right": "tnt_side"},
	26: {"top": "crafting_table_top", "bottom": "planks", "front": "crafting_table_x", "back": "crafting_table_x", "left": "crafting_table_z", "right": "crafting_table_z"},
	27: {"top": "furnace_y", "bottom": "stone", "front": "furnace_front", "back": "furnace_side", "left": "furnace_side", "right": "furnace_side"},
	37: {"top": "chest_top", "bottom": "planks", "front": "chest_front", "back": "chest_side", "left": "chest_side", "right": "chest_side"},
}


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


def get_face_uv_rect(x0, y0, x1, y1, tex_w=64, tex_h=64, mirror=False):
	"""
	Converts 2D image pixel rectangle (x0, y0) -> (x1, y1) into 4 normalized OpenGL UV corners.
	Image origin: Top-Left (0, 0).
	OpenGL UV origin: Bottom-Left (0.0, 0.0).
	Returns corners: top-left (u0, v1), top-right (u1, v1), bottom-right (u1, v0), bottom-left (u0, v0).
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


def build_cuboid_uv_atlas(x, y, w, h, d, tex_w=64, tex_h=64, mirror=False):
	"""
	Computes the 6 canonical face UV rectangles for a Minecraft cuboid of size (w, h, d) at origin (x, y).
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


# GLSL Shaders specifically for 2D Player Skin Texture & Held Items
PLAYER_VERT_SHADER = """
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

PLAYER_FRAG_SHADER = """
#version 330
out vec4 fragment_colour;

uniform sampler2D skin_sampler;
uniform float light_mult;

in vec2 interpolated_tex_coords;
in float interpolated_shading_value;

void main(void) {
	vec4 col = texture(skin_sampler, interpolated_tex_coords);
	if (col.a < 0.1) discard;
	float lm = (light_mult <= 0.0) ? 1.0 : light_mult;
	fragment_colour = vec4(col.rgb * (interpolated_shading_value * lm), col.a);
}
"""


class StevePlayerModel:
	def __init__(self, skin_path=None):
		self.skin_texture_id = None
		self.tex_w = 64
		self.tex_h = 64
		self.is_alex = False

		self.item_texture_cache = {}

		self.load_skin(skin_path)
		self.build_uv_atlas()

		self.walk_time = 0.0
		self.swing_time = 0.0
		self.is_swinging = False
		self.sneaking = False
		self.in_liquid = False
		self.holding_item = False

		# Custom Shader Program for 2D Player Skin Texture & Held Items
		self.shader_program = None
		self.matrix_loc = -1
		self.sampler_loc = -1
		self.init_shader()

		# VAO / VBO buffers for 3D Third-Person Model Rendering
		self.vao_3rd = None
		self.vbo_pos_3rd = None
		self.vbo_tex_3rd = None
		self.vbo_shd_3rd = None

		# VAO / VBO buffers for Dedicated 1st-Person Arm Rendering
		self.vao_1st = None
		self.vbo_pos_1st = None
		self.vbo_tex_1st = None
		self.vbo_shd_1st = None

		# VAO / VBO buffers for Held Item Rendering
		self.vao_held = None
		self.vbo_pos_held = None
		self.vbo_tex_held = None
		self.vbo_shd_held = None

	def load_skin(self, skin_path=None):
		if skin_path is None:
			skin_path = os.path.join("textures", "entity", "steve.png")

		if os.path.exists(skin_path):
			try:
				img = pyglet.image.load(skin_path)
				self.tex_w = img.width
				self.tex_h = img.height
				raw_data = img.get_image_data().get_data("RGBA", img.width * 4)

				# Detect Alex (slim 3px arm) vs Steve (classic 4px arm)
				if self.tex_h >= 64 and len(raw_data) >= 64 * 64 * 4:
					pixel_offset = (43 * 64 + 54) * 4
					alpha = raw_data[pixel_offset + 3]
					if alpha == 0:
						self.is_alex = True

				tex_id = gl.GLuint(0)
				gl.glGenTextures(1, tex_id)
				gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id.value)

				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

				gl.glTexImage2D(
					gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
					img.width, img.height, 0,
					gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw_data
				)
				self.skin_texture_id = tex_id.value
			except Exception as e:
				print(f"Error loading Steve skin texture: {e}")

	def build_uv_atlas(self):
		tw, th = self.tex_w, self.tex_h
		arm_w = 3 if self.is_alex else 4

		# 1. HEAD (8x8x8 at x=0, y=0)
		self.uv_head = build_cuboid_uv_atlas(0, 0, 8, 8, 8, tw, th)

		# 2. RIGHT LEG (4x12x4 at x=0, y=16)
		self.uv_r_leg = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th)

		# 3. BODY / TORSO (8x12x4 at x=16, y=16)
		self.uv_torso = build_cuboid_uv_atlas(16, 16, 8, 12, 4, tw, th)

		# 4. RIGHT ARM (arm_w x 12 x 4 at x=40, y=16)
		self.uv_r_arm = build_cuboid_uv_atlas(40, 16, arm_w, 12, 4, tw, th)

		# 5. LEFT LEG (4x12x4)
		if th >= 64:
			self.uv_l_leg = build_cuboid_uv_atlas(16, 48, 4, 12, 4, tw, th)
		else:
			self.uv_l_leg = build_cuboid_uv_atlas(0, 16, 4, 12, 4, tw, th, mirror=True)

		# 6. LEFT ARM (arm_w x 12 x 4)
		if th >= 64:
			self.uv_l_arm = build_cuboid_uv_atlas(32, 48, arm_w, 12, 4, tw, th)
		else:
			self.uv_l_arm = build_cuboid_uv_atlas(40, 16, arm_w, 12, 4, tw, th, mirror=True)

	def init_shader(self):
		try:
			v_shader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
			v_src = ctypes.create_string_buffer(PLAYER_VERT_SHADER.encode('utf-8'))
			v_len = ctypes.c_int(len(v_src.value) + 1)
			v_ptr = ctypes.cast(ctypes.pointer(ctypes.pointer(v_src)), ctypes.POINTER(ctypes.POINTER(ctypes.c_char)))
			gl.glShaderSource(v_shader, 1, v_ptr, ctypes.byref(v_len))
			gl.glCompileShader(v_shader)

			f_shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
			f_src = ctypes.create_string_buffer(PLAYER_FRAG_SHADER.encode('utf-8'))
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
			self.sampler_loc = gl.glGetUniformLocation(prog, ctypes.create_string_buffer(b"skin_sampler"))
			self.light_mult_loc = gl.glGetUniformLocation(prog, ctypes.create_string_buffer(b"light_mult"))
		except Exception as e:
			print(f"Error initializing Player shader: {e}")

	def get_named_texture_id(self, tex_name):
		if tex_name in self.item_texture_cache:
			return self.item_texture_cache[tex_name]

		img_path = os.path.join("textures", f"{tex_name}.png")
		if os.path.exists(img_path):
			try:
				img = pyglet.image.load(img_path)
				raw_data = img.get_image_data().get_data("RGBA", img.width * 4)

				tex_id = gl.GLuint(0)
				gl.glGenTextures(1, tex_id)
				gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id.value)

				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
				gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

				gl.glTexImage2D(
					gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
					img.width, img.height, 0,
					gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw_data
				)
				self.item_texture_cache[tex_name] = tex_id.value
				return tex_id.value
			except Exception as e:
				print(f"Error loading named texture {tex_name}: {e}")

		return self.skin_texture_id

	def get_item_texture_id(self, b_id, icon_textures=None):
		if b_id in self.item_texture_cache:
			return self.item_texture_cache[b_id]

		from gui import BLOCK_INFO
		if b_id in BLOCK_INFO:
			tex_name = BLOCK_INFO[b_id][1]
			return self.get_named_texture_id(tex_name)

		return self.skin_texture_id

	def update(self, dt, is_moving, sprinting=False, left_click=False, sneaking=False, in_liquid=False, holding_item=False):
		self.sneaking = sneaking
		self.in_liquid = in_liquid
		self.holding_item = holding_item

		if is_moving:
			speed_mult = 14.0 if sprinting else 8.0
			self.walk_time += dt * speed_mult
		else:
			self.walk_time = self.walk_time % (2 * math.pi)
			if self.walk_time > 0:
				self.walk_time = max(0.0, self.walk_time - dt * 10.0)

		if left_click:
			self.is_swinging = True

		if self.is_swinging:
			self.swing_time += dt * 7.0
			if self.swing_time >= 1.0:
				self.swing_time = 0.0
				self.is_swinging = False

	def _add_cuboid(self, pos_data, tex_data, shd_data, center, size, uvs, local_rot=(0,0,0), local_pivot=(0,0,0), body_pos=(0,0,0), body_yaw=0.0, body_pitch=0.0):
		"""
		Generates 3D cuboid quad faces (6 faces x 4 corners x 3 coordinates).
		Applies local limb rotation around local_pivot, then applies body orientation around feet origin, and translates to body_pos.
		"""
		cx, cy, cz = center
		w, h, d = size
		hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
		bx, by, bz = body_pos

		# 6 Faces with exact quad corner order (top-left, top-right, bottom-right, bottom-left)
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
				# 1. Rotate locally around limb pivot
				x, y, z = transform_point(x, y, z, rx=local_rot[0], ry=local_rot[1], rz=local_rot[2], pivot=local_pivot)
				# 2. Rotate by body pitch (for swimming/sneaking) then yaw around feet origin
				if body_pitch != 0.0:
					x, y, z = transform_point(x, y, z, rx=body_pitch, pivot=(0.0, 1.0, 0.0))
				x, y, z = transform_point(x, y, z, ry=body_yaw, pivot=(0.0, 0.0, 0.0))
				# 3. Translate to world body position
				transformed.append((x + bx, y + by, z + bz))

			# 2 Triangles per quad: (0, 1, 2) and (0, 2, 3)
			for idx in (0, 1, 2, 0, 2, 3):
				pos_data.extend(transformed[idx])
				tex_data.extend([uv_coords[idx][0], uv_coords[idx][1]])
				shd_data.append(shading)

	def _add_item_quad(self, pos_data, tex_data, shd_data, center, size, local_rot=(0,0,0), local_pivot=(0,0,0), in_plane_rot=3.14159265):
		"""
		Generates clean double-sided 2D item quad (front & back faces) with zero side-stretching artifacts.
		in_plane_rot: Rotation angle in radians to rotate the item in its 2D plane (default 180 degrees = 3.14159265 rad).
		"""
		cx, cy, cz = center
		s = size / 2.0

		# Front quad facing +Z
		f_corners = [
			(-s,  s, 0.0), # Top-Left
			( s,  s, 0.0), # Top-Right
			( s, -s, 0.0), # Bottom-Right
			(-s, -s, 0.0)  # Bottom-Left
		]
		f_uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]

		# Back quad facing -Z
		b_corners = [
			( s,  s, 0.0), # Top-Left
			(-s,  s, 0.0), # Top-Right
			(-s, -s, 0.0), # Bottom-Right
			( s, -s, 0.0)  # Bottom-Left
		]
		b_uvs = [(1.0, 1.0), (0.0, 1.0), (0.0, 0.0), (1.0, 0.0)]

		for corners, uv_coords, shading in [(f_corners, f_uvs, 1.0), (b_corners, b_uvs, 0.85)]:
			transformed = []
			for x, y, z in corners:
				# Rotate in 2D item plane first by 90 degrees
				x, y, z = transform_point(x, y, z, rz=in_plane_rot)
				x += cx; y += cy; z += cz
				x, y, z = transform_point(x, y, z, rx=local_rot[0], ry=local_rot[1], rz=local_rot[2], pivot=local_pivot)
				transformed.append((x, y, z))

			for idx in (0, 1, 2, 0, 2, 3):
				pos_data.extend(transformed[idx])
				tex_data.extend([uv_coords[idx][0], uv_coords[idx][1]])
				shd_data.append(shading)

	def render_third_person(self, camera, perspective, world):
		"""
		Renders Steve/Alex 3D Player Model in Third-Person View (TPP Back or TPP Front).
		Exact Minecraft model dimensions (in 1/16th block units):
		- Head: 8x8x8 px (0.5 x 0.5 x 0.5 units), Pivot (0.0, 1.5, 0.0)
		- Body: 8x12x4 px (0.5 x 0.75 x 0.25 units), Pivot (0.0, 1.5, 0.0)
		- Right Leg: 4x12x4 px (0.25 x 0.75 x 0.25 units), Pivot (-0.125, 0.75, 0.0)
		- Left Leg: 4x12x4 px (0.25 x 0.75 x 0.25 units), Pivot (0.125, 0.75, 0.0)
		- Right Arm: Steve: 4x12x4 (0.25x0.75x0.25, Pivot -0.375,1.375,0), Alex: 3x12x4 (0.1875x0.75x0.25, Pivot -0.34375,1.375,0)
		- Left Arm:  Steve: 4x12x4 (0.25x0.75x0.25, Pivot  0.375,1.375,0), Alex: 3x12x4 (0.1875x0.75x0.25, Pivot  0.34375,1.375,0)
		"""
		if not self.skin_texture_id or not self.shader_program:
			return

		px, py, pz = camera.position
		yaw, pitch = camera.rotation
		feet_pos = (px, py - getattr(camera, 'eye_offset', 1.62), pz)

		# Limb swing animations
		swing = math.sin(self.walk_time) * (math.pi / 5.0)
		arm_swing_r = -swing
		arm_swing_l = swing
		leg_swing_r = swing
		leg_swing_l = -swing

		# Attack/Mining swing animation
		mining_swing = math.sin(self.swing_time * math.pi) * (math.pi / 3.0) if self.is_swinging else 0.0
		arm_swing_r -= mining_swing

		# Holding item arm pose
		if self.holding_item:
			arm_swing_r -= 0.35

		# Sneaking posture
		sneak_pitch = 0.25 if self.sneaking else 0.0
		body_y_offset = -0.125 if self.sneaking else 0.0
		feet_pos = (feet_pos[0], feet_pos[1] + body_y_offset, feet_pos[2])

		# Swimming posture
		body_pitch = math.pi / 2.5 if self.in_liquid else sneak_pitch

		# Arm dimensions & pivots for Steve vs Alex
		arm_w = 0.1875 if self.is_alex else 0.25
		r_arm_x = -0.34375 if self.is_alex else -0.375
		l_arm_x = 0.34375 if self.is_alex else 0.375

		pos_data = []
		tex_data = []
		shd_data = []

		# 1. BODY / TORSO (Center y = 1.125, size 0.5 x 0.75 x 0.25)
		self._add_cuboid(pos_data, tex_data, shd_data, (0.0, 1.125, 0.0), (0.5, 0.75, 0.25), self.uv_torso, body_pos=feet_pos, body_yaw=yaw, body_pitch=body_pitch)

		# 2. HEAD (Pivot at neck y = 1.5, size 0.5 x 0.5 x 0.5, center y = 1.75)
		self._add_cuboid(pos_data, tex_data, shd_data, (0.0, 1.75, 0.0), (0.5, 0.5, 0.5), self.uv_head, local_rot=(pitch, 0, 0), local_pivot=(0.0, 1.5, 0.0), body_pos=feet_pos, body_yaw=yaw, body_pitch=body_pitch)

		# 3. RIGHT LEG (Pivot at hip y = 0.75, x = -0.125, size 0.25 x 0.75 x 0.25, center y = 0.375)
		self._add_cuboid(pos_data, tex_data, shd_data, (-0.125, 0.375, 0.0), (0.25, 0.75, 0.25), self.uv_r_leg, local_rot=(leg_swing_r, 0, 0), local_pivot=(-0.125, 0.75, 0.0), body_pos=feet_pos, body_yaw=yaw, body_pitch=body_pitch)

		# 4. LEFT LEG (Pivot at hip y = 0.75, x = 0.125, size 0.25 x 0.75 x 0.25, center y = 0.375)
		self._add_cuboid(pos_data, tex_data, shd_data, (0.125, 0.375, 0.0), (0.25, 0.75, 0.25), self.uv_l_leg, local_rot=(leg_swing_l, 0, 0), local_pivot=(0.125, 0.75, 0.0), body_pos=feet_pos, body_yaw=yaw, body_pitch=body_pitch)

		# 5. RIGHT ARM (Pivot at shoulder y = 1.375, x = r_arm_x, size arm_w x 0.75 x 0.25, center y = 1.0)
		self._add_cuboid(pos_data, tex_data, shd_data, (r_arm_x, 1.0, 0.0), (arm_w, 0.75, 0.25), self.uv_r_arm, local_rot=(arm_swing_r, 0, 0), local_pivot=(r_arm_x, 1.375, 0.0), body_pos=feet_pos, body_yaw=yaw, body_pitch=body_pitch)

		# 6. LEFT ARM (Pivot at shoulder y = 1.375, x = l_arm_x, size arm_w x 0.75 x 0.25, center y = 1.0)
		self._add_cuboid(pos_data, tex_data, shd_data, (l_arm_x, 1.0, 0.0), (arm_w, 0.75, 0.25), self.uv_l_arm, local_rot=(arm_swing_l, 0, 0), local_pivot=(l_arm_x, 1.375, 0.0), body_pos=feet_pos, body_yaw=yaw, body_pitch=body_pitch)

		if not pos_data:
			return

		gl.glUseProgram(self.shader_program)

		mvp_matrix = camera.mv_matrix * camera.p_matrix
		flat_matrix = sum(mvp_matrix.data, [])
		if self.matrix_loc != -1:
			gl.glUniformMatrix4fv(self.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_matrix))
		if self.sampler_loc != -1:
			gl.glUniform1i(self.sampler_loc, 0)
		if getattr(self, "light_mult_loc", -1) != -1:
			p_light = 1.0
			if world:
				bx, by, bz = int(math.floor(feet_pos[0])), int(math.floor(feet_pos[1])), int(math.floor(feet_pos[2]))
				_, sky_lvl, blk_lvl = world.get_light_at((bx, by, bz))
				eff = max(sky_lvl, blk_lvl)
				p_light = 0.20 + 0.80 * ((eff / 15.0) ** 1.5)
			gl.glUniform1f(self.light_mult_loc, p_light)

		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D, self.skin_texture_id)

		if self.vao_3rd is None:
			self.vao_3rd = gl.GLuint(0)
			gl.glGenVertexArrays(1, self.vao_3rd)
			self.vbo_pos_3rd = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_pos_3rd)
			self.vbo_tex_3rd = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_tex_3rd)
			self.vbo_shd_3rd = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_shd_3rd)

		gl.glBindVertexArray(self.vao_3rd)

		# Position VBO
		c_pos = (gl.GLfloat * len(pos_data))(*pos_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos_3rd)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_pos), c_pos, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		# TexCoord VBO
		c_tex = (gl.GLfloat * len(tex_data))(*tex_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex_3rd)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_tex), c_tex, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		# Shading VBO
		c_shd = (gl.GLfloat * len(shd_data))(*shd_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shd_3rd)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_shd), c_shd, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(pos_data) // 3)
		gl.glBindVertexArray(0)

	def render_first_person_arm(self, camera, held_block_id=0, icon_textures=None):
		"""
		Dedicated Minecraft First-Person Arm & Held Item/Block Rendering Pipeline.
		Renders Steve/Alex 3D Right Arm extending forward into the screen from the lower-right corner.
		Renders held miniature 3D block or clean 2D item tool held naturally in hand.
		"""
		if not self.skin_texture_id or not self.shader_program:
			return

		# Walking bobbing
		bob_x = math.cos(self.walk_time) * 0.015
		bob_y = math.sin(self.walk_time * 2.0) * 0.01

		# Mining / Attack Swing animation
		swing_sin = math.sin(self.swing_time * math.pi)
		rot_x = -0.85 * swing_sin  # -48 deg pitch chop
		rot_y = +0.40 * swing_sin  # +23 deg yaw sweep inward
		rot_z = -0.30 * swing_sin  # -17 deg roll

		off_x = -0.12 * swing_sin + bob_x
		off_y = -0.10 * swing_sin + bob_y
		off_z = -0.15 * swing_sin

		arm_w = 0.1875 if self.is_alex else 0.25

		# Position shoulder in lower-right corner of screen extending forward into -Z
		arm_center = (0.38 + off_x, -0.42 + off_y, -0.38 + off_z)
		arm_pivot = (0.38, -0.15, -0.38)

		# Pitch arm forward (+1.10 rad / ~63 deg), turn inward (-0.45 rad / ~-26 deg), roll (+0.15 rad / ~9 deg)
		arm_rot = (rot_x + 1.10, rot_y - 0.45, rot_z + 0.15)

		arm_pos_data = []
		arm_tex_data = []
		arm_shd_data = []

		self._add_cuboid(
			arm_pos_data, arm_tex_data, arm_shd_data,
			arm_center, (arm_w, 0.75, 0.25), self.uv_r_arm,
			local_rot=arm_rot, local_pivot=arm_pivot,
			body_pos=(0, 0, 0), body_yaw=0.0
		)

		if not arm_pos_data:
			return

		# Render 3D Arm using Camera Projection Matrix
		gl.glUseProgram(self.shader_program)
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glClear(gl.GL_DEPTH_BUFFER_BIT) # Ensure 1st-person arm renders cleanly over world terrain

		flat_p_matrix = sum(camera.p_matrix.data, [])
		if self.matrix_loc != -1:
			gl.glUniformMatrix4fv(self.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_p_matrix))
		if self.sampler_loc != -1:
			gl.glUniform1i(self.sampler_loc, 0)
		if getattr(self, "light_mult_loc", -1) != -1:
			p_light = 1.0
			if hasattr(camera, 'position'):
				px, py, pz = camera.position
			gl.glUniform1f(self.light_mult_loc, 1.0)

		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D, self.skin_texture_id)

		if self.vao_1st is None:
			self.vao_1st = gl.GLuint(0); gl.glGenVertexArrays(1, self.vao_1st)
			self.vbo_pos_1st = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_pos_1st)
			self.vbo_tex_1st = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_tex_1st)
			self.vbo_shd_1st = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_shd_1st)

		gl.glBindVertexArray(self.vao_1st)

		c_pos = (gl.GLfloat * len(arm_pos_data))(*arm_pos_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos_1st)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_pos), c_pos, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		c_tex = (gl.GLfloat * len(arm_tex_data))(*arm_tex_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex_1st)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_tex), c_tex, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		c_shd = (gl.GLfloat * len(arm_shd_data))(*arm_shd_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shd_1st)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_shd), c_shd, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(arm_pos_data) // 3)
		gl.glBindVertexArray(0)

		# Render Held Block or Item in Hand if active slot has an item/block
		if held_block_id != 0:
			self.render_held_item(camera, held_block_id, icon_textures, arm_center, arm_rot, swing_sin, off_x, off_y, off_z)

		gl.glEnable(gl.GL_CULL_FACE)

	def _draw_single_mesh(self, pos_data, tex_data, shd_data, tex_id):
		if not pos_data or not tex_id:
			return

		gl.glUseProgram(self.shader_program)
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
		if getattr(self, "light_mult_loc", -1) != -1:
			gl.glUniform1f(self.light_mult_loc, 1.0)

		if self.vao_held is None:
			self.vao_held = gl.GLuint(0); gl.glGenVertexArrays(1, self.vao_held)
			self.vbo_pos_held = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_pos_held)
			self.vbo_tex_held = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_tex_held)
			self.vbo_shd_held = gl.GLuint(0); gl.glGenBuffers(1, self.vbo_shd_held)

		gl.glBindVertexArray(self.vao_held)

		c_pos = (gl.GLfloat * len(pos_data))(*pos_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos_held)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_pos), c_pos, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		c_tex = (gl.GLfloat * len(tex_data))(*tex_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex_held)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_tex), c_tex, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		c_shd = (gl.GLfloat * len(shd_data))(*shd_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shd_held)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_shd), c_shd, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(pos_data) // 3)
		gl.glBindVertexArray(0)

	def render_held_item(self, camera, held_block_id, icon_textures, arm_center, arm_rot, swing_sin, off_x, off_y, off_z):
		# Hand position at the front tip of the extended right arm
		hand_x = arm_center[0] - 0.10
		hand_y = arm_center[1] + 0.18
		hand_z = arm_center[2] - 0.20

		is_tool = (held_block_id >= 100 or held_block_id in (
			38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 56, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76,
			91, 92, 95, 178, 180,
			226, 227, 228, 230, 231, 272,
			236, 237, 238, 240, 241, 273,
			246, 247, 248, 250, 251, 274,
			256, 257, 258, 260, 261, 275,
			266, 267, 268, 270, 271, 276
		))

		if is_tool:
			# Tool Item (e.g. Pickaxe, Shovel, Axe, Sword, Stick, Ingot)
			# Clean 2D Quad rotated by +90 degrees as requested by user
			item_tex_id = self.get_item_texture_id(held_block_id, icon_textures)
			if not item_tex_id:
				return

			tool_center = (hand_x + 0.02, hand_y + 0.08, hand_z - 0.14)
			tool_pivot = (hand_x, hand_y, hand_z)
			tool_rot = (arm_rot[0] + 0.25, arm_rot[1] - 0.35, arm_rot[2] - 0.75)

			item_pos_data = []
			item_tex_data = []
			item_shd_data = []

			self._add_item_quad(
				item_pos_data, item_tex_data, item_shd_data,
				tool_center, 0.42, local_rot=tool_rot, local_pivot=tool_pivot
			)
			self._draw_single_mesh(item_pos_data, item_tex_data, item_shd_data, item_tex_id)

		else:
			# 3D Block (e.g. Crafting Table, Furnace, Chest, Grass, Dirt, Planks, TNT, etc.)
			# Miniature 3D block (size: 0.20 x 0.20 x 0.20) sitting in hand
			block_center = (hand_x - 0.02, hand_y + 0.06, hand_z - 0.08)
			block_pivot = (hand_x, hand_y, hand_z)
			block_rot = (arm_rot[0] + 0.25, arm_rot[1] + 0.70, arm_rot[2] - 0.15)

			cx, cy, cz = block_center
			w, h, d = 0.20, 0.20, 0.20
			hw, hh, hd = w / 2.0, h / 2.0, d / 2.0

			full_uv = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]

			# 6 Faces with exact respective textures
			faces_spec = [
				# ("top", p1, p2, p3, p4, shading)
				("top",    [cx - hw, cy + hh, cz + hd], [cx + hw, cy + hh, cz + hd], [cx + hw, cy + hh, cz - hd], [cx - hw, cy + hh, cz - hd], 1.00),
				("bottom", [cx - hw, cy - hh, cz - hd], [cx + hw, cy - hh, cz - hd], [cx + hw, cy - hh, cz + hd], [cx - hw, cy - hh, cz + hd], 0.50),
				("front",  [cx - hw, cy + hh, cz - hd], [cx + hw, cy + hh, cz - hd], [cx + hw, cy - hh, cz - hd], [cx - hw, cy - hh, cz - hd], 0.95),
				("back",   [cx + hw, cy + hh, cz + hd], [cx - hw, cy + hh, cz + hd], [cx - hw, cy - hh, cz + hd], [cx + hw, cy - hh, cz + hd], 0.80),
				("right",  [cx + hw, cy + hh, cz - hd], [cx + hw, cy + hh, cz + hd], [cx + hw, cy - hh, cz + hd], [cx + hw, cy - hh, cz - hd], 0.85),
				("left",   [cx - hw, cy + hh, cz + hd], [cx - hw, cy + hh, cz - hd], [cx - hw, cy - hh, cz - hd], [cx - hw, cy - hh, cz + hd], 0.85),
			]

			# Check if block has custom multi-face texture dictionary (e.g. Crafting Table, Furnace, Chest)
			if held_block_id in BLOCK_FACE_TEXTURES:
				face_tex_map = BLOCK_FACE_TEXTURES[held_block_id]
				for face_name, p1, p2, p3, p4, shading in faces_spec:
					tex_name = face_tex_map.get(face_name, face_tex_map.get("sides", "stone"))
					tex_id = self.get_named_texture_id(tex_name)

					pos_data, tex_data, shd_data = [], [], []
					transformed = []
					for x, y, z in [p1, p2, p3, p4]:
						x, y, z = transform_point(x, y, z, rx=block_rot[0], ry=block_rot[1], rz=block_rot[2], pivot=block_pivot)
						transformed.append((x, y, z))

					for idx in (0, 1, 2, 0, 2, 3):
						pos_data.extend(transformed[idx])
						tex_data.extend([full_uv[idx][0], full_uv[idx][1]])
						shd_data.append(shading)

					self._draw_single_mesh(pos_data, tex_data, shd_data, tex_id)
			else:
				# Single texture block
				tex_id = self.get_item_texture_id(held_block_id, icon_textures)
				pos_data, tex_data, shd_data = [], [], []
				for face_name, p1, p2, p3, p4, shading in faces_spec:
					transformed = []
					for x, y, z in [p1, p2, p3, p4]:
						x, y, z = transform_point(x, y, z, rx=block_rot[0], ry=block_rot[1], rz=block_rot[2], pivot=block_pivot)
						transformed.append((x, y, z))

					for idx in (0, 1, 2, 0, 2, 3):
						pos_data.extend(transformed[idx])
						tex_data.extend([full_uv[idx][0], full_uv[idx][1]])
						shd_data.append(shading)

				self._draw_single_mesh(pos_data, tex_data, shd_data, tex_id)
