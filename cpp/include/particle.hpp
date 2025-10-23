#pragma once

#include <glm/glm.hpp>

namespace VoiceDialog {

struct Particle {
    glm::vec2 position;
    glm::vec2 velocity;
    glm::vec3 color;
    float size;
    float base_size;
    float brightness;
    int id;

    Particle()
        : position(0.0f), velocity(0.0f), color(1.0f),
          size(1.0f), base_size(1.0f), brightness(1.0f), id(0) {}

    Particle(const glm::vec2& pos, const glm::vec2& vel, int particle_id)
        : position(pos), velocity(vel), color(1.0f),
          size(2.0f), base_size(2.0f), brightness(1.0f), id(particle_id) {}

    void update(float deltaTime) {
        position += velocity * deltaTime;

        // Wrap around screen edges
        if (position.x < 0.0f) position.x += 1.0f;
        if (position.x > 1.0f) position.x -= 1.0f;
        if (position.y < 0.0f) position.y += 1.0f;
        if (position.y > 1.0f) position.y -= 1.0f;
    }
};

} // namespace VoiceDialog
