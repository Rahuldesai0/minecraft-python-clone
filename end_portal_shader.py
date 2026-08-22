"""
End Portal Infinite Parallax Void Shader & Renderer
---------------------------------------------------
Implements the authentic Minecraft Java Edition End Portal celestial visual effect:
- Multi-layer procedural celestial parallax with shifting starfields and deep cosmic nebulas.
- Animated 3D depth perception based on camera translation and viewing angle.
- Seamless spanning across contiguous 3x3 portal blocks without visible tile seams.
"""

import math
import ctypes
import pyglet
import pyglet.gl as gl

PORTAL_VERT_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec2 a_texcoord;

uniform mat4 matrix;
uniform vec3 u_camera_pos;

out vec3 v_world_pos;
out vec2 v_texcoord;
out vec3 v_view_dir;

void main() {
    v_world_pos = a_position;
    v_texcoord = a_texcoord;
    v_view_dir = a_position - u_camera_pos;
    gl_Position = matrix * vec4(a_position, 1.0);
}
"""

PORTAL_FRAG_SHADER = """
#version 330 core
in vec3 v_world_pos;
in vec2 v_texcoord;
in vec3 v_view_dir;

uniform float u_time;
uniform vec3 u_camera_pos;

out vec4 fragColor;

// Procedural hash for celestial star generation
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float star_layer(vec2 uv, float scale, float threshold) {
    vec2 gv = fract(uv * scale) - 0.5;
    vec2 id = floor(uv * scale);
    float n = hash(id);
    if (n > threshold) {
        float d = length(gv);
        float brightness = (n - threshold) / (1.0 - threshold);
        float star = smoothstep(0.12, 0.0, d) * brightness;
        return star;
    }
    return 0.0;
}

void main() {
    vec3 dir = normalize(v_view_dir);
    
    // Deep cosmic background gradient
    vec3 base_color = vec3(0.025, 0.008, 0.045);
    
    // Multi-depth parallax star layers
    vec3 star_color = vec3(0.0);
    
    // Layer 1: Distant slowly drifting stars
    vec2 uv1 = v_world_pos.xz * 0.18 + dir.xz * 1.8 + vec2(u_time * 0.015, u_time * 0.010);
    float s1 = star_layer(uv1, 14.0, 0.88);
    star_color += vec3(0.55, 0.25, 0.90) * s1 * 1.5;
    
    // Layer 2: Medium depth cyan/teal stars
    vec2 uv2 = v_world_pos.xz * 0.32 + dir.xz * 3.2 + vec2(-u_time * 0.020, u_time * 0.018);
    float s2 = star_layer(uv2, 10.0, 0.90);
    star_color += vec3(0.20, 0.85, 0.75) * s2 * 1.8;
    
    // Layer 3: Foreground bright magenta/purple stars
    vec2 uv3 = v_world_pos.xz * 0.55 + dir.xz * 5.0 + vec2(u_time * 0.028, -u_time * 0.022);
    float s3 = star_layer(uv3, 7.0, 0.92);
    star_color += vec3(0.95, 0.40, 1.00) * s3 * 2.2;
    
    // Layer 4: Deep drifting celestial nebula glow
    vec2 uv4 = v_world_pos.xz * 0.08 + dir.xz * 0.9 + vec2(sin(u_time * 0.05) * 0.1, cos(u_time * 0.04) * 0.1);
    float n1 = hash(floor(uv4 * 4.0));
    vec3 nebula = vec3(0.12, 0.03, 0.18) * (sin(uv4.x * 3.0 + u_time * 0.1) * 0.5 + 0.5) * (cos(uv4.y * 3.0) * 0.5 + 0.5);
    
    vec3 final_color = base_color + nebula + star_color;
    fragColor = vec4(final_color, 1.0);
}
"""


class EndPortalRenderer:
	"""Renders active 3D End Portal horizontal plane blocks with celestial void shader."""
	def __init__(self, world):
		self.world = world
		self.shader_program = None
		self.initialized = False
		self.vao = None
		self.vbo = None
		self.time_accum = 0.0

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(PORTAL_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(PORTAL_FRAG_SHADER, 'fragment')
			self.shader_program = pyglet.graphics.shader.ShaderProgram(vs, fs)

			self.vao = gl.GLuint()
			gl.glGenVertexArrays(1, ctypes.byref(self.vao))
			self.vbo = gl.GLuint()
			gl.glGenBuffers(1, ctypes.byref(self.vbo))

			gl.glBindVertexArray(self.vao)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)

			# Position (location = 0, 3 floats)
			gl.glEnableVertexAttribArray(0)
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 5 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

			# TexCoords (location = 1, 2 floats)
			gl.glEnableVertexAttribArray(1)
			gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 5 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(3 * ctypes.sizeof(ctypes.c_float)))

			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
			gl.glBindVertexArray(0)
			self.initialized = True
		except Exception:
			pass

	def update(self, dt):
		self.time_accum += dt

	def draw(self, camera, portal_blocks):
		"""
		Renders horizontal infinite-depth portal surfaces for all visible portal blocks.
		portal_blocks: list or set of (bx, by, bz) coordinates containing block 183.
		"""
		if not portal_blocks:
			return

		self._init_gl()
		if not self.initialized or not self.shader_program:
			return

		vertex_data = []
		# End Portal horizontal plane sits at Y = 0.75 in local block coordinates (Y = by + 0.25)
		for bx, by, bz in portal_blocks:
			py = by + 0.25
			x1, x2 = bx - 0.5, bx + 0.5
			z1, z2 = bz - 0.5, bz + 0.5

			# 2 Triangles forming horizontal quad
			# Triangle 1
			vertex_data.extend([x1, py, z1,  0.0, 0.0])
			vertex_data.extend([x2, py, z1,  1.0, 0.0])
			vertex_data.extend([x2, py, z2,  1.0, 1.0])
			# Triangle 2
			vertex_data.extend([x1, py, z1,  0.0, 0.0])
			vertex_data.extend([x2, py, z2,  1.0, 1.0])
			vertex_data.extend([x1, py, z2,  0.0, 1.0])

		if not vertex_data:
			return

		v_count = len(vertex_data) // 5
		c_data = (ctypes.c_float * len(vertex_data))(*vertex_data)

		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)

		self.shader_program.use()

		# Bind camera transformation matrix
		if hasattr(camera, 'matrix'):
			gl.glUniformMatrix4fv(
				gl.glGetUniformLocation(self.shader_program.id, b"matrix"),
				1, gl.GL_FALSE,
				(gl.GLfloat * 16)(*camera.matrix)
			)
		elif hasattr(camera, 'mv_matrix'):
			mvp_matrix = camera.mv_matrix * camera.p_matrix
			flat_matrix = [val for row in mvp_matrix.data for val in row]
			gl.glUniformMatrix4fv(
				gl.glGetUniformLocation(self.shader_program.id, b"matrix"),
				1, gl.GL_FALSE,
				(gl.GLfloat * 16)(*flat_matrix)
			)

		# Camera position and animated time uniforms
		cam_x, cam_y, cam_z = camera.position
		gl.glUniform3f(gl.glGetUniformLocation(self.shader_program.id, b"u_camera_pos"), cam_x, cam_y, cam_z)
		gl.glUniform1f(gl.glGetUniformLocation(self.shader_program.id, b"u_time"), self.time_accum)

		gl.glBindVertexArray(self.vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_data), c_data, gl.GL_DYNAMIC_DRAW)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, v_count)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
		gl.glBindVertexArray(0)
		self.shader_program.stop()
		gl.glEnable(gl.GL_CULL_FACE)
