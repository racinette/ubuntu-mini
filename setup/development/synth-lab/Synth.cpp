// A native VST3 instrument: 16 voices, MIDI, envelopes and host parameters.
#include <juce_audio_processors/juce_audio_processors.h>
#include <cmath>

class Sound final : public juce::SynthesiserSound
{
public:
    bool appliesToNote(int) override { return true; }
    bool appliesToChannel(int) override { return true; }
};

class Voice final : public juce::SynthesiserVoice
{
public:
    Voice(std::atomic<float>& gainControl, std::atomic<float>& brightnessControl)
        : gain(gainControl), brightness(brightnessControl) {}

    bool canPlaySound(juce::SynthesiserSound* sound) override
    { return dynamic_cast<Sound*>(sound) != nullptr; }

    void startNote(int note, float velocity, juce::SynthesiserSound*, int) override
    {
        phase = 0.0;
        increment = juce::MathConstants<double>::twoPi
            * juce::MidiMessage::getMidiNoteInHertz(note) / getSampleRate();
        level = velocity;
        envelope.setSampleRate(getSampleRate());
        envelope.setParameters({0.01f, 0.12f, 0.65f, 0.25f});
        envelope.noteOn();
    }

    void stopNote(float, bool allowTailOff) override
    {
        envelope.noteOff();
        if (!allowTailOff) { envelope.reset(); clearCurrentNote(); }
    }

    void pitchWheelMoved(int) override {}
    void controllerMoved(int, int) override {}

    void renderNextBlock(juce::AudioBuffer<float>& output, int start, int count) override
    {
        const auto volume = gain.load() * level;
        const auto colour = brightness.load();
        while (count-- > 0)
        {
            // Replace this oscillator/mixing code to design your own sound.
            const auto wave = (std::sin(phase) + colour * 0.3 * std::sin(phase * 3.0))
                / (1.0 + colour * 0.3);
            const auto sample = static_cast<float>(wave) * volume * envelope.getNextSample();
            phase = std::fmod(phase + increment, juce::MathConstants<double>::twoPi);
            for (int channel = 0; channel < output.getNumChannels(); ++channel)
                output.addSample(channel, start, sample);
            ++start;
            if (!envelope.isActive()) { clearCurrentNote(); break; }
        }
    }

private:
    std::atomic<float>& gain;
    std::atomic<float>& brightness;
    juce::ADSR envelope;
    double phase = 0.0, increment = 0.0;
    float level = 0.0f;
};

class SynthLab final : public juce::AudioProcessor
{
public:
    SynthLab()
        : AudioProcessor(BusesProperties().withOutput("Output", juce::AudioChannelSet::stereo(), true)),
          parameters(*this, nullptr, "Parameters", {
              std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"gain", 1},
                  "Gain", 0.0f, 0.3f, 0.08f),
              std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"brightness", 1},
                  "Brightness", 0.0f, 1.0f, 0.25f)})
    {
        for (int i = 0; i < 16; ++i)
            synth.addVoice(new Voice(*parameters.getRawParameterValue("gain"),
                                     *parameters.getRawParameterValue("brightness")));
        synth.addSound(new Sound());
    }

    const juce::String getName() const override { return "Synth Lab"; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.25; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    bool hasEditor() const override { return false; }
    juce::AudioProcessorEditor* createEditor() override { return nullptr; }

    void prepareToPlay(double rate, int) override { synth.setCurrentPlaybackSampleRate(rate); }
    void releaseResources() override { synth.allNotesOff(0, false); }
    bool isBusesLayoutSupported(const BusesLayout& layout) const override
    {
        return layout.getMainInputChannelSet().isDisabled()
            && (layout.getMainOutputChannelSet() == juce::AudioChannelSet::mono()
                || layout.getMainOutputChannelSet() == juce::AudioChannelSet::stereo());
    }
    void processBlock(juce::AudioBuffer<float>& output, juce::MidiBuffer& midi) override
    {
        juce::ScopedNoDenormals noDenormals;
        output.clear();
        synth.renderNextBlock(output, midi, 0, output.getNumSamples());
    }
    void getStateInformation(juce::MemoryBlock& data) override
    { if (auto xml = parameters.copyState().createXml()) copyXmlToBinary(*xml, data); }
    void setStateInformation(const void* data, int bytes) override
    {
        if (auto xml = getXmlFromBinary(data, bytes))
            if (xml->hasTagName(parameters.state.getType()))
                parameters.replaceState(juce::ValueTree::fromXml(*xml));
    }

private:
    juce::AudioProcessorValueTreeState parameters;
    juce::Synthesiser synth;
};

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new SynthLab(); }
