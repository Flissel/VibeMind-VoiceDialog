#include "audio_reactive_sim.hpp"
#include <glad/gl.h>
#include <cmath>
#include <iostream>
#include <fstream>
#include <sstream>
#include <random>

namespace VoiceDialog {

// Helper function to load shader
static std::string loadShaderSource(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to open shader: " << filepath << std::endl;
        return "";
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

// Helper to compile shader
static unsigned int compileShader(const std::string& source, GLenum type) {
    unsigned int shader = glCreateShader(type);
    const char* src = source.c_str();
    glShaderSource(shader, 1, &src, nullptr);
    glCompileShader(shader);

    int success;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        char infoLog[512];
        glGetShaderInfoLog(shader, 512, nullptr, infoLog);
        std::cerr << "Shader compilation failed: " << infoLog << std::endl;
        return 0;
    }
    return shader;
}

AudioReactiveSimulation::AudioReactiveSimulation(int num_particles)
    : color_hue_offset_(0.0f),
      color_saturation_(1.0f),
      particle_energy_(0.0f),
      fisheye_strength_(0.5f),
      fisheye_center_(0.5f, 0.5f),
      window_width_(800),
      window_height_(600),
      vao_(0),
      vbo_(0),
      shader_program_(0),
      fisheye_program_(0),
      framebuffer_(0),
      texture_(0) {

    // Initialize particles
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> pos_dist(0.0f, 1.0f);
    std::uniform_real_distribution<float> vel_dist(-0.1f, 0.1f);

    particles_.reserve(num_particles);
    for (int i = 0; i < num_particles; ++i) {
        glm::vec2 pos(pos_dist(gen), pos_dist(gen));
        glm::vec2 vel(vel_dist(gen), vel_dist(gen));
        particles_.emplace_back(pos, vel, i);
    }
}

AudioReactiveSimulation::~AudioReactiveSimulation() {
    cleanup();
}

bool AudioReactiveSimulation::initialize(int window_width, int window_height) {
    window_width_ = window_width;
    window_height_ = window_height;

    if (!setupShaders()) return false;
    if (!setupBuffers()) return false;
    if (!setupFramebuffer()) return false;

    // OpenGL state
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glEnable(GL_PROGRAM_POINT_SIZE);

    return true;
}

void AudioReactiveSimulation::updateAudio(const AudioFeatures& audio) {
    current_audio_ = audio;

    // Update color hue based on audio
    color_hue_offset_ += audio.amplitude * 2.0f;
    if (color_hue_offset_ > 360.0f) color_hue_offset_ -= 360.0f;

    // Saturation pulses with beats
    color_saturation_ = 0.7f + audio.beat_detected * 0.3f;

    // Particle energy from amplitude
    particle_energy_ = audio.amplitude;
}

void AudioReactiveSimulation::update(float deltaTime) {
    // Update all particles with audio influence
    for (auto& particle : particles_) {
        updateParticleFromAudio(particle, current_audio_);
        particle.update(deltaTime);
    }
}

void AudioReactiveSimulation::render() {
    // First pass: Render particles to framebuffer
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);
    glViewport(0, 0, window_width_, window_height_);
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);

    renderParticles();

    // Second pass: Apply fisheye effect to screen
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    applyFisheyeEffect();
}

void AudioReactiveSimulation::setFisheyeStrength(float strength) {
    fisheye_strength_ = strength;
}

void AudioReactiveSimulation::setWindowSize(int width, int height) {
    window_width_ = width;
    window_height_ = height;
    setupFramebuffer();  // Recreate framebuffer with new size
}

void AudioReactiveSimulation::cleanup() {
    if (vao_) glDeleteVertexArrays(1, &vao_);
    if (vbo_) glDeleteBuffers(1, &vbo_);
    if (shader_program_) glDeleteProgram(shader_program_);
    if (fisheye_program_) glDeleteProgram(fisheye_program_);
    if (framebuffer_) glDeleteFramebuffers(1, &framebuffer_);
    if (texture_) glDeleteTextures(1, &texture_);
}

