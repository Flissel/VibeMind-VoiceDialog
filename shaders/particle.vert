#version 330 core

layout (location = 0) in vec2 aPos;
layout (location = 1) in vec3 aColor;
layout (location = 2) in float aSize;

out vec3 particleColor;

uniform float aspectRatio;

void main() {
    gl_Position = vec4(aPos.x * 2.0 - 1.0, (aPos.y * 2.0 - 1.0) * aspectRatio, 0.0, 1.0);
    gl_PointSize = aSize;
    particleColor = aColor;
}
