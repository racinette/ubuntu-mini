// Run: pw-jack sclang -D setup/development/effects-demo.scd
// Generates quiet test audio; opens no input and sends nothing to the speakers.
// WAV channels 1/2 are dry; channels 3/4 are processed. See the setup docs.
(
var cache = "XDG_CACHE_HOME".getenv ? (Platform.userHomeDir +/+ ".cache");
var directory = cache +/+ "minion/audio/effects-demo";
var plugins = [
    "AIDA-X.vst3", "BYOD.vst3",
    "Dragonfly Early Reflections.vst3", "Dragonfly Hall Reverb.vst3",
    "Dragonfly Plate Reverb.vst3", "Dragonfly Room Reverb.vst3",
    "Compressor Stereo.vst3", "Gate Stereo.vst3", "Parametric Equalizer x16 Stereo.vst3"
];
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.sampleRate = 48000;
s.recHeaderFormat = "WAV";
s.recSampleFormat = "float";

s.waitForBoot({
    VSTPlugin.search(s, ["/usr/lib/vst3", Platform.userHomeDir +/+ ".vst3"],
        options: (parallel: false, timeout: 20), verbose: false, action: {
            fork {
                try {
                    SynthDef(\effectCheck, { |sourceOn=0|
                        var envelope = Decay2.ar(Impulse.ar(3), 0.005, 0.2);
                        var dry = ((SinOsc.ar([110, 165]) * 0.08) + (PinkNoise.ar(0.02) ! 2))
                            * envelope * sourceOn;
                        var wet = VSTPlugin.ar(dry, 2);
                        Out.ar(2, dry ++ wet);
                    }).add;
                    s.sync;
                    plugins.do { |key, index|
                        var synth, controller, ready = Condition.new, loaded = false;
                        var recording = directory +/+ (index.asString ++ ".wav");
                        synth = Synth(\effectCheck);
                        controller = VSTPluginController(synth);
                        controller.open(key, editor: false, action: { |host, success|
                            loaded = success;
                            ready.unhang;
                        });
                        ready.hang;
                        if(loaded.not) { Error("Failed to load " ++ key).throw };
                        ("Loaded: " ++ key).postln;
                        controller.info.printParameters;
                        s.prepareForRecord(recording, numChannels: 4);
                        s.sync;
                        s.record(bus: 2);
                        synth.set(\sourceOn, 1);
                        2.wait;
                        synth.set(\sourceOn, 0);
                        0.8.wait;
                        s.stopRecording;
                        s.sync;
                        synth.free;
                        s.sync;
                        ("Rendered: " ++ key ++ " -> " ++ recording).postln;
                    };
                    File.use(directory +/+ "plugins.txt", "w", { |file|
                        plugins.do { |key| file.write(key ++ "\n") };
                    });
                    s.quit({ 0.exit });
                } { |error|
                    error.reportError;
                    s.quit({ 1.exit });
                };
            };
        });
}, onFailure: { "Audio server failed to boot".error; 1.exit });
)
