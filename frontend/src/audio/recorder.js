// frontend/src/audio/recorder.js
// WHY this file: manages the microphone capture pipeline on the main JS thread.
// It creates the AudioContext, loads the worklet, connects the mic, and calls
// onChunk(Int16ArrayBuffer) for every 512-sample frame the worklet sends back.
//
// IMPORTANT: AudioContext MUST be created inside a user gesture handler (button press).
// Browsers suspend audio APIs until a real user interaction — this class enforces that.

export class AudioRecorder {
  constructor() {
    // These are set during start() — not here — because AudioContext
    // creation must happen inside a user gesture.
    this._context = null;
    this._stream = null;
    this._sourceNode = null;
    this._workletNode = null;
    this._onChunk = null;
    this._onReady = null;
  }

  /**
   * Start recording.
   *
   * @param {function} onChunk - Called with each Int16Array chunk (as ArrayBuffer).
   * @param {function} onReady - Called once with the actual sample rate being used.
   *
   * WHY async: getUserMedia and audioWorklet.addModule are both Promise-based.
   * We must await them in order — worklet must be registered before we connect the mic.
   */
  async start(onChunk, onReady) {
    this._onChunk = onChunk;
    this._onReady = onReady;

    // Step 1: Try to create AudioContext at 16000 Hz (what Gnani STT wants).
    // Some mobile browsers silently ignore the requested sampleRate and use their
    // native rate instead. We read back context.sampleRate to get the truth.
    let context;
    try {
      context = new AudioContext({ sampleRate: 16000 });
    } catch (err) {
      // Browser rejected 16000 Hz — fall back to whatever the browser prefers.
      // We'll report the actual rate in onReady so the backend can tell Gnani.
      console.warn("[recorder] AudioContext 16000 Hz refused, using default rate:", err.message);
      context = new AudioContext();
    }
    this._context = context;

    // Resume in case the context started in suspended state.
    // WHY: Some browsers start AudioContext suspended even after a user gesture.
    if (context.state === "suspended") {
      await context.resume();
    }

    const actualRate = context.sampleRate;
    console.log(`[recorder] AudioContext sample rate: ${actualRate} Hz`);

    // Step 2: Load the AudioWorklet processor.
    // WHY addModule before getUserMedia: the worklet must be registered before
    // we try to create an AudioWorkletNode from it, or the constructor throws.
    // The path is relative to the page origin — Vite serves public/ at root.
    await context.audioWorklet.addModule("/recorder-worklet.js");

    // Step 3: Request microphone access with settings optimised for voice.
    this._stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,  // mono — Gnani STT wants mono
      },
    });

    // Step 4: Connect mic → worklet.
    this._sourceNode = context.createMediaStreamSource(this._stream);
    this._workletNode = new AudioWorkletNode(context, "recorder-worklet");

    // Step 5: Listen for PCM chunks posted by the worklet.
    this._workletNode.port.onmessage = (event) => {
      // event.data.pcm is the transferred Int16Array (ownership moved here).
      if (this._onChunk) {
        // Pass the underlying ArrayBuffer so the caller can send it via WebSocket.
        this._onChunk(event.data.pcm.buffer);
      }
    };

    // Connect the graph: mic source → worklet (we don't connect to speakers
    // because we don't want mic playback, only capture).
    this._sourceNode.connect(this._workletNode);
    // WHY connect worklet to destination with zero gain: some browsers require
    // the worklet to be connected to the graph output to keep it processing.
    // We achieve this by connecting but NOT routing to speakers explicitly —
    // the worklet processes but its output goes nowhere visible.
    // Actually: some browsers will suspend the worklet if it has no downstream.
    // Safe approach: connect to context.destination.
    // On mobile, this won't play mic through speaker because there's no audio
    // signal from the worklet output (it outputs silence; PCM is sent via port).
    this._workletNode.connect(context.destination);

    // Tell the caller the actual sample rate so they can include it in the
    // WebSocket "start" message to the backend.
    if (this._onReady) {
      this._onReady(actualRate);
    }
  }

  /**
   * Stop recording and release all resources.
   *
   * WHY: not calling stop() leaks the mic stream — the browser keeps
   * the red recording indicator on until all tracks are explicitly stopped.
   */
  stop() {
    // Disconnect audio graph nodes first.
    if (this._workletNode) {
      this._workletNode.port.onmessage = null;
      try { this._workletNode.disconnect(); } catch (_) {}
      this._workletNode = null;
    }
    if (this._sourceNode) {
      try { this._sourceNode.disconnect(); } catch (_) {}
      this._sourceNode = null;
    }

    // Stop all mic tracks — this releases the mic hardware.
    if (this._stream) {
      this._stream.getTracks().forEach((t) => t.stop());
      this._stream = null;
    }

    // Close the AudioContext to free OS audio resources.
    if (this._context) {
      this._context.close().catch(() => {});
      this._context = null;
    }

    this._onChunk = null;
    this._onReady = null;
  }
}
