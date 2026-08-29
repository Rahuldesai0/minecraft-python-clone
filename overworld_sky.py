import math
import random
import ctypes
import os
import pyglet
import pyglet.gl as gl

OVERWORLD_SKY_VERT_SRC = """#version 330
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

OVERWORLD_SKY_FRAG_SRC = """#version 330
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
        raise RuntimeError(f"Overworld Sky Shader error: {log_buf.value.decode()}")
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
        raise RuntimeError(f"Overworld Sky Program error: {log_buf.value.decode()}")
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


class OverworldRealisticSkyRenderer:
    """Renders photorealistic Sun, Moon, twinkling Stars, and animated Aurora Borealis for Overworld Shaders."""
    def __init__(self):
        self.program = None
        self.u_mvp = -1
        self.u_tex = -1

        self.vao = None
        self.vbo_pos = None
        self.vbo_tex = None
        self.vbo_col = None
        self.ibo = None

        self.sun_tex = None
        self.moon_tex = None
        self.aurora_tex = None
        self.star_tex = None
        self.initialized = False

        # Generate persistent Overworld night starfield on full 360-degree celestial sphere
        rng = random.Random(13579)
        self.stars = []
        for _ in range(950):
            u = rng.uniform(-1.0, 1.0)
            phi = rng.uniform(0.0, math.tau)
            r_xy = math.sqrt(max(0.0, 1.0 - u * u))
            x = r_xy * math.cos(phi)
            y = u
            z = r_xy * math.sin(phi)

            roll = rng.random()
            if roll < 0.40:
                color = (1.0, 1.0, 1.0)       # Brilliant Pure White
            elif roll < 0.65:
                color = (0.75, 0.90, 1.0)     # O-type Electric Cyan
            elif roll < 0.85:
                color = (1.0, 0.88, 0.68)     # Solar Gold
            else:
                color = (1.0, 0.68, 0.48)     # Warm Amber

            star_size = rng.uniform(1.8, 4.2)
            twinkle_freq = rng.uniform(1.5, 4.2)
            twinkle_phase = rng.uniform(0.0, math.tau)
            base_alpha = rng.uniform(0.70, 1.0)

            self.stars.append({
                "base_dir": (x, y, z),
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
            self.program = link_program(OVERWORLD_SKY_VERT_SRC, OVERWORLD_SKY_FRAG_SRC)
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

            # Load photorealistic Overworld sky textures
            tex_dir = 'd:/Programs/tp/textures'
            self.sun_tex = load_gl_texture(os.path.join(tex_dir, "overworld_sun.png"))
            self.moon_tex = load_gl_texture(os.path.join(tex_dir, "overworld_moon.png"))
            self.aurora_tex = load_gl_texture(os.path.join(tex_dir, "aurora_curtain.png"))
            self.star_tex = load_gl_texture(os.path.join(tex_dir, "space_star.png"))

            self.initialized = True
        except Exception as e:
            print(f"[OverworldRealisticSky Init Error]: {e}")

    def render(self, camera, time_of_day=0.25, total_time=0.0):
        if not self.initialized:
            self.init_gl()
        if not self.initialized or self.program is None:
            return

        cam_x, cam_y, cam_z = camera.position

        try:
            mvp_matrix = camera.mv_matrix * camera.p_matrix
            flat_mvp = sum(mvp_matrix.data, [])
            mvp_data = (gl.GLfloat * 16)(*flat_mvp)
        except Exception as e:
            print(f"[OverworldSky Matrix Error]: {e}")
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

        R = 380.0
        tod = time_of_day % 1.0
        theta = (tod - 0.50) * math.tau

        # Celestial East-to-West trajectories
        sun_dx = -math.sin(theta)
        sun_dy = math.cos(theta)
        sun_dz = 0.0

        moon_dx = math.sin(theta)
        moon_dy = -math.cos(theta)
        moon_dz = 0.0

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
        # 1. Photorealistic Realistic Sun
        # -------------------------------------------------------------
        if self.sun_tex and sun_dy > -0.15:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Additive solar brilliance
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.sun_tex)
            
            # Sun elevation color transition (amber-crimson at horizon -> brilliant gold at zenith)
            sun_elev = max(0.0, min(1.0, sun_dy))
            horizon_fade = max(0.0, min(1.0, (sun_dy + 0.15) / 0.25))
            
            sr = 1.0
            sg = 0.55 + 0.43 * sun_elev
            sb = 0.22 + 0.74 * sun_elev
            sa = horizon_fade
            
            p, t, c, idxs = build_billboard_quad((sun_dx, sun_dy, sun_dz), 95.0, 95.0, color=(sr, sg, sb, sa))
            upload_and_draw(p, t, c, idxs)

        # -------------------------------------------------------------
        # 2. Photorealistic Realistic Moon
        # -------------------------------------------------------------
        if self.moon_tex and moon_dy > -0.15:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA) # Alpha blend realistic moon
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.moon_tex)
            
            moon_elev_fade = max(0.0, min(1.0, (moon_dy + 0.15) / 0.25))
            p, t, c, idxs = build_billboard_quad((moon_dx, moon_dy, moon_dz), 80.0, 80.0, color=(1.0, 1.0, 1.0, moon_elev_fade))
            upload_and_draw(p, t, c, idxs)

        # -------------------------------------------------------------
        # 3. Dynamic Animated Aurora Borealis (Northern Lights at Night)
        # -------------------------------------------------------------
        # Aurora appears at night (tod < 0.24 or tod >= 0.76) across the northern sky
        aurora_intensity = 0.0
        if tod < 0.20 or tod >= 0.80:
            aurora_intensity = 1.0
        elif 0.20 <= tod < 0.25:
            aurora_intensity = 1.0 - (tod - 0.20) / 0.05
        elif 0.75 <= tod < 0.80:
            aurora_intensity = (tod - 0.75) / 0.05

        if self.aurora_tex and aurora_intensity > 0.01:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Additive atmospheric glow
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.aurora_tex)
            
            aur_pos, aur_tex, aur_col, aur_idx = [], [], [], []
            v_count = 0

            # 4 undulating, layered ribbons of aurora arching in the north
            aurora_layers = [
                ((0.0, 0.48, -0.85), 260.0, 130.0, 0.0, (0.2, 1.0, 0.6, 0.65 * aurora_intensity)),
                ((-0.45, 0.55, -0.75), 230.0, 120.0, -0.25, (0.3, 0.9, 1.0, 0.55 * aurora_intensity)),
                ((0.45, 0.52, -0.78), 240.0, 125.0, 0.22, (0.8, 0.35, 1.0, 0.50 * aurora_intensity)),
                ((0.0, 0.68, -0.65), 210.0, 110.0, 0.05, (0.4, 1.0, 0.8, 0.45 * aurora_intensity)),
            ]
            for c_dir, sw, sh, base_roll, col in aurora_layers:
                # Undulating dynamic wave motion
                wave_roll = base_roll + math.sin(total_time * 0.45 + c_dir[0] * 3.0) * 0.08
                p, t, c, idxs = build_billboard_quad(c_dir, sw, sh, roll_ang=wave_roll, color=col)
                aur_pos.extend(p)
                aur_tex.extend(t)
                aur_col.extend(c)
                aur_idx.extend([i + v_count for i in idxs])
                v_count += 4
            upload_and_draw(aur_pos, aur_tex, aur_col, aur_idx)

        # -------------------------------------------------------------
        # 4. Realistic Twinkling Overworld Night Stars
        # -------------------------------------------------------------
        # Night star visibility factor
        star_intensity = 0.0
        if tod < 0.20 or tod >= 0.80:
            star_intensity = 1.0
        elif 0.20 <= tod < 0.26:
            star_intensity = 1.0 - (tod - 0.20) / 0.06
        elif 0.74 <= tod < 0.80:
            star_intensity = (tod - 0.74) / 0.06

        if self.star_tex and star_intensity > 0.01:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Additive twinkle
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.star_tex)
            
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            s_pos, s_tex, s_col, s_idx = [], [], [], []
            v_count = 0
            for star in self.stars:
                bx, by, bz = star["base_dir"]
                # Rotate stars along with celestial sphere (theta)
                rx_dir = bx * cos_t - by * sin_t
                ry_dir = bx * sin_t + by * cos_t
                rz_dir = bz

                if ry_dir > 0.04:
                    twinkle = math.sin(total_time * star["freq"] + star["phase"]) * 0.35 + 0.65
                    alpha = star["base_alpha"] * twinkle * star_intensity * min(1.0, (ry_dir - 0.04) / 0.10)
                    cr, cg, cb = star["color"]
                    p, t, c, idxs = build_billboard_quad((rx_dir, ry_dir, rz_dir), star["size"], star["size"], color=(cr, cg, cb, alpha))
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
        gl.glEnable(gl.GL_CULL_FACE)


overworld_sky_renderer = OverworldRealisticSkyRenderer()
