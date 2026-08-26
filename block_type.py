import models.cube # default model

class Block_type:
	# new optional model argument (cube model by default)
	def __init__(self, texture_manager, name = "unknown", block_face_textures = {"all": "cobblestone"}, model = models.cube, transparent = False, break_time = 1.0, requires_tool = False):
		self.name = name
		self.break_time = break_time
		self.requires_tool = requires_tool

		# create members based on model attributes

		self.model = model
		self.is_cube = getattr(model, "is_cube", True)
		self.transparent = transparent or getattr(model, "transparent", False) or (not self.is_cube)
		self.translucent = getattr(model, "translucent", False)

		# replace data contained in numbers.py with model specific data

		self.vertex_positions = model.vertex_positions
		self.tex_coords = model.tex_coords.copy()
		self.shading_values = model.shading_values

		def set_block_face(face, texture):
			# make sure we don't add inexistent faces
			if face > len(self.tex_coords) - 1:
				return

			self.tex_coords[face] = self.tex_coords[face].copy()

			for vertex in range(4):
				self.tex_coords[face][vertex * 3 + 2] = texture

		for face in block_face_textures:
			texture = block_face_textures[face]
			texture_manager.add_texture(texture)

			texture_index = texture_manager.textures.index(texture)

			if face == "all":
				for f_idx in range(len(self.tex_coords)):
					set_block_face(f_idx, texture_index)
			
			elif face == "sides":
				set_block_face(0, texture_index)
				set_block_face(1, texture_index)
				set_block_face(4, texture_index)
				set_block_face(5, texture_index)
			
			elif face in ["right", "left", "top", "bottom", "front", "back"]:
				set_block_face(["right", "left", "top", "bottom", "front", "back"].index(face), texture_index)
			else:
				new_tc = [0.0, 1.0, float(texture_index),  0.0, 0.0, float(texture_index),  1.0, 0.0, float(texture_index),  1.0, 1.0, float(texture_index)]
				self.tex_coords.append(new_tc)