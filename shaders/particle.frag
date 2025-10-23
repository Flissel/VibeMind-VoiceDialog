#version 330 core

in vec3 particleColor;
out vec4 FragColor;

void main() {
    // Create circular particles
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);

    if (dist > 0.5)
        discard;

    // Soft edges
    float alpha = 1.0 - smoothstep(0.3, 0.5, dist);

    FragColor = vec4(particleColor, alpha);
}
