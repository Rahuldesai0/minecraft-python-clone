"""
Minecraft Java Edition Primed TNT Entity & Physics Simulation
------------------------------------------------------------
Implements canonical Minecraft Java Edition Primed TNT mechanics:
- 0.98 x 0.98 x 0.98 bounding box
- 0.04 blocks/tick gravity
- 0.98 air drag & 0.70 ground friction
- 80 ticks (4.0s) standard fuse / 10-30 ticks chain-reaction fuse
- Continuous swept 3D voxel AABB collision
- Automatic detonation & explosion creation upon fuse expiration
"""

import math
import random
import explosion


class PrimedTNTEntity:
	"""Minecraft Primed TNT Entity with authentic physics, collision, and fuse countdown."""
	def __init__(self, entity_id, position, velocity=None, fuse_ticks=80):
		self.entity_id = entity_id
		self.position = list(position)  # [x, y, z] center-bottom
		if velocity is not None:
			self.velocity = list(velocity)
		else:
			# Default ignition launch impulse: slight upward hop + random horizontal nudge
			angle = random.uniform(0, math.tau)
			self.velocity = [
				-math.sin(angle) * 0.02,
				0.20,
				-math.cos(angle) * 0.02
			]
		self.fuse = float(fuse_ticks)
		self.width = 0.98
		self.height = 0.98
		self.on_ground = False
		self.is_dead = False
		self.yaw = 0.0

	def get_bounding_box(self):
		px, py, pz = self.position
		hw = self.width / 2.0
		return (px - hw, px + hw, py, py + self.height, pz - hw, pz + hw)

	def update(self, dt, world, tnt_manager=None, mob_manager=None, camera=None, gui=None, item_drop_manager=None):
		if self.is_dead:
			return

		dt_ticks = dt * 20.0
		self.fuse -= dt_ticks

		# Fuse Expiration -> Detonation!
		if self.fuse <= 0.0:
			self.is_dead = True
			ex_pos = (self.position[0], self.position[1] + 0.49, self.position[2])
			explosion.create_explosion(
				world, ex_pos, power=4.0, source_entity=self,
				tnt_manager=tnt_manager, mob_manager=mob_manager,
				camera=camera, gui=gui, item_drop_manager=item_drop_manager
			)
			return

		# Gravity (0.04 blocks/tick^2)
		self.velocity[1] -= 0.04 * dt_ticks

		step_vx = self.velocity[0] * dt_ticks
		step_vy = self.velocity[1] * dt_ticks
		step_vz = self.velocity[2] * dt_ticks

		px, py, pz = self.position
		hw = self.width / 2.0
		h = self.height

		def is_solid(bx, by, bz):
			if by < 0 or by > 255:
				return False
			b_id = world.get_block_number((bx, by, bz))
			return b_id != 0 and b_id not in (9, 19, 15, 20, 78)

		# 1. Y Movement & Floor/Ceiling Collision
		ny = py + step_vy
		self.on_ground = False

		if step_vy < 0:
			by_floor = int(math.floor(ny))
			bx_min, bx_max = int(math.floor(px - hw + 0.02)), int(math.floor(px + hw - 0.02))
			bz_min, bz_max = int(math.floor(pz - hw + 0.02)), int(math.floor(pz + hw - 0.02))

			hit_floor = False
			for bx in range(bx_min, bx_max + 1):
				for bz in range(bz_min, bz_max + 1):
					if is_solid(bx, by_floor, bz):
						hit_floor = True
						break
				if hit_floor:
					break

			if hit_floor:
				ny = by_floor + 1.0
				self.velocity[1] = 0.0
				self.on_ground = True
		elif step_vy > 0:
			by_ceil = int(math.floor(ny + h))
			bx_min, bx_max = int(math.floor(px - hw + 0.02)), int(math.floor(px + hw - 0.02))
			bz_min, bz_max = int(math.floor(pz - hw + 0.02)), int(math.floor(pz + hw - 0.02))

			hit_ceil = False
			for bx in range(bx_min, bx_max + 1):
				for bz in range(bz_min, bz_max + 1):
					if is_solid(bx, by_ceil, bz):
						hit_ceil = True
						break
				if hit_ceil:
					break

			if hit_ceil:
				ny = by_ceil - h
				self.velocity[1] = 0.0

		py = ny

		# 2. X Movement & Wall Collision
		nx = px + step_vx
		if step_vx != 0:
			check_x = int(math.floor(nx + hw)) if step_vx > 0 else int(math.floor(nx - hw))
			by_min = int(math.floor(py + 0.05))
			by_max = int(math.floor(py + h - 0.05))
			bz_min = int(math.floor(pz - hw + 0.02))
			bz_max = int(math.floor(pz + hw - 0.02))

			hit_x = False
			for by in range(by_min, by_max + 1):
				for bz in range(bz_min, bz_max + 1):
					if is_solid(check_x, by, bz):
						hit_x = True
						break
				if hit_x:
					break

			if hit_x:
				nx = (check_x - hw - 0.001) if step_vx > 0 else (check_x + 1.0 + hw + 0.001)
				self.velocity[0] = 0.0

		px = nx

		# 3. Z Movement & Wall Collision
		nz = pz + step_vz
		if step_vz != 0:
			check_z = int(math.floor(nz + hw)) if step_vz > 0 else int(math.floor(nz - hw))
			by_min = int(math.floor(py + 0.05))
			by_max = int(math.floor(py + h - 0.05))
			bx_min = int(math.floor(px - hw + 0.02))
			bx_max = int(math.floor(px + hw - 0.02))

			hit_z = False
			for by in range(by_min, by_max + 1):
				for bx in range(bx_min, bx_max + 1):
					if is_solid(bx, by, check_z):
						hit_z = True
						break
				if hit_z:
					break

			if hit_z:
				nz = (check_z - hw - 0.001) if step_vz > 0 else (check_z + 1.0 + hw + 0.001)
				self.velocity[2] = 0.0

		pz = nz
		self.position = [px, py, pz]

		# 4. Drag & Friction
		drag = 0.98 ** dt_ticks
		self.velocity[0] *= drag
		self.velocity[1] *= drag
		self.velocity[2] *= drag

		if self.on_ground:
			self.velocity[0] *= (0.70 ** dt_ticks)
			self.velocity[2] *= (0.70 ** dt_ticks)