// HSV to RGB conversion
glm::vec3 AudioReactiveSimulation::hsvToRgb(float h, float s, float v) const {
    float c = v * s;
    float x = c * (1.0f - std::abs(std::fmod(h / 60.0f, 2.0f) - 1.0f));
    float m = v - c;

    float r, g, b;
    if (h < 60.0f)       { r = c; g = x; b = 0; }
    else if (h < 120.0f) { r = x; g = c; b = 0; }
    else if (h < 180.0f) { r = 0; g = c; b = x; }
    else if (h < 240.0f) { r = 0; g = x; b = c; }
    else if (h < 300.0f) { r = x; g = 0; b = c; }
    else                 { r = c; g = 0; b = x; }

    return glm::vec3(r + m, g + m, b + m);
}

glm::vec3 AudioReactiveSimulation::getColorFromAudio(int particleId, const AudioFeatures& audio) const {
    // Base hue from particle ID
    float base_hue = std::fmod(static_cast<float>(particleId) * 7.3f + color_hue_offset_, 360.0f);

    // Modulate hue with frequency content
    float hue_shift = 0.0f;
    hue_shift += audio.bass * 60.0f;      // Bass → Blues/purples
    hue_shift += audio.mid * 120.0f;      // Mid → Greens/yellows
    hue_shift += audio.treble * 180.0f;   // Treble → Reds/oranges

    float final_hue = std::fmod(base_hue + hue_shift, 360.0f);

    // Saturation responsive to beats
    float saturation = color_saturation_;

    // Brightness/value from amplitude
    float value = 0.5f + audio.amplitude * 0.5f;

    return hsvToRgb(final_hue, saturation, value);
}

void AudioReactiveSimulation::updateParticleFromAudio(Particle& p, const AudioFeatures& audio) {
    // Particle velocity responds to audio
    float speed_multiplier = 1.0f + particle_energy_ * 2.0f;
    p.velocity *= (1.0f + (speed_multiplier - 1.0f) * 0.01f);  // Smooth acceleration

    // Size pulses with beats
    p.size = p.base_size * (1.0f + audio.beat_detected * 0.5f);

    // Color from audio
    p.color = getColorFromAudio(p.id, audio);

    // Frequency bands affect different particle groups
    if (!audio.spectrum.empty()) {
        int freq_bin = p.id % static_cast<int>(audio.spectrum.size());
        float freq_influence = audio.spectrum[freq_bin];
        p.brightness = 0.5f + freq_influence * 0.5f;
        p.color *= p.brightness;  // Apply brightness to color
    }
}

bool AudioReactiveSimulation::setupShaders() {
    // Particle shaders
    std::string vert_src = loadShaderSource("shaders/particle.vert");
    std::string frag_src = loadShaderSource("shaders/particle.frag");

    if (vert_src.empty() || frag_src.empty()) {
        std::cerr << "Failed to load particle shaders" << std::endl;
        return false;
    }

    unsigned int vert_shader = compileShader(vert_src, GL_VERTEX_SHADER);
    unsigned int frag_shader = compileShader(frag_src, GL_FRAGMENT_SHADER);

    if (!vert_shader || !frag_shader) return false;

    shader_program_ = glCreateProgram();
    glAttachShader(shader_program_, vert_shader);
    glAttachShader(shader_program_, frag_shader);
    glLinkProgram(shader_program_);

    int success;
    glGetProgramiv(shader_program_, GL_LINK_STATUS, &success);
    if (!success) {
        char infoLog[512];
        glGetProgramInfoLog(shader_program_, 512, nullptr, infoLog);
        std::cerr << "Shader program linking failed: " << infoLog << std::endl;
        return false;
    }

    glDeleteShader(vert_shader);
    glDeleteShader(frag_shader);

    // Fisheye shaders
    std::string fisheye_vert_src = loadShaderSource("shaders/fisheye.vert");
    std::string fisheye_frag_src = loadShaderSource("shaders/fisheye.frag");

    if (fisheye_vert_src.empty() || fisheye_frag_src.empty()) {
        std::cerr << "Failed to load fisheye shaders" << std::endl;
        return false;
    }

    unsigned int fisheye_vert = compileShader(fisheye_vert_src, GL_VERTEX_SHADER);
    unsigned int fisheye_frag = compileShader(fisheye_frag_src, GL_FRAGMENT_SHADER);

    if (!fisheye_vert || !fisheye_frag) return false;

    fisheye_program_ = glCreateProgram();
    glAttachShader(fisheye_program_, fisheye_vert);
    glAttachShader(fisheye_program_, fisheye_frag);
    glLinkProgram(fisheye_program_);

    glGetProgramiv(fisheye_program_, GL_LINK_STATUS, &success);
    if (!success) {
        char infoLog[512];
        glGetProgramInfoLog(fisheye_program_, 512, nullptr, infoLog);
        std::cerr << "Fisheye program linking failed: " << infoLog << std::endl;
        return false;
    }

    glDeleteShader(fisheye_vert);
    glDeleteShader(fisheye_frag);

    return true;
}

