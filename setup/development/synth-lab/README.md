# Synth Lab

An editable C++/JUCE VST3 instrument, sequenced by SuperCollider. This builds a
native Linux plugin; SuperCollider's VSTPlugin extension hosts it.

## Build

```bash
cd ~/Projects/synth-lab
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --target SynthLab_VST3 --parallel 2
```

JUCE is preinstalled at `~/.local/share/minion/audio/JUCE-9.0.4`. To use another
checkout, pass `-DJUCE_SOURCE_DIR=/path/to/JUCE` when configuring.

The plugin bundle is `build/SynthLab_artefacts/Release/VST3/Synth Lab.vst3`.
It accepts MIDI and has 16 voices, an amplitude envelope, and Gain/Brightness
parameters. It has no custom graphical editor; hosts can expose its parameters.
Edit `Synth.cpp` to change the synthesis algorithm and rebuild. Stop the host
before rebuilding or loading the replacement plugin.

## Play and record

```bash
pw-jack sclang -D play.scd
pw-play demo.wav
```

`pw-jack` connects the audio server to the existing PipeWire session. The script
loads the VST3 directly from the build directory, prints its parameters, plays a
melody and a chord, records the output to `demo.wav`, then exits. It records only
the synth output; no microphone input is opened. Edit `play.scd` for notes,
timing, chords and parameter changes. Run at a comfortable speaker volume.

For a terminal session without a display connection, use:

```bash
QT_QPA_PLATFORM=offscreen pw-jack sclang -D play.scd
```

## Use it elsewhere

To make this VST3 visible in other hosts, copy the whole `Synth Lab.vst3` bundle
into `~/.vst3/`, then scan plugins in the host. That copy must be updated after
rebuilding; this SuperCollider example always loads the current build directly.

JUCE and VSTPlugin sources are pinned by the distro's audio setup manifest. Setup
reruns retain this project, including your edits and generated files.

References: [JUCE CMake API](https://github.com/juce-framework/JUCE/blob/master/docs/CMake%20API.md),
[VSTPlugin](https://github.com/Spacechild1/vstplugin),
[VST controller API](https://github.com/Spacechild1/vstplugin/blob/master/sc/HelpSource/Classes/VSTPluginController.schelp).
