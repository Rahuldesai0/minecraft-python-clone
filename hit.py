import math
import block_state

HIT_RANGE = 3

class Hit_ray:
	def __init__(self, world, rotation, starting_position):
		self.world = world
		
		self.vector = (
			math.cos(rotation[0]) * math.cos(rotation[1]),
			math.sin(rotation[1]),
			math.sin(rotation[0]) * math.cos(rotation[1]))
		
		self.starting_pos = tuple(starting_position)
		self.position = list(starting_position)
		self.block = tuple(map(lambda x: int(round(x)), self.position))

		self.distance = 0
	
	def check(self, hit_callback, distance, current_block, next_block, face_vector=None):
		block_num = self.world.get_block_number(next_block)
		if block_num != 0 and block_num not in (9, 19, 15, 20):
			boxes = block_state.get_block_hitboxes(self.world, next_block, block_num)
			if boxes:
				# Find closest ray-AABB intersection among block's sub-boxes
				best_t = float('inf')
				best_face = None

				for box in boxes:
					t, f_vec = block_state.ray_intersect_aabb(self.starting_pos, self.vector, box)
					if t is not None and 0.0 <= t <= (HIT_RANGE + 0.5) and t < best_t:
						best_t = t
						best_face = f_vec

				if best_face is not None:
					hit_pos = (
						self.starting_pos[0] + self.vector[0] * best_t,
						self.starting_pos[1] + self.vector[1] * best_t,
						self.starting_pos[2] + self.vector[2] * best_t
					)
					hit_callback(current_block, next_block, best_face, hit_pos)
					return True
			else:
				hit_pos = (
					self.position[0] + self.vector[0] * distance,
					self.position[1] + self.vector[1] * distance,
					self.position[2] + self.vector[2] * distance
				)
				hit_callback(current_block, next_block, face_vector, hit_pos)
				return True
		
		self.position = list(map(lambda x: self.position[x] + self.vector[x] * distance, range(3)))
		self.block = next_block
		self.distance += distance

		return False

	def step(self, hit_callback):
		bx, by, bz = self.block
		local_position = list(map(lambda x: self.position[x] - self.block[x], range(3)))

		sign = [1, 1, 1] # '1' for positive, '-1' for negative
		absolute_vector = list(self.vector)

		for component in range(3):
			if self.vector[component] < 0:
				sign[component] = -1

				absolute_vector[component] = -absolute_vector[component]
				local_position[component] = -local_position[component]
		
		lx, ly, lz = local_position
		vx, vy, vz = absolute_vector

		if vx:
			x = 0.5
			y = (0.5 - lx) / vx * vy + ly
			z = (0.5 - lx) / vx * vz + lz

			if y >= -0.5 and y <= 0.5 and z >= -0.5 and z <= 0.5:
				distance = math.sqrt((x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2)
				return self.check(hit_callback, distance, self.block, (bx + sign[0], by, bz), face_vector=(-sign[0], 0, 0))
		
		if vy:
			x = (0.5 - ly) / vy * vx + lx
			y = 0.5
			z = (0.5 - ly) / vy * vz + lz

			if x >= -0.5 and x <= 0.5 and z >= -0.5 and z <= 0.5:
				distance = math.sqrt((x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2)
				return self.check(hit_callback, distance, self.block, (bx, by + sign[1], bz), face_vector=(0, -sign[1], 0))
		
		if vz:
			x = (0.5 - lz) / vz * vx + lx
			y = (0.5 - lz) / vz * vy + ly
			z = 0.5

			if x >= -0.5 and x <= 0.5 and y >= -0.5 and y <= 0.5:
				distance = math.sqrt((x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2)
				return self.check(hit_callback, distance, self.block, (bx, by, bz + sign[2]), face_vector=(0, 0, -sign[2]))