// core/static/js/audio-processor.js

class AudioProcessor extends AudioWorkletProcessor {
    process(inputs) {
        // Get the audio data from the input
        const inputData = inputs[0][0];

        // If there's data, convert it to 16-bit PCM and post it back to the main thread.
        if (inputData) {
            const buffer = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                buffer[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
            }
            this.port.postMessage(buffer.buffer, [buffer.buffer]);
        }
        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);