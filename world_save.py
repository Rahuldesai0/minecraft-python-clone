import os
import json
import gzip
import shutil
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES_DIR = os.path.join(BASE_DIR, 'saves')

def ensure_saves_dir():
	os.makedirs(SAVES_DIR, exist_ok=True)
	return SAVES_DIR

def is_existing_world(folder_name):
	folder_path = os.path.join(SAVES_DIR, folder_name)
	if not os.path.exists(folder_path):
		return False
	if os.path.exists(os.path.join(folder_path, 'level.dat')):
		return True
	chunks_path = os.path.join(folder_path, 'chunks')
	if os.path.exists(chunks_path) and os.listdir(chunks_path):
		return True
	return False

def get_unique_world_name(base_name="New World"):
	ensure_saves_dir()
	base_name = base_name.strip()
	if not base_name:
		base_name = "New World"

	target_name = base_name
	counter = 1
	while is_existing_world(target_name):
		target_name = f"{base_name} ({counter})"
		counter += 1

	return target_name

def list_saved_worlds():
	ensure_saves_dir()
	worlds = []

	if not os.path.exists(SAVES_DIR):
		return worlds

	for item in os.listdir(SAVES_DIR):
		folder_path = os.path.join(SAVES_DIR, item)
		if os.path.isdir(folder_path):
			level_dat = os.path.join(folder_path, 'level.dat')
			if os.path.exists(level_dat):
				try:
					with gzip.open(level_dat, 'rt', encoding='utf-8') as f:
						data = json.load(f)
					data['folder_name'] = item
					worlds.append(data)
				except Exception:
					# Fallback metadata for plain directory
					worlds.append({
						'name': item,
						'folder_name': item,
						'seed': 0,
						'last_played': os.path.getmtime(folder_path),
						'last_played_str': time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(folder_path))),
						'render_distance': 6
					})

	# Sort by last played timestamp descending
	worlds.sort(key=lambda w: w.get('last_played', 0), reverse=True)
	return worlds

def save_world(world_name, seed, player_data, world_data, inventory_data, drops_data=None):
	ensure_saves_dir()
	folder_path = os.path.join(SAVES_DIR, world_name)
	chunks_path = os.path.join(folder_path, 'chunks')
	os.makedirs(chunks_path, exist_ok=True)

	now = time.time()
	now_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))

	level_data = {
		'name': world_name,
		'seed': seed,
		'last_played': now,
		'last_played_str': now_str,
		'player': player_data,
		'world': world_data,
		'inventory': inventory_data,
		'drops': drops_data or []
	}

	level_dat_path = os.path.join(folder_path, 'level.dat')
	with gzip.open(level_dat_path, 'wt', encoding='utf-8', compresslevel=1) as f:
		json.dump(level_data, f, indent=2)

	return folder_path

def load_world(world_name):
	folder_path = os.path.join(SAVES_DIR, world_name)
	level_dat_path = os.path.join(folder_path, 'level.dat')
	if not os.path.exists(level_dat_path):
		return None

	try:
		with gzip.open(level_dat_path, 'rt', encoding='utf-8') as f:
			data = json.load(f)
		data['folder_name'] = world_name
		return data
	except Exception as e:
		print(f"Error loading level.dat for {world_name}: {e}")
		return None

def rename_world(old_name, new_name):
	ensure_saves_dir()
	old_path = os.path.join(SAVES_DIR, old_name)
	if not os.path.exists(old_path):
		return False, "Save folder does not exist"

	new_unique_name = get_unique_world_name(new_name)
	new_path = os.path.join(SAVES_DIR, new_unique_name)

	try:
		# Update level.dat name field first
		level_dat_path = os.path.join(old_path, 'level.dat')
		if os.path.exists(level_dat_path):
			try:
				with gzip.open(level_dat_path, 'rt', encoding='utf-8') as f:
					data = json.load(f)
				data['name'] = new_unique_name
				with gzip.open(level_dat_path, 'wt', encoding='utf-8', compresslevel=1) as f:
					json.dump(data, f, indent=2)
			except Exception:
				pass

		os.rename(old_path, new_path)
		return True, new_unique_name
	except Exception as e:
		return False, str(e)

def delete_world(world_name):
	folder_path = os.path.join(SAVES_DIR, world_name)
	if os.path.exists(folder_path):
		try:
			shutil.rmtree(folder_path)
			return True
		except Exception as e:
			print(f"Error deleting world {world_name}: {e}")
			return False
	return False
