// Run from a terminal: pw-jack sclang -D play.scd
// Loads our compiled VST3, plays MIDI and writes demo.wav beside this script.
(
var directory = thisProcess.nowExecutingPath.dirname;
var plugin = directory +/+ "build/SynthLab_artefacts/Release/VST3/Synth Lab.vst3";
var recording = directory +/+ "demo.wav";

if(PathName(plugin).isFolder.not) {
    "Build the VST3 first; see README.md".error;
    1.exit;
};

s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.sampleRate = 48000;
s.recHeaderFormat = "WAV";
s.recSampleFormat = "int16";

s.waitForBoot({
    SynthDef(\vstInstrument, {
        Out.ar(0, VSTPlugin.ar(nil, 2));
    }).add;
    s.sync;

    ~instrument = Synth(\vstInstrument);
    ~vst = VSTPluginController(~instrument);
    ~vst.open(plugin, editor: false, action: { |controller, success|
        if(success.not) {
            "VST3 failed to load".error;
            s.quit({ 1.exit });
        } {
            fork {
                "Loaded VST3: Synth Lab".postln;
                controller.info.printParameters;
                s.prepareForRecord(recording, numChannels: 2);
                s.sync;
                s.record;
                0.2.wait;

                [60, 64, 67, 72, 67, 64, 60, 55].do({ |note|
                    s.bind { controller.midi.noteOn(0, note, 90) };
                    0.3.wait;
                    s.bind { controller.midi.noteOff(0, note) };
                    0.1.wait;
                });

                // Set an exposed VST parameter, then play a chord.
                controller.set("Brightness", 0.9);
                s.bind {
                    [60, 64, 67].do { |note| controller.midi.noteOn(0, note, 70) };
                };
                1.wait;
                s.bind {
                    [60, 64, 67].do { |note| controller.midi.noteOff(0, note) };
                };
                1.wait;
                s.stopRecording;
                s.sync;
                ~instrument.free;
                ("Recorded: " ++ recording).postln;
                s.quit({ 0.exit });
            };
        };
    });
}, onFailure: { "Audio server failed to boot".error; 1.exit });
)
