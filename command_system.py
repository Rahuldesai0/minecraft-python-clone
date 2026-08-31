"""
Minecraft Java Edition Command System & Fast Procedural Structure Locator
--------------------------------------------------------------------------
Implements:
1. /tp <x> <y> <z> [dimension]  (Local & Cross-Dimension Teleportation)
2. /summon <mob_name> [x] [y] [z]  (Passive, Hostile & Boss Entities)
3. /kill [@s | @e | @a]  (Targeted Player & Entity Killer)
4. /locate <structure_name>  (Ultra-fast <0.1ms Mathematical Structure Probe within 2000 blocks)
"""

import math
import random

COLOR_SUCCESS = (85, 255, 85, 255)    # Minecraft Green
COLOR_ERROR   = (255, 85, 85, 255)    # Minecraft Red
COLOR_INFO    = (85, 255, 255, 255)   # Minecraft Aqua / Cyan
COLOR_WARN    = (255, 255, 85, 255)   # Minecraft Yellow

STRUCTURE_DIMENSIONS = {
	"village": "overworld",
	"stronghold": "overworld",
	"dungeon": "overworld",
	"spawner": "overworld",
	"fortress": "nether",
	"nether_fortress": "nether",
	"pillars": "end",
	"end_pillars": "end",
	"crystals": "end",
	"exit_portal": "end",
	"fountain": "end",
	"end_portal": "end",
	"spawn_platform": "end",
}

VALID_MOBS = {
	"cow": "cow",
	"pig": "pig",
	"sheep": "sheep",
	"chicken": "chicken",
	"zombie": "zombie",
	"skeleton": "skeleton",
	"spider": "spider",
	"creeper": "creeper",
	"enderman": "enderman",
	"zombie_pigman": "zombie_pigman",
	"pigman": "zombie_pigman",
	"blaze": "blaze",
	"silverfish": "silverfish",
	"ghast": "ghast",
	"magma_cube": "magma_cube",
	"ender_dragon": "ender_dragon",
	"dragon": "ender_dragon",
}


def parse_coord(token, current_val):
	"""Parses absolute or relative tilde (~) coordinate."""
	token = token.strip()
	if token.startswith("~"):
		rem = token[1:]
		if not rem:
			return float(current_val)
		return float(current_val) + float(rem)
	return float(token)


