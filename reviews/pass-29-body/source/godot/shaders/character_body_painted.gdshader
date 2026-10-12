// Body-only study: baked anatomical paint follows the mesh; the real scene
// lights and shadow attenuation still determine its dimensional lighting.
shader_type spatial;
render_mode specular_disabled;

uniform vec4 skin_colour : source_color = vec4(1.0);
uniform vec3 cool_glaze = vec3(0.74, 0.84, 1.04);
uniform vec3 warm_glaze = vec3(1.06, 1.02, 0.96);
uniform float shadow_level = 0.22;
uniform float middle_level = 0.62;
uniform float light_level = 0.94;
// Neutral grayscale is coefficient data, not an sRGB skin colour.
uniform sampler2D brush_pigment : filter_linear_mipmap, repeat_enable;
varying vec2 paint;
varying float pigment;

void vertex() {
    paint = UV2;
}

void fragment() {
    pigment = texture(brush_pigment, UV * 3.0).r;
    ALBEDO = skin_colour.rgb * COLOR.rgb * clamp(paint.x, 0.60, 1.05)
        * mix(cool_glaze, warm_glaze, clamp(paint.y, 0.0, 1.0));
    ROUGHNESS = 0.97;
    SPECULAR = 0.0;
}

void light() {
    // Brush marks break the illustrated light transitions, not the skin pigment.
    float value = dot(normalize(NORMAL), LIGHT) + (paint.x - 0.88) * 0.85 + (pigment - 0.5) * 1.2;
    float form = mix(shadow_level, middle_level, smoothstep(-0.22, 0.12, value));
    form = mix(form, light_level, smoothstep(0.42, 0.67, value));
    vec3 glaze = mix(cool_glaze, warm_glaze, smoothstep(-0.15, 0.65, value));
    DIFFUSE_LIGHT += form * glaze * LIGHT_COLOR * ATTENUATION / PI;
}
