cmake_minimum_required(VERSION 3.22)
project(SynthLab VERSION 0.1.0 LANGUAGES C CXX)

set(JUCE_SOURCE_DIR "$ENV{HOME}/.local/share/minion/audio/JUCE-9.0.4"
    CACHE PATH "JUCE source checkout")
add_subdirectory("${JUCE_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/JUCE")

juce_add_plugin(SynthLab
    COMPANY_NAME "Synth Lab"
    BUNDLE_ID "org.synthlab.instrument"
    PLUGIN_MANUFACTURER_CODE SyLb
    PLUGIN_CODE Sl01
    PRODUCT_NAME "Synth Lab"
    IS_SYNTH TRUE
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT FALSE
    FORMATS VST3
    COPY_PLUGIN_AFTER_BUILD FALSE)
target_sources(SynthLab PRIVATE Synth.cpp)
target_compile_features(SynthLab PRIVATE cxx_std_17)
target_compile_definitions(SynthLab PUBLIC
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0)
target_link_libraries(SynthLab PRIVATE juce::juce_audio_processors
    PUBLIC juce::juce_recommended_config_flags)
