#version 330

layout(location = 0) in vec3 vertex_position;
layout(location = 1) in vec3 tex_coords;
layout(location = 2) in vec3 light_and_shading; // x: sky_light (0-15), y: block_light (0-15), z: face_shading (0-1)

out vec3 local_position;
out vec3 interpolated_tex_coords;
out vec3 interpolated_light_and_shading;

uniform mat4 matrix;

void main(void) {
	local_position = vertex_position;
	interpolated_tex_coords = tex_coords;
	interpolated_light_and_shading = light_and_shading;
	gl_Position = matrix * vec4(vertex_position, 1.0);
}