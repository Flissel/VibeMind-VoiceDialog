#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "audio_features.hpp"
#include "audio_reactive_sim.hpp"

namespace py = pybind11;
using namespace VoiceDialog;

PYBIND11_MODULE(visual_sim_core, m) {
    m.doc() = "Audio-reactive visual simulation core";

    // AudioFeatures struct
    py::class_<AudioFeatures>(m, "AudioFeatures")
        .def(py::init<>())
        .def_readwrite("amplitude", &AudioFeatures::amplitude,
                       "Overall volume (0.0 - 1.0)")
        .def_readwrite("bass", &AudioFeatures::bass,
                       "Low frequencies (0.0 - 1.0)")
        .def_readwrite("mid", &AudioFeatures::mid,
                       "Mid frequencies (0.0 - 1.0)")
        .def_readwrite("treble", &AudioFeatures::treble,
                       "High frequencies (0.0 - 1.0)")
        .def_readwrite("spectrum", &AudioFeatures::spectrum,
                       "Frequency spectrum (64 bins)")
        .def_readwrite("beat_detected", &AudioFeatures::beat_detected,
                       "Beat detection (0.0 or 1.0)");

    // AudioReactiveSimulation class
    py::class_<AudioReactiveSimulation>(m, "AudioReactiveSimulation")
        .def(py::init<int>(),
             py::arg("num_particles") = 100,
             "Create audio-reactive simulation")

        .def("initialize", &AudioReactiveSimulation::initialize,
             py::arg("window_width"), py::arg("window_height"),
             "Initialize OpenGL resources")

        .def("update_audio", &AudioReactiveSimulation::updateAudio,
             py::arg("audio"),
             "Update simulation with audio features")

        .def("update", &AudioReactiveSimulation::update,
             py::arg("delta_time"),
             "Update simulation state")

        .def("render", &AudioReactiveSimulation::render,
             "Render the scene")

        .def("set_fisheye_strength", &AudioReactiveSimulation::setFisheyeStrength,
             py::arg("strength"),
             "Set fisheye effect strength (0.0 - 1.0)")

        .def("set_window_size", &AudioReactiveSimulation::setWindowSize,
             py::arg("width"), py::arg("height"),
             "Update window size")

        .def("cleanup", &AudioReactiveSimulation::cleanup,
             "Cleanup OpenGL resources");
}
