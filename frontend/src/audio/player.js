// frontend/src/audio/player.js
// WHY this file: plays PCM16 audio chunks received from the backend (TTS stream).
// Schedules AudioBufferSourceNodes back-to-back so there are no gaps between chunks.
// stop() cancels all queued audio immediately — used for barge-in (button press
// while agent is speaking).
//
// AudioContext is created lazily on first play (requires a prior user gesture).

export class AudioPlayer {
  constructor() {
    this._context = null;
    // nextPlayTime tracks when the last queued buffer ends so we can schedule
    // the next one to start exactly there (gapless playback).
    this._nextPlayTime = 0;
    // Keep references to all queued source nodes so stop() can kill them.
    this._sources = [];
  }

  /**
   * Lazily create (or resume) the AudioContext.
   *
   * WHY lazy: AudioContext creation needs a prior user gesture. By the time
   * enqueue() is first called (the user pressed the button already), the
   * gesture constraint is satisfied.
   */
  async _ensureContext() {
    if (!this._context) {
      // WHY no sampleRate here: we don't know the TTS rate at construction time.
      // We pass the rate per-chunk in enqueue(). The AudioBuffer accepts any rate.
      this._context = new AudioContext();
    }
    if (this._context.state === "suspended") {
      await this._context.resume();
    }
  }

  /**
   * Decode one PCM16 chunk and queue it for playback.
   *
   * @param {ArrayBuffer} pcm16bytes - Raw Int16 little-endian PCM bytes.
   * @param {number} sampleRate      - Sample rate of this audio (e.g. 24000).
   */
  async enqueue(pcm16bytes, sampleRate) {
    await this._ensureContext();
    const ctx = this._context;

    // Convert Int16 bytes → Float32 samples.
    // WHY: Web Audio API works with Float32 in range [-1, 1]; PCM16 uses Int16
    // in range [-32768, 32767]. We divide by 32768 to normalise.
    const int16 = new Int16Array(pcm16bytes);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    // Create an AudioBuffer from the float samples.
    const audioBuffer = ctx.createBuffer(1, float32.length, sampleRate);
    audioBuffer.copyToChannel(float32, 0);

    // Schedule this chunk to play exactly when the previous chunk ends.
    // WHY: AudioBufferSourceNode is a "fire and forget" — once started it
    // plays its buffer and stops. We chain them by scheduling each one at
    // the end time of the last one (nextPlayTime).
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    // Start time: whichever is later — right now (if we've fallen behind)
    // or exactly after the last chunk (normal gapless case).
    const startAt = Math.max(ctx.currentTime, this._nextPlayTime);
    source.start(startAt);

    // Advance the pointer by the duration of this chunk.
    this._nextPlayTime = startAt + audioBuffer.duration;

    // Track this source so stop() can cancel it.
    this._sources.push(source);

    // Clean up reference when the source finishes naturally.
    source.onended = () => {
      this._sources = this._sources.filter((s) => s !== source);
    };
  }

  /**
   * Immediately stop all queued and playing audio.
   *
   * WHY: barge-in — the ASHA worker presses the button while the agent is
   * speaking. We must cut audio in < 300 ms (P9 requirement).
   */
  stop() {
    // Stop every queued source node.
    for (const source of this._sources) {
      try {
        source.stop();
      } catch (_) {
        // source.stop() throws if the source has already finished — ignore.
      }
    }
    this._sources = [];

    // Reset the play pointer so the next enqueue() starts from "now".
    if (this._context) {
      this._nextPlayTime = this._context.currentTime;
    } else {
      this._nextPlayTime = 0;
    }
  }

  /**
   * Release all resources. Call when the session ends.
   */
  close() {
    this.stop();
    if (this._context) {
      this._context.close().catch(() => {});
      this._context = null;
    }
  }
}
