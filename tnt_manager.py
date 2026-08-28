"""
Minecraft Java Edition Primed TNT Manager & 3D Overworld Renderer
-----------------------------------------------------------------
Manages all active PrimedTNTEntity instances in the world:
- Spawns, updates, physics-steps, and removes primed TNT
- Modern OpenGL 3.3 Core Profile dynamic VAO/VBO rendering
- Flashing white pulse overlay during fuse countdown
- Seamless integration with the World, Explosion Engine, and Chunk mesher
"""

import math
import ctypes
import pyglet.gl as gl
from tnt_entity import PrimedTNTEntity


class TNTManager:
	"""Manages active primed TNT entities, updates physics, and renders 3D TNT cubes."""
	def __init__(self, world):
		self.world = world
		self.tnt_entities = []
		self.next_entity_id = 1

		# OpenGL 3.3 Buffers
		self.vao = None
		self.vbo_pos = None
		self.vbo_tex = None
		self.vbo_shd = None

	def spawn_primed_tnt(self, position, velocity=None, fuse_ticks=80):
		"""Spawns a new PrimedTNTEntity in the world."""
		eid = self.next_entity_id
		self.next_entity_id += 1
		tnt = PrimedTNTEntity(eid, position, velocity=velocity, fuse_ticks=fuse_ticks)
		self.tnt_entities.append(tnt)
		return tnt

	def update(self, dt, mob_manager=None, camera=None, gui=None, item_drop_manager=None):
		"""Updates physics, fuse countdowns, and explosions for all primed TNT entities."""
		i = 0
		while i < len(self.tnt_entities):
			tnt = self.tnt_entities[i]
			tnt.update(
				dt, self.world, tnt_manager=self, mob_manager=mob_manager,
				camera=camera, gui=gui, item_drop_manager=item_drop_manager
			)
			if tnt.is_dead:
				self.tnt_entities.pop(i)
				continue
			i += 1

	def _ensure_buffers(self):
		if self.vao is None:
			self.vao = gl.GLuint(0)
			gl.glGenVertexArrays(1, self.vao)
			self.vbo_pos = gl.GLuint(0)
			gl.glGenBuffers(1, self.vbo_pos)
			self.vbo_tex = gl.GLuint(0)
			gl.glGenBuffers(1, self.vbo_tex)
			self.vbo_shd = gl.GLuint(0)
			gl.glGenBuffers(1, self.vbo_shd)

	def draw(self, shader):
		"""Renders all primed TNT blocks with pulsing white flash in 3D world space."""
		if not self.tnt_entities:
			return

		self._ensure_buffers()

		# Texture layers for TNT: top, bottom, sides
		tex_mgr = self.world.texture_manager
		top_tex = "tnt_top" if "tnt_top" in tex_mgr.textures else "tnt_side"
		bot_tex = "tnt_bottom" if "tnt_bottom" in tex_mgr.textures else "tnt_side"
		side_tex = "tnt_side" if "tnt_side" in tex_mgr.textures else "tnt_top"

		top_layer = float(tex_mgr.textures.index(top_tex)) if top_tex in tex_mgr.textures else 0.0
		bot_layer = float(tex_mgr.textures.index(bot_tex)) if bot_tex in tex_mgr.textures else 0.0
		side_layer = float(tex_mgr.textures.index(side_tex)) if side_tex in tex_mgr.textures else 0.0

		pos_data = []
		tex_data = []
		shd_data = []

		hw = 0.49  # Half width (0.98 total width)
		h = 0.98

		for tnt in self.tnt_entities:
			x, y, z = tnt.position
			
			# Flashing white pulse: Minecraft Java pulses faster as fuse reaches 0
			# Flash on/off every ~5 ticks, then solid white in last 10 ticks
			is_white_flash = False
			if tnt.fuse < 10.0:
				is_white_flash = True
			elif int(tnt.fuse / 4.0) % 2 == 1:
				is_white_flash = True

			shading_base = 1.6 if is_white_flash else 1.0

			# 6 Faces of the TNT Cube: Top, Bottom, North, South, East, West
			faces = [
				# Top face (+Y)
				([(x - hw, y + h, z - hw), (x - hw, y + h, z + hw), (x + hw, y + h, z + hw), (x + hw, y + h, z - hw)], top_layer, 1.0),
				# Bottom face (-Y)
				([(x - hw, y, z + hw), (x - hw, y, z - hw), (x + hw, y, z - hw), (x + hw, y, z + hw)], bot_layer, 0.55),
				# North face (-Z)
				([(x + hw, y, z - hw), (x - hw, y, z - hw), (x - hw, y + h, z - hw), (x + hw, y + h, z - hw)], side_layer, 0.8),
				# South face (+Z)
				([(x - hw, y, z + hw), (x + hw, y, z + hw), (x + hw, y + h, z + hw), (x - hw, y + h, z + hw)], side_layer, 0.8),
				# West face (-X)
				([(x - hw, y, z - hw), (x - hw, y, z + hw), (x - hw, y + h, z + hw), (x - hw, y + h, z - hw)], side_layer, 0.65),
				# East face (+X)
				([(x + hw, y, z + hw), (x + hw, y, z - hw), (x + hw, y + h, z - hw), (x + hw, y + h, z + hw)], side_layer, 0.65),
			]

			for v_quad, layer, face_shd in faces:
				uvs = [(0.0, 0.0, layer), (0.0, 1.0, layer), (1.0, 1.0, layer), (1.0, 0.0, layer)]
				for idx in (0, 1, 2, 0, 2, 3):
					pos_data.extend(v_quad[idx])
					tex_data.extend(uvs[idx])
					shd_data.extend([15.0, 0.0, face_shd * shading_base])

		if not pos_data:
			return

		num_vertices = len(pos_data) // 3

		gl.glBindVertexArray(self.vao)

		# Upload Position VBO (Location 0)
		pos_c_arr = (gl.GLfloat * len(pos_data))(*pos_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(pos_c_arr), pos_c_arr, gl.GL_STREAM_DRAW)
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)

		# Upload Texture VBO (Location 1)
		tex_c_arr = (gl.GLfloat * len(tex_data))(*tex_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tex_c_arr), tex_c_arr, gl.GL_STREAM_DRAW)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)

		# Upload Shading VBO (Location 2)
		shd_c_arr = (gl.GLfloat * len(shd_data))(*shd_data)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shd)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(shd_c_arr), shd_c_arr, gl.GL_STREAM_DRAW)
		gl.glEnableVertexAttribArray(2)
		gl.glVertexAttribPointer(2, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, num_vertices)
		gl.glBindVertexArray(0)