bool AudioReactiveSimulation::setupBuffers() {
    glGenVertexArrays(1, &vao_);
    glGenBuffers(1, &vbo_);

    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);

    // Position
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, sizeof(Particle), (void*)offsetof(Particle, position));
    glEnableVertexAttribArray(0);

    // Color
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(Particle), (void*)offsetof(Particle, color));
    glEnableVertexAttribArray(1);

    // Size
    glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, sizeof(Particle), (void*)offsetof(Particle, size));
    glEnableVertexAttribArray(2);

    glBindVertexArray(0);

    return true;
}

bool AudioReactiveSimulation::setupFramebuffer() {
    // Delete old framebuffer if exists
    if (framebuffer_) glDeleteFramebuffers(1, &framebuffer_);
    if (texture_) glDeleteTextures(1, &texture_);

    // Create framebuffer
    glGenFramebuffers(1, &framebuffer_);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);

    // Create texture
    glGenTextures(1, &texture_);
    glBindTexture(GL_TEXTURE_2D, texture_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, window_width_, window_height_, 0, GL_RGB, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture_, 0);

    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        std::cerr << "Framebuffer is not complete!" << std::endl;
        return false;
    }

    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    return true;
}

void AudioReactiveSimulation::renderParticles() {
    glUseProgram(shader_program_);

    // Set aspect ratio uniform
    float aspectRatio = static_cast<float>(window_height_) / static_cast<float>(window_width_);
    int aspectLoc = glGetUniformLocation(shader_program_, "aspectRatio");
    glUniform1f(aspectLoc, aspectRatio);

    // Update VBO with particle data
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferData(GL_ARRAY_BUFFER, particles_.size() * sizeof(Particle), particles_.data(), GL_DYNAMIC_DRAW);

    // Draw particles
    glBindVertexArray(vao_);
    glDrawArrays(GL_POINTS, 0, static_cast<GLsizei>(particles_.size()));
    glBindVertexArray(0);
}

void AudioReactiveSimulation::applyFisheyeEffect() {
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);

    glUseProgram(fisheye_program_);

    // Set uniforms
    int texLoc = glGetUniformLocation(fisheye_program_, "screenTexture");
    int strengthLoc = glGetUniformLocation(fisheye_program_, "fisheyeStrength");
    int centerLoc = glGetUniformLocation(fisheye_program_, "fisheyeCenter");
    int ampLoc = glGetUniformLocation(fisheye_program_, "audioAmplitude");

    glUniform1i(texLoc, 0);
    glUniform1f(strengthLoc, fisheye_strength_);
    glUniform2f(centerLoc, fisheye_center_.x, fisheye_center_.y);
    glUniform1f(ampLoc, current_audio_.amplitude);

    // Bind texture
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, texture_);

    // Fullscreen quad
    static const float quadVertices[] = {
        // pos        // tex
        -1.0f,  1.0f,  0.0f, 1.0f,
        -1.0f, -1.0f,  0.0f, 0.0f,
         1.0f, -1.0f,  1.0f, 0.0f,
        -1.0f,  1.0f,  0.0f, 1.0f,
         1.0f, -1.0f,  1.0f, 0.0f,
         1.0f,  1.0f,  1.0f, 1.0f
    };

    static unsigned int quadVAO = 0, quadVBO = 0;
    if (quadVAO == 0) {
        glGenVertexArrays(1, &quadVAO);
        glGenBuffers(1, &quadVBO);
        glBindVertexArray(quadVAO);
        glBindBuffer(GL_ARRAY_BUFFER, quadVBO);
        glBufferData(GL_ARRAY_BUFFER, sizeof(quadVertices), quadVertices, GL_STATIC_DRAW);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)(2 * sizeof(float)));
    }

    glBindVertexArray(quadVAO);
    glDrawArrays(GL_TRIANGLES, 0, 6);
    glBindVertexArray(0);
}

} // namespace VoiceDialog
