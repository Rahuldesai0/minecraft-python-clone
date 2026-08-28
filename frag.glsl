#version 330

out vec4 fragment_colour;

uniform sampler2DArray texture_array_sampler;
uniform sampler2D shadow_heightmap;
uniform vec3 shadow_origin;
uniform float shadow_world_size;

uniform float sky_light_factor; // 1.0 at day (15/15), 0.40 at night (6/15)
uniform float min_light_level;  // default ~0.20 ambient cave floor

// Ray Traced / Enhanced Lighting Uniforms
uniform int lighting_mode;      // 0: Classic Block Lighting, 1: Ray Traced (Shader)
uniform vec3 sun_direction;     // Normalized vector to Sun in world space
uniform vec3 camera_pos;        // Player eye position
uniform float game_time;        // Elapsed time (seconds) for wave/reflection dynamics
uniform int dimension_id;       // 0: Overworld, 1: Nether, 2: End

in vec3 local_position;
in vec3 interpolated_tex_coords;
in vec3 interpolated_light_and_shading;

void main(void) {
	vec4 texture_colour = texture(texture_array_sampler, interpolated_tex_coords);

	if (texture_colour.a == 0.0) { // discard if texel's alpha component is 0 (texel is transparent)
		discard;
	}

	float dist_to_cam = length(camera_pos - local_position);

	// =========================================================================
	// CELESTIAL OBJECTS (Sun, Moon, Stars at R >= 250)
	// =========================================================================
	if (dist_to_cam > 250.0) {
		// Pure emissive brilliant rendering for Sun, Moon, Stars
		vec3 emissive_color = texture_colour.rgb;
		
		// If rendering Sun (warm radiant glow):
		if (sun_direction.y > -0.2) {
			emissive_color = mix(texture_colour.rgb, vec3(1.0, 0.98, 0.85), 0.60) * 1.4;
		}
		fragment_colour = vec4(emissive_color, texture_colour.a);
		return;
	}

	float s_factor = (sky_light_factor <= 0.0) ? 0.0 : sky_light_factor;
	float m_light = (min_light_level <= 0.0) ? 0.20 : min_light_level;

	float sky_light_val = interpolated_light_and_shading.x;
	float block_light_val = interpolated_light_and_shading.y;
	float face_shd_val = clamp(interpolated_light_and_shading.z, 0.50, 1.0);

	// =========================================================================
	// MODE 0: CLASSIC MINECRAFT BLOCK LIGHTING
	// =========================================================================
	if (lighting_mode == 0) {
		float effective_sky = sky_light_val * s_factor;
		float effective_light = max(effective_sky, block_light_val);
		float light_ratio = clamp(effective_light / 15.0, 0.0, 1.0);
		float smooth_ratio = light_ratio * light_ratio * (3.0 - 2.0 * light_ratio); // Smoothstep curve
		float min_effective = mix(m_light, 0.35, s_factor);
		float brightness = mix(min_effective, 1.0, smooth_ratio);
		float final_mult = max(min_effective * 0.70, brightness * face_shd_val);
		fragment_colour = vec4(texture_colour.rgb * final_mult, texture_colour.a);
		return;
	}

	// =========================================================================
	// MODE 1: RAY TRACED SHADER LIGHTING (Strict Directional Light & Reflections)
	// =========================================================================

	// 1. Geometric Normal from screen-space partial derivatives
	vec3 dX = dFdx(local_position);
	vec3 dY = dFdy(local_position);
	vec3 geo_normal = normalize(cross(dX, dY));
	vec3 V = normalize(camera_pos - local_position);
	if (dot(geo_normal, V) < 0.0) {
		geo_normal = -geo_normal;
	}

	// 2. Identify Surface Material Properties
	bool is_water = (interpolated_tex_coords.z >= 8.5 && interpolated_tex_coords.z <= 9.5) ||
	                (interpolated_tex_coords.z >= 18.5 && interpolated_tex_coords.z <= 19.5) ||
	                (texture_colour.a < 0.95);
	bool is_ice = (interpolated_tex_coords.z >= 93.5 && interpolated_tex_coords.z <= 95.5);
	bool is_reflective = (is_water || is_ice);

	// 3. Normal Perturbation for Dynamic Water Waves
	vec3 N = geo_normal;
	if (is_water) {
		float wave1 = sin(local_position.x * 2.2 + game_time * 2.8 + local_position.z * 1.6);
		float wave2 = cos(local_position.z * 2.4 - game_time * 2.2 + local_position.x * 1.5);
		vec3 wave_normal = normalize(vec3(wave1 * 0.15, 1.0, wave2 * 0.15));
		N = normalize(mix(geo_normal, wave_normal, 0.75));
	}

	// 4. Directional Sun/Moon Ray Lighting (Strictly from Sun Direction L)
	vec3 L = normalize(sun_direction);
	float sun_height = L.y;

	// Smooth day vs night blend factor (continuous transition across twilight)
	float day_factor = smoothstep(-0.15, 0.15, sun_height);
	
	// Golden hour sunrise/sunset peak when sun is near horizon (sun_height in [-0.20, 0.25])
	float horizon_factor = 1.0 - clamp(abs(sun_height) / 0.30, 0.0, 1.0);
	horizon_factor = horizon_factor * horizon_factor;

	// Direct Diffuse Lambertian: ONLY lit if facing towards the sun (N.L > 0)
	float NdotL = max(0.0, dot(N, L));

	// Sky exposure ratio (from voxel sky light BFS)
	float sky_exposure = clamp(sky_light_val / 15.0, 0.0, 1.0);

	// =========================================================================
	// REAL-TIME DIRECTIONAL SHADOW RAYMARCHING (Trees, Mountains, Cliffs, Buildings)
	// =========================================================================
	float sun_shadow = 0.0;
	if (NdotL > 0.001 && sun_height > -0.05) {
		float occlusion = 0.0;
		// March along ray L towards the sun
		// 24 high-resolution adaptive steps spanning 0.8m to 125m
		for (int i = 1; i <= 24; i++) {
			float fi = float(i);
			float t = fi * 0.75 + (fi * fi) * 0.18;
			vec3 ray_pos = local_position + L * t;

			vec2 uv = (ray_pos.xz - shadow_origin.xz) / shadow_world_size;
			if (uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0) {
				float occ_h = texture(shadow_heightmap, uv).r * 255.0;
				if (ray_pos.y < occ_h - 0.20) {
					occlusion = 1.0;
					break;
				}
			}
		}

		float direct_vis = (1.0 - occlusion) * sky_exposure;
		sun_shadow = direct_vis * smoothstep(0.0, 0.20, NdotL);
	}

	// Celestial Sun & Sky Colors (Smooth continuous day/sunset/night gradients)
	vec3 midday_sun = vec3(1.35, 1.28, 1.15);
	vec3 sunset_sun = vec3(1.50, 0.68, 0.22);
	vec3 moon_light = vec3(0.42, 0.55, 0.88);

	vec3 direct_day_sun = mix(midday_sun, sunset_sun, horizon_factor);
	vec3 direct_sun_color = mix(moon_light, direct_day_sun, day_factor);

	vec3 midday_sky = vec3(0.55, 0.72, 0.98) * 0.50;
	vec3 sunset_sky = vec3(0.75, 0.45, 0.30) * 0.55;
	vec3 night_sky  = vec3(0.12, 0.16, 0.30);

	vec3 direct_day_sky = mix(midday_sky, sunset_sky, horizon_factor);
	vec3 ambient_sky_color = mix(night_sky, direct_day_sky, day_factor);

	// Direct Sunlight: strictly directional (N.L * shadow)
	vec3 direct_sun = direct_sun_color * (NdotL * sun_shadow * s_factor);

	// Indirect Ambient Skylight: guaranteed ambient floor so side faces in shade remain clearly visible
	float ambient_floor = mix(0.18, 0.38, day_factor);
	vec3 ambient_light = ambient_sky_color * max(sky_exposure * s_factor, ambient_floor);

	// 5. Point Light Emission (Torches, Glowstone, Lava, Fire)
	vec3 torch_light = vec3(0.0);
	if (block_light_val > 0.0) {
		float b_ratio = clamp(block_light_val / 15.0, 0.0, 1.0);
		float b_curve = b_ratio * b_ratio * (3.0 - 2.0 * b_ratio);
		torch_light = vec3(1.15, 0.80, 0.40) * b_curve * 1.35;
	}

	// Ambient Occlusion from vertex corner shading
	float ao = face_shd_val;

	// Total Diffuse Illumination
	vec3 total_illumination = (direct_sun + ambient_light + torch_light) * ao;

	// Base shaded diffuse color
	vec3 shaded_color = texture_colour.rgb * total_illumination;

	// 6. Highly Reflective Water & Ice with Mirror Sky & Specular Sun Glints
	if (is_reflective) {
		vec3 R = reflect(-V, N);

		// Blinn-Phong Sun Glint Specular Beam across water
		vec3 H = normalize(L + V);
		float NdotH = max(0.0, dot(N, H));
		float spec_power = is_water ? 96.0 : 40.0;
		float spec_intensity = pow(NdotH, spec_power);
		vec3 specular_glint = direct_sun_color * spec_intensity * sun_shadow * (day_factor * 2.5 + 0.9);

		// Strong Fresnel Reflection (Schlick approximation)
		float F0 = is_water ? 0.28 : 0.15;
		float cos_theta = max(0.0, dot(N, V));
		float fresnel = F0 + (1.0 - F0) * pow(1.0 - cos_theta, 2.0);

		// Sky & Horizon Reflection Color along ray R
		float r_sky_height = clamp(R.y, 0.0, 1.0);
		vec3 day_reflected_sky = mix(vec3(0.78, 0.88, 1.00), vec3(0.35, 0.62, 1.00), r_sky_height);
		vec3 night_reflected_sky = mix(vec3(0.12, 0.16, 0.28), vec3(0.04, 0.06, 0.16), r_sky_height);
		vec3 reflected_sky = mix(night_reflected_sky, day_reflected_sky, day_factor);

		// Blend reflection prominently onto surface
		shaded_color = mix(shaded_color, reflected_sky, fresnel * 0.90) + specular_glint;
	}

	// 7. Distance Atmospheric Scattering / Horizon Mist
	float fog_density = 0.0030;
	float fog_factor = clamp(1.0 - exp(-dist_to_cam * fog_density), 0.0, 0.80);
	vec3 fog_color = mix(vec3(0.06, 0.09, 0.20), vec3(0.60, 0.76, 0.96), day_factor);

	if (dimension_id == 1) { // Nether
		fog_color = vec3(0.28, 0.06, 0.06);
	} else if (dimension_id == 2) { // End
		fog_color = vec3(0.09, 0.03, 0.14);
	}

	// ACES Tone Mapping for vibrant shader contrast
	vec3 tonemapped = shaded_color / (shaded_color + vec3(0.85)) * 1.18;
	vec3 final_color = mix(tonemapped, fog_color, fog_factor);

	fragment_colour = vec4(final_color, texture_colour.a);
}