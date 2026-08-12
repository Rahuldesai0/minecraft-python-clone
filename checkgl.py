from vnoise import Noise
_noise_gen = Noise()

# Example usage to generate 2D Perlin noise
def generate_perlin_noise(width, height, scale, octaves, persistence, lacunarity, seed):
    noise_map = []
    for y in range(height):
        row = []
        for x in range(width):
            value = _noise_gen.noise2(x / scale,
                                  y / scale,
                                  octaves=octaves,
                                  persistence=persistence,
                                  lacunarity=lacunarity)
            row.append(value)
        noise_map.append(row)
    return noise_map

# Example parameters
width = 100
height = 100
scale = 50
octaves = 6
persistence = 0.5
lacunarity = 2.0
seed = 0

# Generate Perlin noise map
noise_map = generate_perlin_noise(width, height, scale, octaves, persistence, lacunarity, seed)

# Now you can use the noise_map for whatever purpose you need
print(noise_map)