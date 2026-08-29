import math
import random
import ctypes
import os
import pyglet
import pyglet.gl as gl

# =============================================================================
# CLASSIC 3D BLOCKY CLOUD SHADERS (BLOCK LIGHTING MODE)
# =============================================================================
BLOCKY_CLOUD_VERT_SRC = """#version 330
layout(location = 0) in vec3 a_Position;
layout(location = 1) in vec4 a_Color;

uniform mat4 u_MVPMatrix;

out vec4 v_Color;
out vec3 v_WorldPos;

void main(void) {
    v_Color = a_Color;
    v_WorldPos = a_Position;
    gl_Position = u_MVPMatrix * vec4(a_Position, 1.0);
}
"""

BLOCKY_CLOUD_FRAG_SRC = """#version 330
in vec4 v_Color;
in vec3 v_WorldPos;

uniform vec3 u_CameraPos;
uniform float u_RenderDist;

out vec4 fragColor;

void main(void) {
    float dist = length(v_WorldPos.xz - u_CameraPos.xz);
    // Smooth horizon fade near the edge of cloud render distance
    float alpha_fade = 1.0 - smoothstep(u_RenderDist * 0.75, u_RenderDist, dist);
    vec4 col = v_Color;
    col.a *= alpha_fade;
    if (col.a < 0.01) {
        discard;
    }
    fragColor = col;
}
"""

def compile_shader(shader_type, src):
    s = gl.glCreateShader(shader_type)
    src_bytes = src.encode('utf-8')
    source_length = ctypes.c_int(len(src_bytes) + 1)
    source_buffer = ctypes.create_string_buffer(src_bytes)
    buffer_pointer = ctypes.cast(
        ctypes.pointer(ctypes.pointer(source_buffer)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_char))
    )
    gl.glShaderSource(s, 1, buffer_pointer, ctypes.byref(source_length))
    gl.glCompileShader(s)
    status = gl.GLint()
    gl.glGetShaderiv(s, gl.GL_COMPILE_STATUS, ctypes.byref(status))
    if not status.value:
        log_len = gl.GLint()
        gl.glGetShaderiv(s, gl.GL_INFO_LOG_LENGTH, ctypes.byref(log_len))
        log_buf = ctypes.create_string_buffer(log_len.value)
        gl.glGetShaderInfoLog(s, log_len, None, log_buf)
        raise RuntimeError(f"Cloud Shader error: {log_buf.value.decode()}")
    return s

def link_program(vert_src, frag_src):
    vs = compile_shader(gl.GL_VERTEX_SHADER, vert_src)
    fs = compile_shader(gl.GL_FRAGMENT_SHADER, frag_src)
    p = gl.glCreateProgram()
    gl.glAttachShader(p, vs)
    gl.glAttachShader(p, fs)
    gl.glLinkProgram(p)
    gl.glDeleteShader(vs)
    gl.glDeleteShader(fs)
    status = gl.GLint()
    gl.glGetProgramiv(p, gl.GL_LINK_STATUS, ctypes.byref(status))
    if not status.value:
        log_len = gl.GLint()
        gl.glGetProgramiv(p, gl.GL_INFO_LOG_LENGTH, ctypes.byref(log_len))
        log_buf = ctypes.create_string_buffer(log_len.value)
        gl.glGetProgramInfoLog(p, log_len, None, log_buf)
        raise RuntimeError(f"Cloud Program error: {log_buf.value.decode()}")
    return p