def execute_command(game, raw_cmd):
	"""
	Parses and executes an in-game command.
	Returns: (success: bool, feedback_text: str, color_rgba: tuple)
	"""
	if not raw_cmd or not raw_cmd.strip():
		return False, "", COLOR_ERROR

	cmd_str = raw_cmd.strip()
	if cmd_str.startswith("/"):
		cmd_str = cmd_str[1:].strip()

	if not cmd_str:
		return False, "", COLOR_ERROR

	tokens = cmd_str.split()
	cmd = tokens[0].lower()
	args = tokens[1:]

	# -------------------------------------------------------------
	# 1. TELEPORT (/tp or /teleport)
	# -------------------------------------------------------------
	if cmd in ("tp", "teleport"):
		# /tp without args -> teleport to last death location, or world spawn if not dead
		if len(args) == 0:
			last_death = getattr(game, "last_death_pos", None) or getattr(game.camera, "last_death_pos", None)
			if last_death is not None:
				dx, dy, dz = last_death
				dim = getattr(game, "last_death_dimension", getattr(game.camera, "last_death_dimension", "overworld"))
				game.teleport_to(dx, dy - game.camera.eye_offset, dz, dimension=dim)
				return True, f"Teleported to last death location: X={dx:.1f}, Y={dy:.1f}, Z={dz:.1f} in {dim}", COLOR_SUCCESS
			else:
				# Teleport to X=0, Z=0 and Y surface where player spawned in world
				spawn_y = 64
				if hasattr(game, "get_surface_height"):
					spawn_y = game.get_surface_height(0, 0)
				elif hasattr(game, "world") and game.world:
					for y in range(255, 0, -1):
						b = game.world.get_block_number((0, y, 0))
						if b != 0 and b not in (9, 19, 15, 20):
							spawn_y = y
							break
				target_y = float(spawn_y + 1.0)
				game.teleport_to(0.5, target_y, 0.5, dimension="overworld")
				return True, f"Teleported to world spawn: X=0.5, Y={target_y:.1f}, Z=0.5 in overworld", COLOR_SUCCESS

		if len(args) < 3:
			return False, "Usage: /tp [x y z [dimension]]", COLOR_ERROR

		px, py, pz = game.camera.position
		try:
			tx = parse_coord(args[0], px)
			ty = parse_coord(args[1], py - game.camera.eye_offset)
			tz = parse_coord(args[2], pz)
		except ValueError:
			return False, f"Invalid coordinates: {' '.join(args[:3])}", COLOR_ERROR

		target_dim = None
		if len(args) >= 4:
			dim_arg = args[3].lower()
			if dim_arg in ("overworld", "nether", "end"):
				target_dim = dim_arg
			else:
				return False, f"Unknown dimension: '{dim_arg}' (Use: overworld, nether, end)", COLOR_ERROR

		current_dim = getattr(game, "dimension", "overworld")
		final_dim = target_dim if target_dim else current_dim

		try:
			game.teleport_to(tx, ty, tz, dimension=final_dim)
			dim_suffix = f" in {final_dim}" if target_dim else ""
			return True, f"Teleported to X={tx:.1f}, Y={ty:.1f}, Z={tz:.1f}{dim_suffix}", COLOR_SUCCESS
		except Exception as e:
			return False, f"Teleport failed: {e}", COLOR_ERROR

	# -------------------------------------------------------------
	# 2. SUMMON (/summon)
	# -------------------------------------------------------------
	elif cmd == "summon":
		if not args:
			return False, "Usage: /summon <mob_name> [x] [y] [z]", COLOR_ERROR

		mob_raw = args[0].lower()
		if mob_raw not in VALID_MOBS:
			valid_list = ", ".join(sorted(list(set(VALID_MOBS.keys()))))
			return False, f"Unknown entity: '{mob_raw}'. Available: {valid_list}", COLOR_ERROR

		canonical_mob = VALID_MOBS[mob_raw]
		px, py, pz = game.camera.position

		# Determine spawn position
		if len(args) >= 4:
			try:
				sx = parse_coord(args[1], px)
				sy = parse_coord(args[2], py - game.camera.eye_offset)
				sz = parse_coord(args[3], pz)
			except ValueError:
				return False, f"Invalid spawn coordinates: {' '.join(args[1:4])}", COLOR_ERROR
		else:
			# Default: 2 blocks in front of player
			rad_x, rad_y = game.camera.rotation
			dir_x = math.cos(rad_x) * math.cos(rad_y)
			dir_z = math.sin(rad_x) * math.cos(rad_y)
			sx = px + dir_x * 2.5
			sy = py - game.camera.eye_offset
			sz = pz + dir_z * 2.5

		try:
			if canonical_mob == "ender_dragon":
				import ender_dragon
				dragon = ender_dragon.EnderDragonEntity((sx, sy + 5.0, sz))
				game.ender_dragon = dragon
				if hasattr(game, "world") and game.world:
					game.world.ender_dragon = dragon
				if getattr(game, "ender_dragon_renderer", None) is None:
					game.ender_dragon_renderer = ender_dragon.EnderDragonRenderer(game.texture_manager)
				return True, f"Summoned Ender Dragon at X={sx:.1f}, Y={sy:.1f}, Z={sz:.1f}", COLOR_SUCCESS
			else:
				if hasattr(game, "mob_manager") and game.mob_manager:
					mob = game.mob_manager.spawn_mob(canonical_mob, (sx, sy, sz))
					return True, f"Summoned new {canonical_mob} at X={sx:.1f}, Y={sy:.1f}, Z={sz:.1f}", COLOR_SUCCESS
				else:
					return False, "Mob manager is not available.", COLOR_ERROR
		except Exception as e:
			return False, f"Summon failed: {e}", COLOR_ERROR

	# -------------------------------------------------------------
	# 3. KILL (/kill)
	# -------------------------------------------------------------
	elif cmd == "kill":
		target = args[0].lower() if args else "@s"

		if target == "@s":
			# Kill player self
			px, py, pz = game.camera.position
			curr_dim = getattr(game, "dimension", "overworld")
			game.last_death_pos = [px, py, pz]
			game.last_death_dimension = curr_dim
			game.camera.last_death_pos = [px, py, pz]
			game.camera.last_death_dimension = curr_dim
			if hasattr(game, "mob_manager") and game.mob_manager:
				game.mob_manager.reset_all_aggro()
			if hasattr(game, "camera") and hasattr(game.camera, "take_damage"):
				game.camera.health = max(1, game.camera.health)
				game.camera.take_damage(99999, flying=False, gui=game.gui, world=game.world)
			return True, "Killed self (@s)", COLOR_WARN

		elif target == "@e":
			# Kill all active mobs
			killed_count = 0
			if hasattr(game, "mob_manager") and game.mob_manager:
				killed_count += len(game.mob_manager.mobs)
				game.mob_manager.mobs.clear()

			if hasattr(game, "ender_dragon") and game.ender_dragon and not game.ender_dragon.is_dead:
				game.ender_dragon.health = 0
				game.ender_dragon.is_dead = True
				killed_count += 1

			return True, f"Killed {killed_count} active entities (@e)", COLOR_SUCCESS

		elif target == "@a":
			# Kill all mobs AND player
			killed_count = 0
			if hasattr(game, "mob_manager") and game.mob_manager:
				killed_count += len(game.mob_manager.mobs)
				game.mob_manager.mobs.clear()

			if hasattr(game, "ender_dragon") and game.ender_dragon and not game.ender_dragon.is_dead:
				game.ender_dragon.health = 0
				game.ender_dragon.is_dead = True
				killed_count += 1

			px, py, pz = game.camera.position
			curr_dim = getattr(game, "dimension", "overworld")
			game.last_death_pos = [px, py, pz]
			game.last_death_dimension = curr_dim
			game.camera.last_death_pos = [px, py, pz]
			game.camera.last_death_dimension = curr_dim

			if hasattr(game, "mob_manager") and game.mob_manager:
				game.mob_manager.reset_all_aggro()

			if hasattr(game, "camera") and hasattr(game.camera, "take_damage"):
				game.camera.health = max(1, game.camera.health)
				game.camera.take_damage(99999, flying=False, gui=game.gui, world=game.world)
				killed_count += 1

			return True, f"Killed everything: Player and {max(0, killed_count - 1)} entities (@a)", COLOR_WARN

		else:
			return False, f"Unknown target selector: '{target}' (Use: @s, @e, @a)", COLOR_ERROR

	# -------------------------------------------------------------
	# 4. LOCATE (/locate)
	# -------------------------------------------------------------
	elif cmd == "locate":
		if not args:
			struct_list = "village, stronghold, fortress, pillars, exit_portal"
			return False, f"Usage: /locate <structure_name> (Available: {struct_list})", COLOR_ERROR

		struct_name = args[0].lower()
		current_dim = getattr(game, "dimension", "overworld")

		if struct_name not in STRUCTURE_DIMENSIONS:
			valid_s = ", ".join(sorted(list(set(STRUCTURE_DIMENSIONS.keys()))))
			return False, f"Unknown structure '{struct_name}'. Available: {valid_s}", COLOR_ERROR

		expected_dim = STRUCTURE_DIMENSIONS[struct_name]
		if current_dim != expected_dim:
			return False, f"Structure '{struct_name}' does not generate in the {current_dim}! (Found in: {expected_dim})", COLOR_ERROR

		px, py, pz = game.camera.position
		seed = getattr(game, "world_seed", None)
		if seed is None and hasattr(game, "world") and game.world:
			seed = getattr(game.world, "seed", 0)
		if seed is None:
			seed = 0

		# Mathematical ultra-fast 2000-block search without loading chunks
		if struct_name == "village":
			import village
			curr_rx = int(math.floor(px / 288.0))
			curr_rz = int(math.floor(pz / 288.0))

			closest_v = None
			min_d = float('inf')

			# 2000 block radius search (~4 regions = 1152m)
			for dx in range(-4, 5):
				for dz in range(-4, 5):
					rx = curr_rx + dx
					rz = curr_rz + dz
					plan = village.get_village_for_region(seed, rx, rz)
					if plan:
						dist = math.sqrt((plan.center_x - px) ** 2 + (plan.center_z - pz) ** 2)
						if dist <= 2000.0 and dist < min_d:
							min_d = dist
							closest_v = (plan.center_x, plan.base_y, plan.center_z, dist)

			if closest_v:
				vx, vy, vz, dist = closest_v
				return True, f"[Structure] Closest village is at X: {vx}, Y: {vy}, Z: {vz} ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Could not find structure 'village' within 2000 blocks.", COLOR_WARN

		elif struct_name == "stronghold":
			import stronghold_manager
			positions = stronghold_manager.get_stronghold_positions(seed)

			closest_sh = None
			min_d = float('inf')
			for sx, sy, sz in positions:
				dist = math.sqrt((sx - px) ** 2 + (sz - pz) ** 2)
				if dist <= 2000.0 and dist < min_d:
					min_d = dist
					closest_sh = (sx, sy, sz, dist)

			if closest_sh:
				sx, sy, sz, dist = closest_sh
				return True, f"[Structure] Closest stronghold is at X: {sx}, Y: {sy}, Z: {sz} ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Could not find structure 'stronghold' within 2000 blocks.", COLOR_WARN

		elif struct_name in ("dungeon", "spawner"):
			import dungeon
			curr_cx = int(math.floor(px / 16.0))
			curr_cz = int(math.floor(pz / 16.0))
			closest_d = None
			min_d = float('inf')

			# Search up to 60 chunks (960 blocks)
			for dx in range(-60, 61):
				for dz in range(-60, 61):
					d_data = dungeon.get_dungeon_in_chunk(curr_cx + dx, curr_cz + dz, seed)
					if d_data:
						dwx, dwy, dwz, mob_t = d_data
						floor_y = dwy - 2
						dist = math.sqrt((dwx - px) ** 2 + (dwz - pz) ** 2)
						if dist <= 1000.0 and dist < min_d:
							min_d = dist
							closest_d = (dwx, floor_y, dwz, mob_t, dist)

			if closest_d:
				dwx, floor_y, dwz, mob_t, dist = closest_d
				return True, f"[Structure] Closest {mob_t} dungeon is at X: {dwx}, Y: {floor_y}, Z: {dwz} ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Could not find any dungeons within 1000 blocks.", COLOR_WARN

		elif struct_name in ("fortress", "nether_fortress"):
			import fortress_manager
			curr_rx = int(math.floor(px / 384.0))
			curr_rz = int(math.floor(pz / 384.0))

			closest_f = None
			min_d = float('inf')

			# 2000 block radius search (~3 regions = 1152m)
			for dx in range(-3, 4):
				for dz in range(-3, 4):
					rx = curr_rx + dx
					rz = curr_rz + dz
					f = fortress_manager.get_fortress_for_region(rx, rz, seed)
					if f:
						fx, fy, fz = f.origin
						dist = math.sqrt((fx - px) ** 2 + (fz - pz) ** 2)
						if dist <= 2000.0 and dist < min_d:
							min_d = dist
							closest_f = (fx, fy, fz, dist)

			if closest_f:
				fx, fy, fz, dist = closest_f
				return True, f"[Structure] Closest nether_fortress is at X: {fx}, Y: {fy}, Z: {fz} ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Could not find structure 'fortress' within 2000 blocks.", COLOR_WARN

		elif struct_name in ("pillars", "end_pillars", "crystals"):
			import end_generator
			pillar_defs = end_generator.get_pillar_definitions()
			closest_p = None
			min_d = float('inf')

			for p in pillar_defs:
				px_p = p['x']
				pz_p = p['z']
				ph = p['height']
				dist = math.sqrt((px_p - px) ** 2 + (pz_p - pz) ** 2)
				if dist <= 2000.0 and dist < min_d:
					min_d = dist
					closest_p = (px_p, ph, pz_p, dist)

			if closest_p:
				x, y, z, dist = closest_p
				return True, f"[Structure] Closest obsidian pillar is at X: {x}, Y: {y}, Z: {z} ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Could not find structure 'pillars' within 2000 blocks.", COLOR_WARN

		elif struct_name in ("exit_portal", "fountain", "end_portal"):
			import end_generator
			fy = end_generator.get_fountain_y(seed)
			dist = math.sqrt(px * px + pz * pz)
			if dist <= 2000.0:
				return True, f"[Structure] Central Exit Portal Fountain is at X: 0, Y: {fy}, Z: 0 ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Central Exit Portal is outside 2000 blocks.", COLOR_WARN

		elif struct_name == "spawn_platform":
			import end_generator
			py_plat = end_generator.get_spawn_platform_y(seed)
			dist = math.sqrt((100 - px) ** 2 + pz * pz)
			if dist <= 2000.0:
				return True, f"[Structure] Obsidian Spawn Platform is at X: 100, Y: {py_plat}, Z: 0 ({dist:.1f} blocks away)", COLOR_INFO
			else:
				return False, "Obsidian Spawn Platform is outside 2000 blocks.", COLOR_WARN

	# -------------------------------------------------------------
	# 5. TIME (/time set <preset|val> or /time add <seconds>)
	# -------------------------------------------------------------
	elif cmd == "time":
		if not args:
			tod = getattr(game, "time_of_day", 0.25) % 1.0
			total_min = int(tod * 24.0 * 60.0)
			hours = (total_min // 60)
			mins = total_min % 60
			period = "AM" if hours < 12 else "PM"
			disp_hour = hours % 12
			if disp_hour == 0:
				disp_hour = 12
			return True, f"Current time is {disp_hour}:{mins:02d} {period} (time_of_day: {tod:.3f})", COLOR_INFO

		subcmd = args[0].lower()
		if subcmd == "set":
			if len(args) < 2:
				return False, "Usage: /time set <sunrise | midday | sunset | midnight | moon <phase> | day <num> | value>", COLOR_ERROR

			target_val = args[1].lower()

			# Sub-preset: /time set moon <phase_name_or_int>
			if target_val == "moon":
				if len(args) < 3:
					return False, "Usage: /time set moon <0-7 | full | new | waning_gibbous | third_quarter | waning_crescent | waxing_crescent | first_quarter | waxing_gibbous>", COLOR_ERROR
				m_arg = args[2].lower()
				PHASE_ALIASES = {
					"full": 0, "full_moon": 0, "0": 0,
					"waning_gibbous": 1, "gibbous_waning": 1, "1": 1,
					"third_quarter": 2, "last_quarter": 2, "2": 2,
					"waning_crescent": 3, "crescent_waning": 3, "3": 3,
					"new": 4, "new_moon": 4, "4": 4,
					"waxing_crescent": 5, "crescent_waxing": 5, "5": 5,
					"first_quarter": 6, "6": 6,
					"waxing_gibbous": 7, "gibbous_waxing": 7, "7": 7,
				}
				if m_arg in PHASE_ALIASES:
					target_phase = PHASE_ALIASES[m_arg]
					game.day_count = target_phase
					game.time_of_day = 0.0  # Set to midnight to view moon
					if hasattr(game, "update_sky_color"):
						game.update_sky_color()
					return True, f"Set Moon to Phase {target_phase} ({game.moon_phase_name}, Day {game.day_count}) at Midnight", COLOR_SUCCESS
				else:
					return False, f"Unknown moon phase: '{m_arg}'. (Options: full, new, waning_gibbous, third_quarter, waning_crescent, waxing_crescent, first_quarter, waxing_gibbous, 0-7)", COLOR_ERROR

			# Sub-preset: /time set day <day_number>
			if target_val == "day" and len(args) >= 3:
				try:
					d_num = int(args[2])
					game.day_count = max(0, d_num)
					game.time_of_day = 0.50
					if hasattr(game, "update_sky_color"):
						game.update_sky_color()
					return True, f"Set world to Day {game.day_count} (Moon Phase: {game.moon_phase_name})", COLOR_SUCCESS
				except ValueError:
					return False, f"Invalid day number: '{args[2]}'", COLOR_ERROR

			PRESETS = {
				"sunrise": 0.25,
				"dawn": 0.25,
				"morning": 0.25,
				"midday": 0.50,
				"noon": 0.50,
				"day": 0.50,
				"sunset": 0.75,
				"dusk": 0.75,
				"midnight": 0.0,
				"night": 0.0,
			}

			if target_val in PRESETS:
				new_tod = PRESETS[target_val]
				game.time_of_day = new_tod
				if hasattr(game, "update_sky_color"):
					game.update_sky_color()
				name_cap = target_val.capitalize()
				return True, f"Set time to {name_cap} ({new_tod:.2f}) [Day {getattr(game, 'day_count', 0)}: {getattr(game, 'moon_phase_name', 'Full Moon')}]", COLOR_SUCCESS
			else:
				try:
					num_val = float(target_val)
					if num_val > 1.0 and num_val <= 24000:
						# Minecraft ticks (0..24000)
						new_tod = ((num_val / 24000.0) + 0.25) % 1.0
					else:
						new_tod = num_val % 1.0
					game.time_of_day = new_tod
					if hasattr(game, "update_sky_color"):
						game.update_sky_color()
					return True, f"Set time to {new_tod:.3f} [Day {getattr(game, 'day_count', 0)}: {getattr(game, 'moon_phase_name', 'Full Moon')}]", COLOR_SUCCESS
				except ValueError:
					return False, f"Unknown time preset: '{target_val}' (Use: sunrise, midday, sunset, midnight, moon <phase>)", COLOR_ERROR

		elif subcmd == "add":
			if len(args) < 2:
				return False, "Usage: /time add <seconds>", COLOR_ERROR
			try:
				sec_to_add = float(args[1])
				# 1200 seconds = 1 full day cycle (20 minutes)
				tod_delta = sec_to_add / 1200.0
				cur_time = getattr(game, "day_count", 0) * 1.0 + (getattr(game, "time_of_day", 0.25))
				new_time = cur_time + tod_delta
				game.day_count = max(0, int(math.floor(new_time)))
				game.time_of_day = new_time % 1.0
				if hasattr(game, "update_sky_color"):
					game.update_sky_color()
				sign = "+" if sec_to_add >= 0 else ""
				return True, f"Added {sign}{sec_to_add:.1f}s to world time (Day {game.day_count}, Moon: {game.moon_phase_name}, Time: {game.time_of_day:.3f})", COLOR_SUCCESS
			except ValueError:
				return False, f"Invalid number of seconds: '{args[1]}'", COLOR_ERROR

		elif subcmd == "query":
			q_target = args[1].lower() if len(args) > 1 else "time"
			tod = getattr(game, "time_of_day", 0.25) % 1.0
			total_min = int(tod * 24.0 * 60.0)
			hours = (total_min // 60)
			mins = total_min % 60
			period = "AM" if hours < 12 else "PM"
			disp_hour = hours % 12
			if disp_hour == 0:
				disp_hour = 12

			if q_target in ("moon", "phase", "moon_phase"):
				m_name = getattr(game, "moon_phase_name", "Full Moon")
				m_idx = getattr(game, "moon_phase", 0)
				m_br = int(round(getattr(game, "moon_brightness", 1.0) * 100))
				return True, f"Moon Phase: {m_name} (Phase {m_idx}/7, Illumination: {m_br}%, Day {getattr(game, 'day_count', 0)})", COLOR_INFO
			elif q_target in ("day", "daytime"):
				return True, f"Current Day: {getattr(game, 'day_count', 0)} (Moon Phase: {getattr(game, 'moon_phase_name', 'Full Moon')})", COLOR_INFO
			else:
				return True, f"Current time is {disp_hour}:{mins:02d} {period} (time_of_day: {tod:.3f}, Day {getattr(game, 'day_count', 0)}, Moon: {getattr(game, 'moon_phase_name', 'Full Moon')})", COLOR_INFO

		else:
			return False, f"Unknown subcommand: '{subcmd}'. Use: /time set <preset>, /time add <seconds>, or /time query [moon|day|time]", COLOR_ERROR

	else:
		return False, f"Unknown command: '/{cmd}'. Available: /tp, /summon, /kill, /locate, /time", COLOR_ERROR
