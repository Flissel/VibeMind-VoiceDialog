#pragma once

#include "audio_features.hpp"
#include "particle.hpp"
#include <vector>
#include <glm/glm.hpp>

namespace VoiceDialog {

class AudioReactiveSimulation {
public:
    AudioReactiveSimulation(int num_particles = 100);
    ~AudioReactiveSimulation();

    // Initialize OpenGL resources
    bool initialize(int window_width, int window_height);

    // Update simulation with audio data
    void updateAudio(const AudioFeatures& audio);

    // Update simulation state
    void update(float deltaTime);

    // Render the scene
    void render();

    // Configuration
    void setFisheyeStrength(float strength);
    void setWindowSize(int width, int height);

    // Cleanup
    void cleanup();

private:
    // Simulation state
    std::vector<Particle> particles_;
    AudioFeatures current_audio_;

    // Visual parameters
    float color_hue_offset_;
    float color_saturation_;
    float particle_energy_;
    float fisheye_strength_;
    glm::vec2 fisheye_center_;

    // Window dimensions
    int window_width_;
    int window_height_;

    // OpenGL resources
    unsigned int vao_;
    unsigned int vbo_;
    unsigned int shader_program_;
    unsigned int fisheye_program_;
    unsigned int framebuffer_;
    unsigned int texture_;

    // Helper methods
    glm::vec3 hsvToRgb(float h, float s, float v) const;
    glm::vec3 getColorFromAudio(int particleId, const AudioFeatures& audio) const;
    void updateParticleFromAudio(Particle& p, const AudioFeatures& audio);

    // OpenGL setup
    bool setupShaders();
    bool setupBuffers();
    bool setupFramebuffer();

    // Rendering
    void renderParticles();
    void applyFisheyeEffect();
};

} // namespace VoiceDialog
