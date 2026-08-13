import array

SUBCHUNK_WIDTH  = 4
SUBCHUNK_HEIGHT = 4
SUBCHUNK_LENGTH = 4

class Subchunk:
	def __init__(self, parent, subchunk_position):
		self.parent = parent
		self.world = self.parent.world

		self.subchunk_position = subchunk_position

		self.local_position = (
			self.subchunk_position[0] * SUBCHUNK_WIDTH,
			self.subchunk_position[1] * SUBCHUNK_HEIGHT,
			self.subchunk_position[2] * SUBCHUNK_LENGTH)

		self.position = (
			self.parent.position[0] + self.local_position[0],
			self.parent.position[1] + self.local_position[1],
			self.parent.position[2] + self.local_position[2])

		# mesh variables (C-native array.array for zero-copy GPU buffer uploads)

		self.opaque_mesh_vertex_positions = array.array('f')
		self.opaque_mesh_tex_coords = array.array('f')
		self.opaque_mesh_shading_values = array.array('f')
		self.opaque_mesh_index_counter = 0
		self.opaque_mesh_indices = array.array('I')

		self.translucent_mesh_vertex_positions = array.array('f')
		self.translucent_mesh_tex_coords = array.array('f')
		self.translucent_mesh_shading_values = array.array('f')
		self.translucent_mesh_index_counter = 0
		self.translucent_mesh_indices = array.array('I')

		# legacy compatibility aliases
		self.mesh_vertex_positions = array.array('f')
		self.mesh_tex_coords = array.array('f')
		self.mesh_shading_values = array.array('f')
		self.mesh_index_counter = 0
		self.mesh_indices = array.array('I')

	def update_mesh(self):
		self.opaque_mesh_vertex_positions = array.array('f')
		self.opaque_mesh_tex_coords = array.array('f')
		self.opaque_mesh_shading_values = array.array('f')
		self.opaque_mesh_index_counter = 0
		self.opaque_mesh_indices = array.array('I')

		self.translucent_mesh_vertex_positions = array.array('f')
		self.translucent_mesh_tex_coords = array.array('f')
		self.translucent_mesh_shading_values = array.array('f')
		self.translucent_mesh_index_counter = 0
		self.translucent_mesh_indices = array.array('I')

		neighbor_offsets = [
			(1, 0, 0),   # 0: right
			(-1, 0, 0),  # 1: left
			(0, 1, 0),   # 2: top
			(0, -1, 0),  # 3: bottom
			(0, 0, 1),   # 4: front
			(0, 0, -1),  # 5: back
		]

		def add_face(face, is_translucent):
			vp = block_type.vertex_positions[face]

			is_water = block_number in (9, 19)
			is_lava = block_number in (15, 20)
			is_liquid = is_water or is_lava

			if is_liquid:
				# Submerged check: if water is directly above at (x, y + 1, z), fill completely to 1.0 block height (no gaps)
				above_block_num = self.world.get_block_number((x, y + 1, z))
				has_liquid_above = above_block_num in (9, 19, 15, 20)

				if has_liquid_above:
					h_scale = 1.0
				elif is_water:
					level = self.world.get_water_level((x, y, z))
					if level in (0, 8):
						h_scale = 15.0 / 16.0  # Surface water source: 1 pixel lower than 1 block high (15/16 = 0.9375)
					else:
						h_scale = (15.0 - 1.8 * level) / 16.0  # Flowing water decreases height smoothly with level
				elif is_lava:
					level = self.world.get_lava_level((x, y, z))
					if level in (0, 4):
						h_scale = 15.0 / 16.0  # Lava source or falling stream: 15/16 height
					else:
						h_scale = (15.0 - 3.8 * level) / 16.0  # Flowing lava decreases height smoothly across 3 blocks
			else:
				h_scale = 1.0

			if is_translucent:
				pos = self.translucent_mesh_vertex_positions
				for i in range(4):
					pos.append(vp[i * 3 + 0] + x)
					vy = vp[i * 3 + 1]
					if is_liquid:
						if vy > 0.0:
							pos.append((y - 0.5) + h_scale)
						else:
							pos.append(y - 0.5)
					else:
						pos.append(vy + y)
					pos.append(vp[i * 3 + 2] + z)

				c = self.translucent_mesh_index_counter
				self.translucent_mesh_indices.extend((c, c + 1, c + 2, c, c + 2, c + 3))
				self.translucent_mesh_index_counter += 4

				self.translucent_mesh_tex_coords.extend(block_type.tex_coords[face])
				self.translucent_mesh_shading_values.extend(block_type.shading_values[face])
			else:
				pos = self.opaque_mesh_vertex_positions
				for i in range(4):
					pos.append(vp[i * 3 + 0] + x)
					vy = vp[i * 3 + 1]
					if is_liquid:
						if vy > 0.0:
							pos.append((y - 0.5) + h_scale)
						else:
							pos.append(y - 0.5)
					else:
						pos.append(vy + y)
					pos.append(vp[i * 3 + 2] + z)

				c = self.opaque_mesh_index_counter
				self.opaque_mesh_indices.extend((c, c + 1, c + 2, c, c + 2, c + 3))
				self.opaque_mesh_index_counter += 4

				self.opaque_mesh_tex_coords.extend(block_type.tex_coords[face])
				self.opaque_mesh_shading_values.extend(block_type.shading_values[face])

		cx, _, cz = self.parent.chunk_position
		east_chunk = self.world.chunks.get((cx + 1, 0, cz))
		west_chunk = self.world.chunks.get((cx - 1, 0, cz))
		south_chunk = self.world.chunks.get((cx, 0, cz + 1))
		north_chunk = self.world.chunks.get((cx, 0, cz - 1))

		def get_neighbor_block_num(plx, ply, plz, wx, wy, wz):
			if 0 <= plx < 16 and 0 <= ply < 256 and 0 <= plz < 16:
				return self.parent.blocks[plx][ply][plz]
			if ply < 0 or ply >= 256:
				return 0
			if plx >= 16:
				return east_chunk.blocks[0][ply][plz] if east_chunk is not None else 0
			if plx < 0:
				return west_chunk.blocks[15][ply][plz] if west_chunk is not None else 0
			if plz >= 16:
				return south_chunk.blocks[plx][ply][0] if south_chunk is not None else 0
			if plz < 0:
				return north_chunk.blocks[plx][ply][15] if north_chunk is not None else 0
			return 0

		for local_x in range(SUBCHUNK_WIDTH):
			for local_y in range(SUBCHUNK_HEIGHT):
				for local_z in range(SUBCHUNK_LENGTH):
					parent_lx = self.local_position[0] + local_x
					parent_ly = self.local_position[1] + local_y
					parent_lz = self.local_position[2] + local_z

					block_number = self.parent.blocks[parent_lx][parent_ly][parent_lz]

					if block_number:
						block_type = self.world.block_types[block_number]

						x, y, z = (
							self.position[0] + local_x,
							self.position[1] + local_y,
							self.position[2] + local_z)

						is_translucent = getattr(block_type, "translucent", False) or block_type.name in ("water", "under_water")
						is_water = block_type.name in ("water", "under_water")
						is_lava = block_type.name in ("lava", "flowing_lava") or block_number in (15, 20)

						if block_type.is_cube:
							for face_idx, (dx, dy, dz) in enumerate(neighbor_offsets):
								nx, ny, nz = x + dx, y + dy, z + dz
								n_plx, n_ply, n_plz = parent_lx + dx, parent_ly + dy, parent_lz + dz
								neighbor_num = get_neighbor_block_num(n_plx, n_ply, n_plz, nx, ny, nz)

								if is_water or is_lava:
									if neighbor_num == 0:
										add_face(face_idx, is_translucent)
									elif neighbor_num in (9, 19, 15, 20):
										if face_idx != 3:  # Not bottom face
											if is_water:
												n_level = self.world.get_water_level((nx, ny, nz))
												above_n = get_neighbor_block_num(n_plx, n_ply + 1, n_plz, nx, ny + 1, nz) in (9, 19, 15, 20)
												n_h = 1.0 if (above_n or n_level in (0, 8)) else (15.0 - 1.8 * n_level) / 16.0
												
												c_level = self.world.get_water_level((x, y, z))
												above_c = get_neighbor_block_num(parent_lx, parent_ly + 1, parent_lz, x, y + 1, z) in (9, 19, 15, 20)
												c_h = 1.0 if (above_c or c_level in (0, 8)) else (15.0 - 1.8 * c_level) / 16.0
											else:
												n_level = self.world.get_lava_level((nx, ny, nz))
												above_n = get_neighbor_block_num(n_plx, n_ply + 1, n_plz, nx, ny + 1, nz) in (9, 19, 15, 20)
												n_h = 1.0 if (above_n or n_level in (0, 4)) else (15.0 - 3.8 * n_level) / 16.0
												
												c_level = self.world.get_lava_level((x, y, z))
												above_c = get_neighbor_block_num(parent_lx, parent_ly + 1, parent_lz, x, y + 1, z) in (9, 19, 15, 20)
												c_h = 1.0 if (above_c or c_level in (0, 4)) else (15.0 - 3.8 * c_level) / 16.0

											if n_h < c_h - 0.01:
												add_face(face_idx, is_translucent)
									else:
										neighbor_type = self.world.block_types[neighbor_num]
										if not neighbor_type or getattr(neighbor_type, "translucent", False):
											add_face(face_idx, is_translucent)
								else:
									if neighbor_num == 0:
										add_face(face_idx, is_translucent)
									else:
										neighbor_type = self.world.block_types[neighbor_num]
										if not neighbor_type or getattr(neighbor_type, "translucent", False):
											add_face(face_idx, is_translucent)

						else:
							for i in range(len(block_type.vertex_positions)):
								add_face(i, is_translucent)