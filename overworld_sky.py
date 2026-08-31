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

# =============================================================================
# PHOTOREALISTIC PROCEDURAL CUMULUS CLOUD DOME SHADERS (SHADER MODE)
# =============================================================================
REALISTIC_CLOUD_DOME_VERT_SRC = """#version 330
layout(location = 0) in vec3 a_Position;
layout(location = 1) in vec2 a_TexCoord;

uniform mat4 u_MVPMatrix;

out vec2 v_TexCoord;
out vec3 v_SkyPos;

void main(void) {
    v_TexCoord = a_TexCoord;
    v_SkyPos = a_Position;
    gl_Position = u_MVPMatrix * vec4(a_Position, 1.0);
}
"""

REALISTIC_CLOUD_DOME_FRAG_SRC = """#version 330
in vec2 v_TexCoord;
in vec3 v_SkyPos;

uniform vec3 u_CameraPos;
uniform vec3 u_SunDir;
uniform float u_TimeOfDay;
uniform float u_GameTime;

out vec4 fragColor;

// Fast 2D Hash
vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

// 2D Simplex/Perlin noise
float noise2d(vec2 p) {
    const float K1 = 0.366025404;
    const float K2 = 0.211324865;
    vec2 i = floor(p + (p.x + p.y) * K1);
    vec2 a = p - i + (i.x + i.y) * K2;
    vec2 o = (a.x > a.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 b = a - o + K2;
    vec2 c = a - 1.0 + 2.0 * K2;
    vec3 h = max(0.5 - vec3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
    vec3 n = h * h * h * h * vec3(dot(a, hash2(i)), dot(b, hash2(i + o)), dot(c, hash2(i + 1.0)));
    return dot(n, vec3(70.0));
}

// 2D Worley Cellular Noise (produces puffy, billowy, cauliflower cumulus heads!)
float worley2d(vec2 p) {
    vec2 xi = floor(p);
    vec2 xf = fract(p);
    float min_dist = 1.0;
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = 0.5 + 0.5 * sin(hash2(xi + neighbor) * 6.2831853);
            vec2 diff = neighbor + point - xf;
            float dist = length(diff);
            min_dist = min(min_dist, dist);
        }
    }
    return clamp(1.0 - min_dist, 0.0, 1.0);
}

// Multi-octave Worley + Perlin Cumulus Cloud Structure
float cumulus_density(vec2 uv, float day_factor) {
    // Large cumulus base billows (Worley cellular)
    float w1 = worley2d(uv * 1.5);
    float w2 = worley2d(uv * 3.0) * 0.5;
    float w3 = worley2d(uv * 6.0) * 0.25;
    float worley_cumulus = (w1 + w2 + w3) / 1.75;

    // High frequency fractal turbulence (Perlin erosion & wisps)
    float p1 = 0.5 + 0.5 * noise2d(uv * 2.2);
    float p2 = 0.5 + 0.5 * noise2d(uv * 4.8 + vec2(3.1, 1.7));
    float p3 = 0.5 + 0.5 * noise2d(uv * 9.6 + vec2(7.3, 4.1));
    float perlin_fbm = p1 * 0.55 + p2 * 0.30 + p3 * 0.15;

    // Combine Worley billows with Perlin detail
    float shape = mix(worley_cumulus, perlin_fbm, 0.35);

    // Dynamic coverage threshold: Daytime (0.44 = full fluffy cumulus) vs Nighttime (0.64 = scarce, rare isolated wisps)
    float coverage = mix(0.64, 0.44, day_factor);
    return smoothstep(coverage, coverage + 0.28, shape);
}

void main(void) {
    vec3 sky_dir = normalize(v_SkyPos - u_CameraPos);
    if (sky_dir.y < 0.015) {
        discard;
    }

    // Light vectors & time of day
    vec3 L = normalize(u_SunDir);
    float sun_h = L.y;
    float day_factor = smoothstep(-0.15, 0.15, sun_h);
    float horizon_factor = 1.0 - clamp(abs(sun_h) / 0.30, 0.0, 1.0);
    horizon_factor = horizon_factor * horizon_factor;

    // Atmospheric planar perspective projection
    vec2 proj_coord = sky_dir.xz / (sky_dir.y + 0.20);
    
    // Wind drift across the sky
    vec2 wind = vec2(u_GameTime * 0.008, u_GameTime * 0.002);
    vec2 uv = proj_coord * 0.42 + wind;

    // Sample cumulus density (scarce at night to reveal starry sky & northern lights)
    float density = cumulus_density(uv, day_factor);
    if (density <= 0.005) {
        discard;
    }

    // Forward Mie scattering (Silver Lining / Solar Rim Glow)
    float cos_theta = max(0.0, dot(sky_dir, L));
    float silver_lining = pow(cos_theta, 4.0) * 1.8 + pow(cos_theta, 16.0) * 3.5;

    // Celestial Sun, Sky, and Sunset Colors
    vec3 midday_sun = vec3(1.35, 1.30, 1.22);
    vec3 sunset_sun = vec3(1.65, 0.62, 0.20);
    vec3 moon_col   = vec3(0.48, 0.60, 0.92);

    vec3 direct_sun = mix(moon_col, mix(midday_sun, sunset_sun, horizon_factor), day_factor);

    vec3 day_sky_ambient = vec3(0.68, 0.80, 0.98);
    vec3 sunset_ambient  = vec3(0.88, 0.42, 0.35);
    vec3 night_ambient   = vec3(0.12, 0.16, 0.28);

    vec3 ambient_sky = mix(night_ambient, mix(day_sky_ambient, sunset_ambient, horizon_factor), day_factor);

    // Directional shadow on cumulus billows (illuminated top, shaded base)
    vec3 cloud_sunlit = direct_sun * (1.15 + silver_lining * 0.95);
    vec3 cloud_shadow = ambient_sky * 0.55;

    // Soft volumetric internal scattering gradient
    vec3 cumulus_color = mix(cloud_shadow, cloud_sunlit, pow(density, 0.65));

    // Horizon fade & nighttime soft translucency
    float horizon_fade = smoothstep(0.015, 0.18, sky_dir.y);
    float max_alpha = mix(0.65, 0.92, day_factor);
    float alpha = density * max_alpha * horizon_fade;

    fragColor = vec4(cumulus_color, alpha);
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
        width, height, 0,
        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, c_data
    )
    gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
    return tex_id


class OverworldRealisticSkyRenderer:
    """
    Photorealistic Overworld Celestial Sky & Atmospheric Renderer (Shader Mode):
    - Fluffy, photorealistic procedural Cumulus Clouds moving with the atmospheric wind.
    - Photorealistic Sun with solar flare brilliance and sunset transitions.
    - Photorealistic Moon with lunar texture and night illumination.
    - Dynamic animated Aurora Borealis ribbons in the northern sky.
    - Twinkling celestial stars rotating across the night dome.
    """
    def __init__(self):
        self.initialized = False
        self.program = None
        self.cloud_program = None

        self.sun_tex = None
        self.moon_tex = None
        self.aurora_tex = None
        self.star_tex = None

        self.vao = None
        self.vbo_pos = None
        self.vbo_tex = None
        self.vbo_col = None
        self.ibo = None

        self.cloud_vao = None
        self.cloud_vbo_pos = None
        self.cloud_vbo_tex = None
        self.cloud_ibo = None
        self.cloud_index_count = 0

        # Generate realistic twinkling star catalogue
        self.stars = []
        rng = random.Random(42)
        star_palette = [
            (1.0, 1.0, 1.0),
            (0.85, 0.92, 1.0),
            (1.0, 0.95, 0.80),
            (0.80, 0.88, 1.0),
            (1.0, 0.85, 0.70),
        ]
        for _ in range(650):
            theta_s = rng.uniform(0.0, math.tau)
            phi_s = rng.uniform(-0.95, 0.95)
            r_xy = math.sqrt(max(0.0, 1.0 - phi_s * phi_s))
            x = math.cos(theta_s) * r_xy
            y = phi_s
            z = math.sin(theta_s) * r_xy

            color = rng.choice(star_palette)
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
            # 1. Main Celestial Program (Sun, Moon, Stars, Aurora)
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

            # 2. Moving Photorealistic Cumulus Cloud Dome Program
            self.cloud_program = link_program(REALISTIC_CLOUD_DOME_VERT_SRC, REALISTIC_CLOUD_DOME_FRAG_SRC)
            self.u_c_mvp = gl.glGetUniformLocation(self.cloud_program, b"u_MVPMatrix")
            self.u_c_campos = gl.glGetUniformLocation(self.cloud_program, b"u_CameraPos")
            self.u_c_sundir = gl.glGetUniformLocation(self.cloud_program, b"u_SunDir")
            self.u_c_tod = gl.glGetUniformLocation(self.cloud_program, b"u_TimeOfDay")
            self.u_c_time = gl.glGetUniformLocation(self.cloud_program, b"u_GameTime")

            self.cloud_vao = gl.GLuint(0)
            gl.glGenVertexArrays(1, ctypes.byref(self.cloud_vao))
            self.cloud_vbo_pos = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.cloud_vbo_pos))
            self.cloud_vbo_tex = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.cloud_vbo_tex))
            self.cloud_ibo = gl.GLuint(0)
            gl.glGenBuffers(1, ctypes.byref(self.cloud_ibo))

            # Load photorealistic Overworld sky textures
            tex_dir = 'd:/Programs/tp/textures'
            self.sun_tex = load_gl_texture(os.path.join(tex_dir, "overworld_sun.png"))
            self.moon_tex = load_gl_texture(os.path.join(tex_dir, "overworld_moon.png"))
            self.moon_textures = []
            for i in range(8):
                ph_path = os.path.join(tex_dir, f"overworld_moon_phase_{i}.png")
                t_obj = load_gl_texture(ph_path) if os.path.exists(ph_path) else self.moon_tex
                self.moon_textures.append(t_obj)
            self.aurora_tex = load_gl_texture(os.path.join(tex_dir, "aurora_curtain.png"))
            self.star_tex = load_gl_texture(os.path.join(tex_dir, "space_star.png"))

            # Build tessellated upper celestial dome mesh for moving clouds
            self._init_cloud_dome_mesh()

            self.initialized = True
        except Exception as e:
            print(f"[OverworldRealisticSky Init Error]: {e}")

    def _init_cloud_dome_mesh(self):
        """Constructs a high-precision tessellated upper hemisphere dome mesh at R = 380."""
        positions = []
        tex_coords = []
        indices = []

        R = 380.0
        slices = 48
        stacks = 24

        v_idx = 0
        for i in range(stacks):
            # Stack angle from near horizon (0.02) to zenith (pi/2)
            phi0 = 0.02 + (i / float(stacks)) * (math.pi * 0.5 - 0.02)
            phi1 = 0.02 + ((i + 1) / float(stacks)) * (math.pi * 0.5 - 0.02)

            sin_p0, cos_p0 = math.sin(phi0), math.cos(phi0)
            sin_p1, cos_p1 = math.sin(phi1), math.cos(phi1)

            for j in range(slices):
                theta0 = (j / float(slices)) * math.tau
                theta1 = ((j + 1) / float(slices)) * math.tau

                cos_t0, sin_t0 = math.cos(theta0), math.sin(theta0)
                cos_t1, sin_t1 = math.cos(theta1), math.sin(theta1)

                p00 = (R * cos_p0 * cos_t0, R * sin_p0, R * cos_p0 * sin_t0)
                p10 = (R * cos_p0 * cos_t1, R * sin_p0, R * cos_p0 * sin_t1)
                p11 = (R * cos_p1 * cos_t1, R * sin_p1, R * cos_p1 * sin_t1)
                p01 = (R * cos_p1 * cos_t0, R * sin_p1, R * cos_p1 * sin_t0)

                positions.extend([
                    p00[0], p00[1], p00[2],
                    p10[0], p10[1], p10[2],
                    p11[0], p11[1], p11[2],
                    p01[0], p01[1], p01[2],
                ])
                tex_coords.extend([
                    j / float(slices), i / float(stacks),
                    (j + 1) / float(slices), i / float(stacks),
                    (j + 1) / float(slices), (i + 1) / float(stacks),
                    j / float(slices), (i + 1) / float(stacks),
                ])
                indices.extend([
                    v_idx, v_idx + 1, v_idx + 2,
                    v_idx, v_idx + 2, v_idx + 3
                ])
                v_idx += 4

        gl.glBindVertexArray(self.cloud_vao)

        pos_data = (gl.GLfloat * len(positions))(*positions)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.cloud_vbo_pos)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(pos_data), pos_data, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glEnableVertexAttribArray(0)

        tex_data = (gl.GLfloat * len(tex_coords))(*tex_coords)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.cloud_vbo_tex)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tex_data), tex_data, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glEnableVertexAttribArray(1)

        idx_data = (gl.GLuint * len(indices))(*indices)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.cloud_ibo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(idx_data), idx_data, gl.GL_STATIC_DRAW)

        self.cloud_index_count = len(indices)
        gl.glBindVertexArray(0)

    def render(self, camera, time_of_day=0.25, total_time=0.0, moon_phase=0):
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
            return

        gl.glEnable(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_CULL_FACE)

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

        # -------------------------------------------------------------
        # PART A: CELESTIAL BACKGROUND OBJECTS (Sun, Moon, Stars, Aurora)
        # -------------------------------------------------------------
        gl.glUseProgram(self.program)
        gl.glUniformMatrix4fv(self.u_mvp, 1, gl.GL_FALSE, mvp_data)
        gl.glUniform1i(self.u_tex, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindVertexArray(self.vao)

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

        # 1. Realistic Twinkling Overworld Night Stars
        star_intensity = 0.0
        if tod < 0.20 or tod >= 0.80:
            star_intensity = 1.0
        elif 0.20 <= tod < 0.26:
            star_intensity = 1.0 - (tod - 0.20) / 0.06
        elif 0.74 <= tod < 0.80:
            star_intensity = (tod - 0.74) / 0.06

        if self.star_tex and star_intensity > 0.01:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.star_tex)

            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            s_pos, s_tex, s_col, s_idx = [], [], [], []
            v_count = 0
            for star in self.stars:
                bx, by, bz = star["base_dir"]
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

        # 2. Dynamic Animated Aurora Borealis (Northern Lights at Night)
        aurora_intensity = 0.0
        if tod < 0.20 or tod >= 0.80:
            aurora_intensity = 1.0
        elif 0.20 <= tod < 0.25:
            aurora_intensity = 1.0 - (tod - 0.20) / 0.05
        elif 0.75 <= tod < 0.80:
            aurora_intensity = (tod - 0.75) / 0.05

        if self.aurora_tex and aurora_intensity > 0.01:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.aurora_tex)

            aur_pos, aur_tex, aur_col, aur_idx = [], [], [], []
            v_count = 0

            aurora_layers = [
                ((0.0, 0.48, -0.85), 260.0, 130.0, 0.0, (0.2, 1.0, 0.6, 0.65 * aurora_intensity)),
                ((-0.45, 0.55, -0.75), 230.0, 120.0, -0.25, (0.3, 0.9, 1.0, 0.55 * aurora_intensity)),
                ((0.45, 0.52, -0.78), 240.0, 125.0, 0.22, (0.8, 0.35, 1.0, 0.50 * aurora_intensity)),
                ((0.0, 0.68, -0.65), 210.0, 110.0, 0.05, (0.4, 1.0, 0.8, 0.45 * aurora_intensity)),
            ]
            for c_dir, sw, sh, base_roll, col in aurora_layers:
                wave_roll = base_roll + math.sin(total_time * 0.45 + c_dir[0] * 3.0) * 0.08
                p, t, c, idxs = build_billboard_quad(c_dir, sw, sh, roll_ang=wave_roll, color=col)
                aur_pos.extend(p)
                aur_tex.extend(t)
                aur_col.extend(c)
                aur_idx.extend([i + v_count for i in idxs])
                v_count += 4
            upload_and_draw(aur_pos, aur_tex, aur_col, aur_idx)

        # 3. Photorealistic Sun
        if self.sun_tex and sun_dy > -0.15:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.sun_tex)

            sun_elev = max(0.0, min(1.0, sun_dy))
            horizon_fade = max(0.0, min(1.0, (sun_dy + 0.15) / 0.25))

            sr = 1.0
            sg = 0.55 + 0.43 * sun_elev
            sb = 0.22 + 0.74 * sun_elev
            sa = horizon_fade

            p, t, c, idxs = build_billboard_quad((sun_dx, sun_dy, sun_dz), 95.0, 95.0, color=(sr, sg, sb, sa))
            upload_and_draw(p, t, c, idxs)

        # 4. Photorealistic Moon with 8 Phases
        phase_idx = int(moon_phase) % 8
        moon_tex = self.moon_textures[phase_idx] if getattr(self, "moon_textures", None) and phase_idx < len(self.moon_textures) else self.moon_tex
        if moon_tex and moon_dy > -0.15:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glBindTexture(gl.GL_TEXTURE_2D, moon_tex)

            moon_elev_fade = max(0.0, min(1.0, (moon_dy + 0.15) / 0.25))
            p, t, c, idxs = build_billboard_quad((moon_dx, moon_dy, moon_dz), 80.0, 80.0, color=(1.0, 1.0, 1.0, moon_elev_fade))
            upload_and_draw(p, t, c, idxs)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

        # -------------------------------------------------------------
        # PART B: PHOTOREALISTIC MOVING CUMULUS CLOUD DOME OVERLAY
        # -------------------------------------------------------------
        if self.cloud_program and self.cloud_index_count > 0:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glUseProgram(self.cloud_program)

            try:
                gl.glUniformMatrix4fv(self.u_c_mvp, 1, gl.GL_FALSE, mvp_data)
                gl.glUniform3f(self.u_c_campos, cam_x, cam_y, cam_z)
                gl.glUniform3f(self.u_c_sundir, sun_dx, sun_dy, sun_dz)
                gl.glUniform1f(self.u_c_tod, float(tod))
                gl.glUniform1f(self.u_c_time, float(total_time))

                gl.glBindVertexArray(self.cloud_vao)
                gl.glDrawElements(gl.GL_TRIANGLES, self.cloud_index_count, gl.GL_UNSIGNED_INT, 0)
                gl.glBindVertexArray(0)
                gl.glUseProgram(0)
            except Exception as e:
                pass

        gl.glDepthMask(gl.GL_TRUE)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glEnable(gl.GL_CULL_FACE)


overworld_sky_renderer = OverworldRealisticSkyRenderer()
