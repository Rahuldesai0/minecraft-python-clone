#version 330

out vec4 fragment_colour;

uniform sampler2DArray texture_array_sampler;
uniform sampler2D shadow_heightmap;
uniform sampler2D scene_texture;
uniform vec2 window_size;
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
	int tex_id = int(floor(interpolated_tex_coords.z + 0.5));

	// Discard alpha == 0 pixels EXCEPT for glass (so clear glass body can refract & reflect)
	if (texture_colour.a == 0.0 && tex_id != 21) {
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
	bool is_water = (tex_id == 9);
	bool is_ice = (tex_id == 37 || tex_id == 141);
	bool is_gold = (tex_id == 33);
	bool is_iron_block = (tex_id == 34);
	bool is_diamond_block = (tex_id == 35);
	bool is_iron_ore = (tex_id == 19);
	bool is_diamond_ore = (tex_id == 20);
	bool is_gold_ore = (tex_id == 40);
	bool is_glass = (tex_id == 21);
	bool is_metallic = (is_gold || is_iron_block || is_diamond_block);
	bool is_reflective = (is_water || is_ice || is_metallic || is_glass);
	bool is_defect = (is_glass && texture_colour.r > 0.92 && texture_colour.g > 0.92 && texture_colour.b > 0.92 && texture_colour.a > 0.5);

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
	// REAL-TIME DIRECTIONAL SHADOW RAYMARCHING (Trees, Mountains, Cliffs, Buildings, Cactus)
	// =========================================================================
	float sun_shadow = 0.0;
	if (NdotL > 0.001 && sun_height > -0.05) {
		float occlusion = 0.0;
		// March along ray L towards the sun with fine sub-voxel stepping
		// 32 high-precision steps: fine 0.35m steps up to 8m, then expanding steps up to 100m
		for (int i = 1; i <= 32; i++) {
			float fi = float(i);
			float t = (fi <= 16.0) ? (fi * 0.35) : (5.6 + (fi - 16.0) * 1.2 + pow(fi - 16.0, 2.0) * 0.22);
			vec3 ray_pos = local_position + L * t;

			// Sample discrete block voxel column in the shadow heightfield
			vec2 block_xz = floor(ray_pos.xz) + vec2(0.5);
			vec2 uv = (block_xz - shadow_origin.xz) / shadow_world_size;
			if (uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0) {
				float occ_h = texture(shadow_heightmap, uv).r * 255.0;
				if (ray_pos.y < occ_h - 0.15) {
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

	float ambient_floor = mix(0.18, 0.38, day_factor);

	if (dimension_id == 2) { // The End (Illuminated by ethereal deep-space cosmos and celestial planet)
		ambient_sky_color = vec3(0.68, 0.54, 0.90) * 1.35;
		ambient_floor = 0.62;
		direct_sun_color = vec3(0.85, 0.72, 1.10) * 1.15;
	}

	// Direct Sunlight: strictly directional (N.L * shadow)
	vec3 direct_sun = direct_sun_color * (NdotL * sun_shadow * s_factor);

	// Indirect Ambient Skylight: guaranteed ambient floor so side faces in shade remain clearly visible
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
	vec3 base_tint = is_glass ? vec3(0.92, 0.97, 1.05) : vec3(1.0);
	vec3 shaded_color = texture_colour.rgb * base_tint * total_illumination;

	// Physical Clear Glass Body on transparent pixels (Snell's Law Refraction + Dispersion)
	if (is_glass && !is_defect) {
		vec3 T_refr = refract(-V, N, 1.0 / 1.52);
		if (length(T_refr) < 0.001) T_refr = reflect(-V, N);
		vec2 screen_uv = (window_size.x > 1.0) ? (gl_FragCoord.xy / window_size) : vec2(0.5);
		vec2 refr_offset = T_refr.xy * 0.038;
		vec3 refracted_bg;
		if (window_size.x > 1.0) {
			refracted_bg.r = texture(scene_texture, clamp(screen_uv + refr_offset * 1.025, 0.001, 0.999)).r;
			refracted_bg.g = texture(scene_texture, clamp(screen_uv + refr_offset * 1.000, 0.001, 0.999)).g;
			refracted_bg.b = texture(scene_texture, clamp(screen_uv + refr_offset * 0.975, 0.001, 0.999)).b;
		} else {
			refracted_bg = vec3(0.90, 0.95, 1.02) * total_illumination;
		}
		shaded_color = refracted_bg * vec3(0.94, 0.98, 1.04);
		if (texture_colour.a > 0.5) {
			shaded_color = mix(shaded_color, texture_colour.rgb * 1.15 * total_illumination, 0.45);
		}
	}

	// Micro-Defect Glass Internal & Forward Light Scattering with Crystal Sparkle
	if (is_defect) {
		// Forward Mie scattering with chromatic dispersion when looking towards the sun through glass
		float forward_alignment = max(0.0, dot(-V, L)); // 1.0 when looking straight at the sun through the glass
		vec3 chromatic_fwd = vec3(
			pow(forward_alignment, 3.2) * 4.5 + pow(forward_alignment, 14.0) * 10.0,
			pow(forward_alignment, 3.8) * 4.0 + pow(forward_alignment, 16.0) * 8.0,
			pow(forward_alignment, 4.4) * 5.0 + pow(forward_alignment, 18.0) * 12.0
		);
		vec3 sun_forward_glow = direct_sun_color * chromatic_fwd * max(0.40, sky_exposure) * (day_factor * 2.2 + 0.6);

		// Dynamic micro-facet sparkle & shimmer as camera moves
		vec3 spk_coord = local_position * 48.0 + V * 8.0;
		float spk_rnd = sin(dot(floor(spk_coord), vec3(127.1, 311.7, 74.7))) * 43758.5453;
		float spk_hit = pow(fract(spk_rnd), 14.0) * 7.0;
		vec3 spk_rgb = vec3(0.95 + 0.35 * sin(spk_rnd * 6.28), 0.95 + 0.35 * sin(spk_rnd * 6.28 + 2.09), 0.95 + 0.35 * sin(spk_rnd * 6.28 + 4.18));
		vec3 glitter = spk_rgb * spk_hit * (ambient_light * 1.8 + direct_sun_color * 2.2 * s_factor);

		// Omnidirectional diffuse and back-scatter
		vec3 omni_scatter = (ambient_light * 2.2 + torch_light * 2.5 + direct_sun_color * (max(0.0, abs(dot(N, L))) * 1.5 + 0.50)) * vec3(1.12, 1.16, 1.24);
		
		// Brilliant glowing frosted flecks with crystal glitter
		vec3 defect_glow = (sun_forward_glow + omni_scatter + glitter) * ao;
		shaded_color = defect_glow;
	}

	// Diamond, Gold & Iron Ore Subtle Luminescence & Mineral Sparkle
	if (is_diamond_ore || is_gold_ore || is_iron_ore) {
		float mineral_mask = 0.0;
		vec3 mineral_glow_base = vec3(0.0);
		vec3 mineral_glint_base = vec3(1.0);

		if (is_diamond_ore) {
			// Cyan / Aquamarine crystal flecks in stone
			mineral_mask = smoothstep(0.08, 0.22, (texture_colour.b - texture_colour.r)) * 
			               smoothstep(0.08, 0.22, (texture_colour.g - texture_colour.r)) * 
			               smoothstep(0.40, 0.70, texture_colour.b);
			mineral_glow_base = vec3(0.32, 0.88, 1.05) * 0.38;
			mineral_glint_base = vec3(0.65, 0.92, 1.0);
		} else if (is_gold_ore) {
			// Radiant Golden Yellow / Amber mineral flecks in stone
			mineral_mask = smoothstep(0.12, 0.25, (texture_colour.r - texture_colour.b)) * 
			               smoothstep(0.08, 0.20, (texture_colour.g - texture_colour.b)) * 
			               smoothstep(0.55, 0.75, texture_colour.r);
			mineral_glow_base = vec3(1.15, 0.86, 0.30) * 0.38;
			mineral_glint_base = vec3(1.10, 0.95, 0.50);
		} else if (is_iron_ore) {
			// Warm Peach / Rose-Bronze metallic flecks in stone
			mineral_mask = smoothstep(0.08, 0.20, (texture_colour.r - texture_colour.b)) * 
			               smoothstep(0.03, 0.12, (texture_colour.g - texture_colour.b)) * 
			               smoothstep(0.50, 0.72, texture_colour.r);
			mineral_glow_base = vec3(1.02, 0.74, 0.56) * 0.32;
			mineral_glint_base = vec3(1.05, 0.88, 0.75);
		}

		if (mineral_mask > 0.0) {
			// Subtle gentle pulsing mineral glow
			float pulse = 0.88 + 0.12 * sin(game_time * 2.2 + local_position.x * 3.5 + local_position.z * 3.5);
			vec3 mineral_glow = mineral_glow_base * pulse * mineral_mask;

			// Delicate micro-glint sparkle as player moves past the ore
			vec3 spk_coord = local_position * 32.0 + V * 6.0;
			float spk_rnd = sin(dot(floor(spk_coord), vec3(113.5, 271.9, 154.3))) * 43758.5453;
			float spk_hit = pow(fract(spk_rnd), 18.0) * 3.5;
			vec3 spk_glint = mineral_glint_base * spk_hit * mineral_mask * 0.30;

			shaded_color += (mineral_glow + spk_glint);
		}
	}

	// 6. Highly Reflective Water, Ice, Glass & Metallic Blocks
	if (is_reflective) {
		vec3 R = reflect(-V, N);

		// Blinn-Phong Sun Glint Specular Beam (Double-surface specular for dielectric glass)
		vec3 H = normalize(L + V);
		float NdotH = max(0.0, dot(N, H));
		
		float spec_power = is_water ? 96.0 : (is_glass ? 96.0 : (is_metallic ? 64.0 : 48.0));
		float spec_intensity = pow(NdotH, spec_power);
		
		if (is_glass) {
			// Clear glass double-sided celestial sun reflection
			vec3 R_back = reflect(-V, -N);
			float refl_sun = max(max(0.0, dot(R, L)), max(0.0, dot(R_back, L)));
			float glass_spec = pow(refl_sun, 96.0) * 1.6;
			spec_intensity = max(spec_intensity, glass_spec);
		}
		
		vec3 spec_tint = vec3(1.0);
		if (is_gold) {
			spec_tint = vec3(1.10, 0.88, 0.42);
		} else if (is_diamond_block) {
			spec_tint = vec3(0.65, 0.95, 1.15);
		} else if (is_iron_block) {
			spec_tint = vec3(1.05, 1.05, 1.10);
		} else if (is_glass) {
			spec_tint = vec3(1.08, 1.12, 1.20);
		}
		
		float effective_shadow = is_glass ? max(0.40, sky_exposure) : sun_shadow;
		vec3 specular_glint = direct_sun_color * spec_tint * spec_intensity * effective_shadow * (day_factor * 2.2 + 0.6);

		// Fresnel & Total Internal Reflection (Schlick approximation)
		float F0 = is_water ? 0.28 : (is_glass ? 0.04 : (is_metallic ? 0.40 : 0.20));
		float cos_theta = max(0.0, dot(N, V));
		float fresnel = F0 + (is_glass ? 0.45 : (1.0 - F0)) * pow(1.0 - cos_theta, is_glass ? 3.0 : 2.0);

		// Sky & Horizon Reflection Color along ray R
		float r_sky_height = clamp(R.y, 0.0, 1.0);
		vec3 day_reflected_sky = mix(vec3(0.78, 0.88, 1.00), vec3(0.35, 0.62, 1.00), r_sky_height);
		vec3 night_reflected_sky = mix(vec3(0.12, 0.16, 0.28), vec3(0.04, 0.06, 0.16), r_sky_height);
		vec3 reflected_sky = mix(night_reflected_sky, day_reflected_sky, day_factor);
		
		if (is_gold) {
			reflected_sky *= vec3(1.10, 0.88, 0.42);
		} else if (is_diamond_block) {
			reflected_sky = mix(reflected_sky, vec3(0.55, 0.92, 1.0), 0.35);
		} else if (is_glass) {
			reflected_sky *= vec3(0.92, 0.97, 1.05);
		}

		// Blend reflection onto surface (mild light TIR for glass, not metallic)
		if (!is_defect) {
			float blend_weight = is_metallic ? 0.45 : (is_glass ? 0.45 : 0.90);
			shaded_color = mix(shaded_color, reflected_sky, fresnel * blend_weight) + specular_glint;
		}
	}

	// 7. Distance Atmospheric Scattering / Horizon Mist
	float fog_density = 0.0030;
	float fog_factor = clamp(1.0 - exp(-dist_to_cam * fog_density), 0.0, 0.80);
	vec3 fog_color = mix(vec3(0.06, 0.09, 0.20), vec3(0.60, 0.76, 0.96), day_factor);

	if (dimension_id == 1) { // Nether
		fog_color = vec3(0.28, 0.06, 0.06);
	} else if (dimension_id == 2) { // End
		fog_color = vec3(0.045, 0.015, 0.075);
		fog_density = 0.0018;
		fog_factor = clamp(1.0 - exp(-dist_to_cam * fog_density), 0.0, 0.70);
	}

	// ACES Tone Mapping for vibrant shader contrast
	vec3 tonemapped = shaded_color / (shaded_color + vec3(0.85)) * 1.18;
	vec3 final_color = mix(tonemapped, fog_color, fog_factor);

	float out_alpha = texture_colour.a;
	if (is_glass) {
		if (is_defect) {
			// Defect flecks with crisp shine
			out_alpha = 0.90;
		} else {
			// Clear glass body fully transmits refracted background + surface reflection
			out_alpha = 1.0;
		}
	}

	fragment_colour = vec4(final_color, out_alpha);
}