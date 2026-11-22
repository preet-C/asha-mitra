// frontend/public/recorder-worklet.js
/* global AudioWorkletProcessor, registerProcessor */

// WHY this file: AudioWorklet runs in the real-time audio thread (separate from
// the main JS thread), so it can collect mic samples without dropping them.
// It converts Float32 → Int16 PCM and posts 512-sample chunks to the main thread.
//
// RULES: No DOM. No fetch. No console.log. Keep it tiny — this runs every audio frame.

class RecorderWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    // WHY 512-sample buffer: 512 samples × 2 bytes = 1024 bytes per chunk.
    // Gnani STT wants exactly 1024 bytes per frame (512 Int16 samples).
    this._buffer = new Int16Array(512);
    this._bufferIndex = 0;
  }

  process(inputs) {
    // inputs[0][0] is the first channel of the first input (mono mic).
    // If no input is connected yet, inputs[0] may be empty — guard against it.
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true; // return true = keep processor alive

    for (let i = 0; i < channel.length; i++) {
      // Clamp Float32 sample to [-1, 1] then scale to Int16 range.
      // WHY clamp: mic can occasionally produce values slightly outside [-1,1]
      // due to gain stages; clamping prevents Int16 overflow.
      const sample = Math.max(-1, Math.min(1, channel[i]));
      this._buffer[this._bufferIndex] = Math.round(sample * 32767);
      this._bufferIndex++;

      if (this._bufferIndex === 512) {
        // Buffer is full — send it to the main thread.
        // WHY transfer ownership (.buffer): avoids copying 1024 bytes;
        // the ArrayBuffer moves to the main thread instead of being cloned.
        this.port.postMessage({ pcm: this._buffer }, [this._buffer.buffer]);

        // Create a fresh buffer for the next 512 samples.
        this._buffer = new Int16Array(512);
        this._bufferIndex = 0;
      }
    }

    // return true = keep the processor node alive
    return true;
  }
}

registerProcessor("recorder-worklet", RecorderWorklet);
