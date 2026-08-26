import ctypes
import pyglet

import pyglet.gl as gl

FOLIAGE_TEXTURE_TINTS = {
	"leaves_oak": (89, 201, 53),
	"leaves": (89, 201, 53),
	"leaves_birch": (128, 195, 65),
	"leaves_spruce": (75, 140, 75),
	"leaves_jungle": (48, 205, 25),
	"leaves_acacia": (165, 195, 55),
	"leaves_big_oak": (55, 160, 20),
	"fern": (85, 190, 60),
	"vine": (50, 185, 30),
	"tallgrass": (117, 176, 73),
	"waterlily": (45, 125, 45),
	"grass": (115, 195, 65),
	"grass_top": (115, 195, 65),
	"grass_side_overlay": (115, 195, 65),
}

class Texture_manager:
	def __init__(self, texture_width, texture_height, max_textures):
		self.texture_width = texture_width
		self.texture_height = texture_height

		self.max_textures = max_textures

		self.textures = []

		self.texture_array = gl.GLuint(0)
		gl.glGenTextures(1, self.texture_array)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.texture_array)

		gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
		gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
		gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
		gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

		gl.glTexImage3D(
			gl.GL_TEXTURE_2D_ARRAY, 0, gl.GL_RGBA,
			self.texture_width, self.texture_height, self.max_textures,
			0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
	
	def generate_mipmaps(self):
		gl.glGenerateMipmap(gl.GL_TEXTURE_2D_ARRAY)
	
	def add_texture(self, texture):
		if not texture in self.textures:
			self.textures.append(texture)

			raw_image = pyglet.image.load(f"textures/{texture}.png")
			if raw_image.height > self.texture_height:
				texture_image = raw_image.get_region(0, raw_image.height - self.texture_height, self.texture_width, self.texture_height).get_image_data()
			else:
				texture_image = raw_image.get_image_data()

			raw_bytes = bytearray(texture_image.get_data("RGBA", texture_image.width * 4))
			if texture in FOLIAGE_TEXTURE_TINTS:
				tr, tg, tb = FOLIAGE_TEXTURE_TINTS[texture]
				for i in range(0, len(raw_bytes), 4):
					a = raw_bytes[i+3]
					if a > 0:
						r, g, b = raw_bytes[i], raw_bytes[i+1], raw_bytes[i+2]
						# If pixel is greyscale, apply foliage tint
						if abs(r - g) <= 8 and abs(g - b) <= 8:
							grey = (r * 0.299 + g * 0.587 + b * 0.114) / 135.0
							raw_bytes[i]   = max(0, min(255, int(tr * grey)))
							raw_bytes[i+1] = max(0, min(255, int(tg * grey)))
							raw_bytes[i+2] = max(0, min(255, int(tb * grey)))

			gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.texture_array)

			c_data = (gl.GLubyte * len(raw_bytes))(*raw_bytes)
			gl.glTexSubImage3D(
				gl.GL_TEXTURE_2D_ARRAY, 0,
				0, 0, self.textures.index(texture),
				self.texture_width, self.texture_height, 1,
				gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
				c_data)