class CloudManager:
    """
    Overworld Classic 3D Blocky Cloud System (Block Lighting Mode):
    - Separate, distinct small fluffy cloud islands separated by clear open sky.
    - Cloud Level: Y = 128.0 (accessible by flying or building up).
    - 100% Complete, solid 3D faces on all sides with perfect outward winding normals.
    - Horizontal wind drift: Moves continuously along +X across the sky.
    """
    def __init__(self):
        self.cloud_y = 128.0
        self.cloud_thickness = 4.0
        self.cell_size = 12.0 # 12 meters per blocky cloud voxel
        self.grid_radius = 24 # 24 cells radius (approx 288m view distance)
        self.wind_speed = 2.4 # meters per second horizontal drift

        # 64x64 periodic map with discrete small cloud islands separated by clear sky
        self.map_size = 64
        self.cloud_map = self._generate_separate_small_clouds(self.map_size)

        # GL state
        self.initialized = False
        self.blocky_prog = None
        self.blocky_vao = None
        self.blocky_vbo_pos = None
        self.blocky_vbo_col = None
        self.blocky_ibo = None
        self.blocky_index_count = 0

    def _generate_separate_small_clouds(self, size):
        """Generates distinct, separate small fluffy cloud islands separated by open sky."""
        grid = [[False for _ in range(size)] for _ in range(size)]
        rng = random.Random(1234)

        # Space out cloud spawn seeds with large clear gaps
        step = 9
        for sy in range(0, size, step):
            for sx in range(0, size, step):
                cx = (sx + rng.randint(0, 4)) % size
                cy = (sy + rng.randint(0, 4)) % size

                # 75% chance to spawn a discrete cloud island at this seed
                if rng.random() < 0.75:
                    w = rng.randint(2, 5) # 2 to 5 cells wide
                    h = rng.randint(2, 4) # 2 to 4 cells long

                    for dy in range(h):
                        for dx in range(w):
                            # Skip some corner cells for organic puffiness
                            if (dx == 0 or dx == w - 1) and (dy == 0 or dy == h - 1):
                                if rng.random() < 0.40:
                                    continue

                            gx = (cx + dx) % size
                            gy = (cy + dy) % size
                            grid[gy][gx] = True

        return grid

    def init_gl(self):
        if self.initialized:
            return
        try:
            self.blocky_prog = link_program(BLOCKY_CLOUD_VERT_SRC, BLOCKY_CLOUD_FRAG_SRC)
            self.u_blocky_mvp = gl.glGetUniformLocation(self.blocky_prog, b"u_MVPMatrix")
            self.u_blocky_campos = gl.glGetUniformLocation(self.blocky_prog, b"u_CameraPos")
            self.u_blocky_renddist = gl.glGetUniformLocation(self.blocky_prog, b"u_RenderDist")

            self.blocky_vao = gl.GLuint(0)
            gl.glGenVertexArrays(1, ctypes.byref(self.blocky_vao))
            self.blocky_vbo_pos = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.blocky_vbo_pos))
            self.blocky_vbo_col = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.blocky_vbo_col))
            self.blocky_ibo = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.blocky_ibo))

            self.initialized = True
        except Exception as e:
            print(f"[CloudManager Init Error]: {e}")

    def _build_blocky_mesh(self, cam_x, cam_z, total_time, time_of_day):
        """Constructs 100% complete 3D voxel cuboids with perfect outward CCW winding normals."""
        positions = []
        colors = []
        indices = []

        tod = time_of_day % 1.0
        sun_y = math.cos((tod - 0.5) * math.tau)
        day_factor = max(0.0, min(1.0, (sun_y + 0.15) / 0.30))
        horizon_factor = 1.0 - min(1.0, abs(sun_y) / 0.30)
        horizon_factor = horizon_factor * horizon_factor

        # Celestial lighting tint
        day_col = (1.0, 1.0, 1.0)
        sunset_col = (1.0, 0.68, 0.45)
        night_col = (0.16, 0.20, 0.34)

        base_tint = [
            day_col[i] * day_factor * (1.0 - horizon_factor) +
            sunset_col[i] * day_factor * horizon_factor +
            night_col[i] * (1.0 - day_factor)
            for i in range(3)
        ]

        # Authentic Minecraft face shading multipliers
        top_mult = 1.00
        bottom_mult = 0.70
        side_mult = 0.85

        c_top = (base_tint[0] * top_mult, base_tint[1] * top_mult, base_tint[2] * top_mult, 0.85)
        c_bottom = (base_tint[0] * bottom_mult, base_tint[1] * bottom_mult, base_tint[2] * bottom_mult, 0.85)
        c_side = (base_tint[0] * side_mult, base_tint[1] * side_mult, base_tint[2] * side_mult, 0.85)

        # Wind drift offset along +X
        wind_x = total_time * self.wind_speed

        center_cell_x = int(math.floor((cam_x - wind_x) / self.cell_size))
        center_cell_z = int(math.floor(cam_z / self.cell_size))

        rad = self.grid_radius
        y_bot = self.cloud_y
        y_top = self.cloud_y + self.cloud_thickness
        cell_w = self.cell_size

        v_count = 0

        for dz in range(-rad, rad + 1):
            cz = center_cell_z + dz
            mz = cz % self.map_size

            for dx in range(-rad, rad + 1):
                cx = center_cell_x + dx
                mx = cx % self.map_size

                if not self.cloud_map[mz][mx]:
                    continue

                x0 = cx * cell_w + wind_x
                x1 = x0 + cell_w
                z0 = cz * cell_w
                z1 = z0 + cell_w

                has_north = self.cloud_map[(mz - 1) % self.map_size][mx]
                has_south = self.cloud_map[(mz + 1) % self.map_size][mx]
                has_west  = self.cloud_map[mz][(mx - 1) % self.map_size]
                has_east  = self.cloud_map[mz][(mx + 1) % self.map_size]

                # 1. TOP FACE (+Y) - CCW outward normal: (0, +1, 0)
                positions.extend([
                    x0, y_top, z1,
                    x1, y_top, z1,
                    x1, y_top, z0,
                    x0, y_top, z0,
                ])
                colors.extend(list(c_top) * 4)
                indices.extend([v_count, v_count + 1, v_count + 2, v_count, v_count + 2, v_count + 3])
                v_count += 4

                # 2. BOTTOM FACE (-Y) - CCW outward normal: (0, -1, 0)
                positions.extend([
                    x0, y_bot, z0,
                    x1, y_bot, z0,
                    x1, y_bot, z1,
                    x0, y_bot, z1,
                ])
                colors.extend(list(c_bottom) * 4)
                indices.extend([v_count, v_count + 1, v_count + 2, v_count, v_count + 2, v_count + 3])
                v_count += 4

                # 3. NORTH FACE (-Z) - CCW outward normal: (0, 0, -1)
                if not has_north:
                    positions.extend([
                        x1, y_bot, z0,
                        x0, y_bot, z0,
                        x0, y_top, z0,
                        x1, y_top, z0,
                    ])
                    colors.extend(list(c_side) * 4)
                    indices.extend([v_count, v_count + 1, v_count + 2, v_count, v_count + 2, v_count + 3])
                    v_count += 4

                # 4. SOUTH FACE (+Z) - CCW outward normal: (0, 0, +1)
                if not has_south:
                    positions.extend([
                        x0, y_bot, z1,
                        x1, y_bot, z1,
                        x1, y_top, z1,
                        x0, y_top, z1,
                    ])
                    colors.extend(list(c_side) * 4)
                    indices.extend([v_count, v_count + 1, v_count + 2, v_count, v_count + 2, v_count + 3])
                    v_count += 4

                # 5. WEST FACE (-X) - CCW outward normal: (-1, 0, 0)
                if not has_west:
                    positions.extend([
                        x0, y_bot, z0,
                        x0, y_bot, z1,
                        x0, y_top, z1,
                        x0, y_top, z0,
                    ])
                    colors.extend(list(c_side) * 4)
                    indices.extend([v_count, v_count + 1, v_count + 2, v_count, v_count + 2, v_count + 3])
                    v_count += 4

                # 6. EAST FACE (+X) - CCW outward normal: (+1, 0, 0)
                if not has_east:
                    positions.extend([
                        x1, y_bot, z1,
                        x1, y_bot, z0,
                        x1, y_top, z0,
                        x1, y_top, z1,
                    ])
                    colors.extend(list(c_side) * 4)
                    indices.extend([v_count, v_count + 1, v_count + 2, v_count, v_count + 2, v_count + 3])
                    v_count += 4

        # Upload mesh to GPU
        gl.glBindVertexArray(self.blocky_vao)

        pos_data = (gl.GLfloat * len(positions))(*positions)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.blocky_vbo_pos)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(pos_data), pos_data, gl.GL_DYNAMIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glEnableVertexAttribArray(0)

        col_data = (gl.GLfloat * len(colors))(*colors)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.blocky_vbo_col)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(col_data), col_data, gl.GL_DYNAMIC_DRAW)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glEnableVertexAttribArray(1)

        idx_data = (gl.GLuint * len(indices))(*indices)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.blocky_ibo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(idx_data), idx_data, gl.GL_DYNAMIC_DRAW)

        self.blocky_index_count = len(indices)
        gl.glBindVertexArray(0)

    def draw(self, camera, lighting_mode="BLOCK", time_of_day=0.25, total_time=0.0):
        """
        Renders Overworld 3D Blocky Clouds at Y=128 in Block Lighting Mode.
        In Shaders / Ray Traced Mode, realistic clouds are integrated directly into the sky dome.
        """
        is_shader_mode = (lighting_mode in (1, "RAYTRACED", "SHADER"))
        if is_shader_mode:
            return # Handled photorealistically as part of the sky dome in overworld_sky.py

        if not self.initialized:
            self.init_gl()
        if not self.initialized:
            return

        cam_x, cam_y, cam_z = camera.position

        try:
            mvp_matrix = camera.mv_matrix * camera.p_matrix
            flat_mvp = sum(mvp_matrix.data, [])
            mvp_data = (gl.GLfloat * 16)(*flat_mvp)
        except Exception as e:
            return

        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glDepthMask(gl.GL_FALSE)

        # Backface culling ensures clean, seamless cloud surfaces with ZERO interior partition lines
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)

        # Build dynamic separate small blocky clouds with complete outward faces
        self._build_blocky_mesh(cam_x, cam_z, total_time, time_of_day)

        if getattr(self, "blocky_index_count", 0) > 0:
            gl.glUseProgram(self.blocky_prog)
            gl.glUniformMatrix4fv(self.u_blocky_mvp, 1, gl.GL_FALSE, mvp_data)
            gl.glUniform3f(self.u_blocky_campos, cam_x, cam_y, cam_z)
            gl.glUniform1f(self.u_blocky_renddist, float(self.grid_radius * self.cell_size))

            gl.glBindVertexArray(self.blocky_vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self.blocky_index_count, gl.GL_UNSIGNED_INT, 0)
            gl.glBindVertexArray(0)
            gl.glUseProgram(0)

        # Restore GL state
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glEnable(gl.GL_CULL_FACE)


cloud_manager = CloudManager()
