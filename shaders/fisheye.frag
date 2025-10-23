#version 330 core

in vec2 TexCoords;
out vec4 FragColor;

uniform sampler2D screenTexture;
uniform float fisheyeStrength;
uniform vec2 fisheyeCenter;
uniform float audioAmplitude;

vec2 applyFisheye(vec2 uv) {
    vec2 centered = uv - fisheyeCenter;
    float r = length(centered);

    // Dynamic fisheye that pulses with audio
    float strength = fisheyeStrength * (1.0 + audioAmplitude * 0.2);

    // Fisheye distortion
    float r_distorted = r * (1.0 + strength * r * r);

    if (r > 0.001) {
        vec2 direction = normalize(centered);
        return fisheyeCenter + direction * r_distorted;
    }

    return uv;
}

void main() {
    // Apply fisheye distortion
    vec2 distorted_uv = applyFisheye(TexCoords);

    // Check bounds
    if (distorted_uv.x < 0.0 || distorted_uv.x > 1.0 ||
        distorted_uv.y < 0.0 || distorted_uv.y > 1.0) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // Sample texture with distorted coordinates
    vec4 color = texture(screenTexture, distorted_uv);

    // Optional: Add chromatic aberration for extra effect
    float aberration = audioAmplitude * 0.005;
    float r = texture(screenTexture, distorted_uv + vec2(aberration, 0.0)).r;
    float g = texture(screenTexture, distorted_uv).g;
    float b = texture(screenTexture, distorted_uv - vec2(aberration, 0.0)).b;

    FragColor = vec4(r, g, b, color.a);
}
