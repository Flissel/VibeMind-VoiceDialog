#pragma once

#include <vector>

namespace VoiceDialog {

/**
 * Audio features extracted from voice/audio input
 * Used to drive visual effects
 */
struct AudioFeatures {
    float amplitude;           // Overall volume (0.0 - 1.0)
    float bass;               // Low frequencies (0.0 - 1.0)
    float mid;                // Mid frequencies (0.0 - 1.0)
    float treble;             // High frequencies (0.0 - 1.0)
    std::vector<float> spectrum;  // Frequency spectrum (64 bins)
    float beat_detected;      // Beat detection (0.0 or 1.0)

    AudioFeatures()
        : amplitude(0.0f), bass(0.0f), mid(0.0f), treble(0.0f),
          spectrum(64, 0.0f), beat_detected(0.0f) {}
};

} // namespace VoiceDialog
