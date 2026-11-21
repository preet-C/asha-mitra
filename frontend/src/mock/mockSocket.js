// frontend/src/mock/mockSocket.js
// WHY this file: lets P8 UI be developed and demoed without a real backend.
// Replays a scripted session (disclosure → transcript → card fill → danger alert
// → readback → saved) at realistic timing when ?mock=1 is in the URL.
//
// Implements the same interface as a real WebSocket so useVisitSocket.js
// cannot tell the difference — just swap the object.

export function createMockSocket() {
  // We'll store the caller's event handlers here.
  // Real WebSocket uses .onmessage, .onopen, .onclose, .onerror.
  let _onmessage = null;
  let _onopen = null;
  let _onclose = null;
  let _onerror = null;
  let _closed = false;

  // Helper: send a JSON message to the caller as if it came from the server.
  function emit(obj) {
    if (_closed) return;
    if (_onmessage) {
      _onmessage({ data: JSON.stringify(obj) });
    }
  }

  // Helper: send fake binary audio (silence = zero bytes) as an ArrayBuffer.
  function emitBinary(byteLength) {
    if (_closed) return;
    if (_onmessage) {
      _onmessage({ data: new ArrayBuffer(byteLength) });
    }
  }

  // ── scripted session ───────────────────────────────────────────────────────
  // Each entry is [delay_ms, fn]. The fn fires after delay_ms from the
  // previous entry (chained, not from time 0). This makes timing additive
  // so we can read the script top-to-bottom like a storyboard.
  //
  // WHY chained delays not absolute: easier to adjust pacing — just change
  // one number and everything after it shifts accordingly.

  function runScript() {
    const steps = [
      // Backend signals it's ready.
      [100, () => emit({ type: "ready" })],

      // AI disclosure — the first thing the agent always says (Tier A, locked).
      // We simulate ~3 s of TTS playback with silent bytes so the player path
      // is exercised. Real TTS is 24000 Hz PCM16.
      [300, () => emit({ type: "tts_start", sample_rate: 24000, text: "Hello. I am an AI assistant. I help you record this home visit. I can make mistakes, so please check what I read back." })],
      [500, () => emitBinary(2048)],   // chunk 1
      [300, () => emitBinary(2048)],   // chunk 2
      [300, () => emitBinary(2048)],   // chunk 3
      [600, () => emit({ type: "tts_end" })],

      // Worker speaks — backend sends back the transcript.
      [800, () => emit({
        type: "transcript",
        text: "ID 1042, baby weight two kilo eight hundred gram, Penta 1 given today, next visit December fifth, baby has high fever since morning",
      })],

      // Card fills in — weight + vaccines come in first (partial fill).
      [600, () => emit({
        type: "card",
        draft: {
          beneficiary_id: "1042",
          weight_kg: 2.8,
          vaccines_given_today: ["PENTA1"],
          next_visit_date: null,
          vaccines_due: [],
        },
        uncertain: ["weight_kg"],  // weight uncertain until confirmed
      })],

      // Next visit date added, weight still uncertain.
      [700, () => emit({
        type: "card",
        draft: {
          beneficiary_id: "1042",
          weight_kg: 2.8,
          vaccines_given_today: ["PENTA1"],
          next_visit_date: "2026-12-05",
          vaccines_due: ["OPV1"],
        },
        uncertain: ["weight_kg"],
      })],

      // ⚠ Danger alert — fires BEFORE readback (plan rule: danger first).
      [500, () => emit({
        type: "alert",
        signs: [{ id: "NB_FEVER_OR_COLD", label: "Fever or cold to touch" }],
      })],

      // Refer PHC TTS (pre-rendered Tier A line).
      [200, () => emit({ type: "tts_start", sample_rate: 24000, text: "Danger sign: Fever or cold to touch. Refer to the PHC now." })],
      [400, () => emitBinary(2048)],
      [400, () => emitBinary(2048)],
      [400, () => emit({ type: "tts_end" })],

      // Readback TTS — agent reads back all 5 fields.
      [500, () => emit({ type: "tts_start", sample_rate: 24000, text: "Beneficiary 1042. Weight two kilo eight hundred gram — please check. Penta 1 given today. OPV 1 is due. Next visit December fifth. Danger sign: Fever or cold to touch. Is that correct?" })],
      [600, () => emitBinary(2048)],
      [400, () => emitBinary(2048)],
      [400, () => emitBinary(2048)],
      [600, () => emit({ type: "tts_end" })],

      // Worker says "haan" (yes) — card turns all green (uncertain:[]).
      [800, () => emit({ type: "transcript", text: "haan" })],

      [300, () => emit({
        type: "card",
        draft: {
          beneficiary_id: "1042",
          weight_kg: 2.8,
          vaccines_given_today: ["PENTA1"],
          next_visit_date: "2026-12-05",
          vaccines_due: ["OPV1"],
        },
        uncertain: [],  // all confirmed — all fields turn green
      })],

      // Latency badge (simulated — real value comes from gateway timing).
      [100, () => emit({ type: "latency", what: "first_audio", ms: 812 })],

      // Saved — session complete.
      [600, () => emit({ type: "saved", visit_id: "mock-visit-001" })],

      // Saved TTS.
      [200, () => emit({ type: "tts_start", sample_rate: 24000, text: "Saved. Visit recorded." })],
      [400, () => emitBinary(2048)],
      [300, () => emit({ type: "tts_end" })],
    ];

    // Chain the steps using setTimeout so each fires after the previous one.
    let chain = Promise.resolve();
    for (const [delay, fn] of steps) {
      chain = chain.then(
        () => new Promise((resolve) => setTimeout(() => { fn(); resolve(); }, delay))
      );
    }
  }

  // ── public interface (matches real WebSocket) ──────────────────────────────

  const mockSocket = {
    // Callers set these properties just like a real WebSocket.
    set onmessage(fn) { _onmessage = fn; },
    get onmessage() { return _onmessage; },
    set onopen(fn) { _onopen = fn; },
    get onopen() { return _onopen; },
    set onclose(fn) { _onclose = fn; },
    get onclose() { return _onclose; },
    set onerror(fn) { _onerror = fn; },
    get onerror() { return _onerror; },

    readyState: 1, // 1 = OPEN, same as WebSocket.OPEN

    // send() is called by useVisitSocket to send JSON control frames and binary audio.
    // We react to "start" to kick off the scripted session.
    send(data) {
      if (_closed) return;
      if (typeof data === "string") {
        let msg;
        try { msg = JSON.parse(data); } catch { return; }

        if (msg.type === "start") {
          // User selected a language and the socket hook sent "start".
          // Begin the scripted demo session.
          runScript();
        }
        // Other messages (commit, barge_in, end) are silently accepted.
      }
      // Binary audio frames are silently dropped — the mock doesn't echo audio.
    },

    close() {
      _closed = true;
      mockSocket.readyState = 3; // 3 = CLOSED
      if (_onclose) _onclose({ code: 1000, reason: "mock closed" });
    },
  };

  // Fire onopen asynchronously (mimics real WebSocket handshake timing).
  setTimeout(() => {
    if (_onopen) _onopen({});
  }, 50);

  return mockSocket;
}
