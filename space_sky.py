import math
import random
import ctypes
import os
import pyglet
import pyglet.gl as gl

SPACE_VERT_SRC = """#version 330
layout(location = 0) in vec3 a_Position;
layout(location = 1) in vec2 a_TexCoord;
layout(location = 2) in vec4 a_Color;

uniform mat4 u_MVPMatrix;

out vec2 v_TexCoord;
out vec4 v_Color;

void main(void) {
    v_TexCoord = a_TexCoord;
    v_Color = a_Color;
    gl_Position = u_MVPMatrix * vec4(a_Position, 1.0);
}
"""

SPACE_FRAG_SRC = """#version 330
in vec2 v_TexCoord;
in vec4 v_Color;

uniform sampler2D u_Texture;

out vec4 fragColor;

void main(void) {
    vec4 tex = texture(u_Texture, v_TexCoord);
    vec4 col = tex * v_Color;
    if (col.a < 0.003) {
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
        raise RuntimeError(f"Space Shader compilation error: {log_buf.value.decode()}")
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
        raise RuntimeError(f"Space Program link error: {log_buf.value.decode()}")
    return p

def load_gl_texture(path):
    if not os.path.exists(path):
        return None
    image = pyglet.image.load(path)
    image_data = image.get_image_data()
    width = image_data.width
    height = image_data.height
    raw_data = image_data.get_data("RGBA", width * 4)

    tex_id = gl.GLuint(0)
    gl.glGenTextures(1, ctypes.byref(tex_id))
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

    c_data = (gl.GLubyte * len(raw_data)).from_buffer_copy(raw_data)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
        width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, c_data
    )
    gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id


class SpaceSkyRenderer:
    """Renders breathtaking, ultra-realistic, non-blocky deep-space celestial objects in the End dimension."""
    def __init__(self):
        self.program = None
        self.u_mvp = -1
        self.u_tex = -1

        self.vao = None
        self.vbo_pos = None
        self.vbo_tex = None
        self.vbo_col = None
        self.ibo = None

        self.planet_tex = None
        self.galaxy_tex = None
        self.nebula_tex = None
        self.star_tex = None
        self.blackhole_tex = None
        self.initialized = False

        # Generate persistent realistic starfield
        rng = random.Random(998877)
        self.stars = []
        for _ in range(480):
            u = rng.uniform(-1.0, 1.0)
            phi = rng.uniform(0.0, math.tau)
            r_xy = math.sqrt(max(0.0, 1.0 - u * u))
            x = r_xy * math.cos(phi)
            y = u
            z = r_xy * math.sin(phi)
            if y < -0.15:
                y = -y * 0.50 + 0.10

            roll = rng.random()
            if roll < 0.35:
                color = (1.0, 1.0, 1.0)       # Brilliant Pure White
            elif roll < 0.60:
                color = (0.75, 0.90, 1.0)     # O-type Electric Cyan
            elif roll < 0.80:
                color = (0.92, 0.72, 1.0)     # Amethyst Violet
            elif roll < 0.94:
                color = (1.0, 0.88, 0.65)     # K-type Solar Gold
            else:
                color = (1.0, 0.50, 0.85)     # Magnetar / Pulsar Magenta

            star_size = rng.uniform(1.8, 4.5)
            twinkle_freq = rng.uniform(1.2, 3.8)
            twinkle_phase = rng.uniform(0.0, math.tau)
            base_alpha = rng.uniform(0.70, 1.0)

            self.stars.append({
                "dir": (x, y, z),
                "color": color,
                "size": star_size,
                "freq": twinkle_freq,
                "phase": twinkle_phase,
                "base_alpha": base_alpha
            })

    def init_gl(self):
        if self.initialized:
            return
        try:
            self.program = link_program(SPACE_VERT_SRC, SPACE_FRAG_SRC)
            self.u_mvp = gl.glGetUniformLocation(self.program, b"u_MVPMatrix")
            self.u_tex = gl.glGetUniformLocation(self.program, b"u_Texture")

            self.vao = gl.GLuint(0)
            gl.glGenVertexArrays(1, ctypes.byref(self.vao))

            self.vbo_pos = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.vbo_pos))
            self.vbo_tex = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.vbo_tex))
            self.vbo_col = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.vbo_col))
            self.ibo = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.ibo))

            # Load high-resolution space textures
            tex_dir = 'd:/Programs/tp/textures'
            self.planet_tex = load_gl_texture(os.path.join(tex_dir, "end_planet.png"))
            self.galaxy_tex = load_gl_texture(os.path.join(tex_dir, "end_galaxy.png"))
            self.nebula_tex = load_gl_texture(os.path.join(tex_dir, "end_nebula.png"))
            self.star_tex = load_gl_texture(os.path.join(tex_dir, "space_star.png"))
            self.blackhole_tex = load_gl_texture(os.path.join(tex_dir, "end_blackhole.png"))

            self.initialized = True
        except Exception as e:
            print(f"[SpaceSkyRenderer Init Error]: {e}")

    def render(self, camera, total_time=0.0):
        if not self.initialized:
            self.init_gl()
        if not self.initialized or self.program is None:
            return

        cam_x, cam_y, cam_z = camera.position
        
        # Calculate full MVP matrix correctly from camera
        try:
            mvp_matrix = camera.mv_matrix * camera.p_matrix
            flat_mvp = sum(mvp_matrix.data, [])
            mvp_data = (gl.GLfloat * 16)(*flat_mvp)
        except Exception as e:
            print(f"[SpaceSky Matrix Error]: {e}")
            return

        gl.glUseProgram(self.program)
        gl.glUniformMatrix4fv(self.u_mvp, 1, gl.GL_FALSE, mvp_data)
        gl.glUniform1i(self.u_tex, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)

        gl.glEnable(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_CULL_FACE)

        gl.glBindVertexArray(self.vao)

        R = 360.0

        def build_billboard_quad(center_dir, size_w, size_h, roll_ang=0.0, color=(1.0, 1.0, 1.0, 1.0)):
            dx, dy, dz = center_dir
            len_d = math.sqrt(dx*dx + dy*dy + dz*dz)
            dx, dy, dz = dx/len_d, dy/len_d, dz/len_d

            cx = cam_x + dx * R
            cy = cam_y + dy * R
            cz = cam_z + dz * R

            up_ref = (0.0, 1.0, 0.0) if abs(dy) < 0.95 else (1.0, 0.0, 0.0)
            rx = dy * up_ref[2] - dz * up_ref[1]
            ry = dz * up_ref[0] - dx * up_ref[2]
            rz = dx * up_ref[1] - dy * up_ref[0]
            len_r = math.sqrt(rx*rx + ry*ry + rz*rz)
            rx, ry, rz = rx/len_r, ry/len_r, rz/len_r

            ux = ry * dz - rz * dy
            uy = rz * dx - rx * dz
            uz = rx * dy - ry * dx

            if roll_ang != 0.0:
                c_roll = math.cos(roll_ang)
                s_roll = math.sin(roll_ang)
                nrx = rx * c_roll - ux * s_roll
                nry = ry * c_roll - uy * s_roll
                nrz = rz * c_roll - uz * s_roll
                nux = rx * s_roll + ux * c_roll
                nuy = ry * s_roll + uy * c_roll
                nuz = rz * s_roll + uz * c_roll
                rx, ry, rz = nrx, nry, nrz
                ux, uy, uz = nux, nuy, nuz

            hw = size_w * 0.5
            hh = size_h * 0.5

            p0 = (cx - rx * hw - ux * hh, cy - ry * hw - uy * hh, cz - rz * hw - uz * hh)
            p1 = (cx + rx * hw - ux * hh, cy + ry * hw - uy * hh, cz + rz * hw - uz * hh)
            p2 = (cx + rx * hw + ux * hh, cy + ry * hw + uy * hh, cz + rz * hw + uz * hh)
            p3 = (cx - rx * hw + ux * hh, cy - ry * hw + uy * hh, cz - rz * hw - uz * hh)

            positions = [
                p0[0], p0[1], p0[2],
                p1[0], p1[1], p1[2],
                p2[0], p2[1], p2[2],
                p3[0], p3[1], p3[2],
            ]
            tex_coords = [
                0.0, 0.0,
                1.0, 0.0,
                1.0, 1.0,
                0.0, 1.0,
            ]
            colors = list(color) * 4
            indices = [0, 1, 2, 0, 2, 3]
            return positions, tex_coords, colors, indices

        def upload_and_draw(positions, tex_coords, colors, indices):
            if not indices: return
            pos_data = (gl.GLfloat * len(positions))(*positions)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(pos_data), pos_data, gl.GL_STREAM_DRAW)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
            gl.glEnableVertexAttribArray(0)

            tex_data = (gl.GLfloat * len(tex_coords))(*tex_coords)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tex_data), tex_data, gl.GL_STREAM_DRAW)
            gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
            gl.glEnableVertexAttribArray(1)

            col_data = (gl.GLfloat * len(colors))(*colors)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_col)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(col_data), col_data, gl.GL_STREAM_DRAW)
            gl.glVertexAttribPointer(2, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
            gl.glEnableVertexAttribArray(2)

            idx_data = (gl.GLuint * len(indices))(*indices)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ibo)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(idx_data), idx_data, gl.GL_STREAM_DRAW)

            gl.glDrawElements(gl.GL_TRIANGLES, len(indices), gl.GL_UNSIGNED_INT, 0)

        # -------------------------------------------------------------
        # 1. Interstellar Nebula Dust Clouds (Sweeping space gas)
        # -------------------------------------------------------------
        if self.nebula_tex:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Additive cosmic glow
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.nebula_tex)
            neb_pos, neb_tex, neb_col, neb_idx = [], [], [], []
            v_count = 0
            
            nebula_configs = [
                ((0.65, 0.45, -0.60), 220.0, 220.0, 0.4, (0.85, 0.45, 1.0, 0.55)),
                ((-0.70, 0.55, 0.45), 240.0, 240.0, -0.6, (0.45, 0.75, 1.0, 0.50)),
                ((0.15, 0.85, 0.50), 210.0, 210.0, 1.2, (0.95, 0.40, 0.80, 0.45)),
                ((-0.45, 0.35, -0.80), 190.0, 190.0, -1.0, (0.60, 0.50, 1.0, 0.50)),
            ]
            for c_dir, sw, sh, r_ang, col in nebula_configs:
                p, t, c, idxs = build_billboard_quad(c_dir, sw, sh, roll_ang=r_ang, color=col)
                neb_pos.extend(p)
                neb_tex.extend(t)
                neb_col.extend(c)
                neb_idx.extend([i + v_count for i in idxs])
                v_count += 4
            upload_and_draw(neb_pos, neb_tex, neb_col, neb_idx)

        # -------------------------------------------------------------
        # 2. Semi-Massive Interstellar Black Hole at Vertical Top (Zenith)
        # -------------------------------------------------------------
        if self.blackhole_tex:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.blackhole_tex)
            bh_dir = (0.0, 1.0, 0.0) # Directly vertical top (Zenith)
            bh_rot = total_time * 0.015
            p, t, c, idxs = build_billboard_quad(bh_dir, 195.0, 195.0, roll_ang=bh_rot, color=(1.0, 1.0, 1.0, 1.0))
            upload_and_draw(p, t, c, idxs)

        # -------------------------------------------------------------
        # 3. Cosmic Spiral Galaxy Core (Rotating galactic vortex)
        # -------------------------------------------------------------
        if self.galaxy_tex:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.galaxy_tex)
            galaxy_dir = (-0.55, 0.58, -0.55)
            galaxy_rot = total_time * 0.020
            p, t, c, idxs = build_billboard_quad(galaxy_dir, 165.0, 165.0, roll_ang=galaxy_rot, color=(1.0, 0.95, 1.0, 0.95))
            upload_and_draw(p, t, c, idxs)

        # -------------------------------------------------------------
        # 4. Giant Photorealistic Ringed Celestial Planet
        # -------------------------------------------------------------
        if self.planet_tex:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA) # Alpha blend realistic planet
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.planet_tex)
            planet_dir = (0.72, 0.42, 0.54)
            p, t, c, idxs = build_billboard_quad(planet_dir, 135.0, 135.0, roll_ang=0.18, color=(1.0, 1.0, 1.0, 1.0))
            upload_and_draw(p, t, c, idxs)

        # -------------------------------------------------------------
        # 4. Twinkling Deep Space Starfield
        # -------------------------------------------------------------
        if self.star_tex:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Additive twinkle
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.star_tex)
            s_pos, s_tex, s_col, s_idx = [], [], [], []
            v_count = 0
            for star in self.stars:
                twinkle = math.sin(total_time * star["freq"] + star["phase"]) * 0.35 + 0.65
                alpha = star["base_alpha"] * twinkle
                cr, cg, cb = star["color"]
                p, t, c, idxs = build_billboard_quad(star["dir"], star["size"], star["size"], color=(cr, cg, cb, alpha))
                s_pos.extend(p)
                s_tex.extend(t)
                s_col.extend(c)
                s_idx.extend([i + v_count for i in idxs])
                v_count += 4
            upload_and_draw(s_pos, s_tex, s_col, s_idx)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)


space_sky_renderer = SpaceSkyRenderer()
