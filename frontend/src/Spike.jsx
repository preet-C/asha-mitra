// frontend/src/Spike.jsx
// WHY this file: temporary test page (P9 audio spike). Proves the full pipeline:
// phone mic → PCM16 → WebSocket → backend loopback.py → 440 Hz tone → browser speaker.
// Delete or ignore this file once P10 (real Gnani gateway) is working.
//
// Open at http://localhost:5173/spike (or /?spike=1 — see App.jsx link at the bottom).

import { useEffect, useRef, useState } from "react";
import { AudioRecorder } from "./audio/recorder";
import { AudioPlayer } from "./audio/player";

// Determine WebSocket protocol based on page protocol.
// WHY: on HTTPS (cloudflared tunnel) we need wss://, on HTTP we need ws://.
function wsUrl(path) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}

export default function Spike() {
  const [status, setStatus] = useState("idle"); // idle | recording | waiting | playing | done | error
  const [lines, setLines] = useState([]);        // transcript / event log lines shown in <pre>

  // Refs hold mutable objects that shouldn't trigger re-renders.
  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const playerRef = useRef(null);
  const ttsActiveRef = useRef(false);  // true while backend is streaming audio back
  const sampleRateRef = useRef(16000); // updated when recorder reports actual rate

  // ── open WebSocket on mount ────────────────────────────────────────────────
  useEffect(() => {
    const ws = new WebSocket(wsUrl("/ws/loopback"));
    wsRef.current = ws;
    ws.binaryType = "arraybuffer"; // WHY: we receive binary PCM — arraybuffer is easier to pass to player

    ws.onopen = () => {
      log("WebSocket open — hold the button to record");
      setStatus("idle");
    };

    ws.onmessage = async (evt) => {
      if (evt.data instanceof ArrayBuffer) {
        // Binary frame = PCM16 audio chunk from backend tone
        if (ttsActiveRef.current && playerRef.current) {
          await playerRef.current.enqueue(evt.data, 24000);
        }
        return;
      }

      // Text frame = JSON control message
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }

      if (msg.type === "tts_start") {
        log(`← tts_start (sample_rate=${msg.sample_rate})`);
        ttsActiveRef.current = true;
        playerRef.current = new AudioPlayer();
        setStatus("playing");
      } else if (msg.type === "tts_end") {
        log("← tts_end — tone complete");
        ttsActiveRef.current = false;
        setStatus("done");
      } else if (msg.type === "ready") {
        log("← ready");
      } else {
        log(`← ${JSON.stringify(msg)}`);
      }
    };

    ws.onerror = () => {
      log("WebSocket error");
      setStatus("error");
    };

    ws.onclose = () => {
      log("WebSocket closed");
    };

    // Clean up on unmount
    return () => {
      ws.close();
      recorderRef.current?.stop();
      playerRef.current?.close();
    };
  }, []);

  // ── log helper ─────────────────────────────────────────────────────────────
  function log(text) {
    setLines((prev) => [...prev, text]);
  }

  // ── button press: start recording ─────────────────────────────────────────
  async function handlePressStart(e) {
    e.preventDefault(); // prevent scroll / text selection on mobile

    // If agent is speaking, barge in (stop audio + tell backend)
    if (ttsActiveRef.current) {
      playerRef.current?.stop();
      ttsActiveRef.current = false;
      wsRef.current?.send(JSON.stringify({ type: "barge_in" }));
      log("→ barge_in");
      setStatus("recording");
      // Fall through to start a new recording right away
    }

    // Create a fresh recorder for each press
    recorderRef.current?.stop();
    const recorder = new AudioRecorder();
    recorderRef.current = recorder;

    setStatus("recording");
    log("→ starting recorder...");

    try {
      await recorder.start(
        // onChunk: called for every 512-sample PCM16 frame
        (chunkBuffer) => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(chunkBuffer);
          }
        },
        // onReady: called once with the actual AudioContext sample rate
        (rate) => {
          sampleRateRef.current = rate;
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              type: "start",
              sample_rate: rate,
            }));
          }
          log(`→ start (sample_rate=${rate})`);
        }
      );
    } catch (err) {
      log(`recorder error: ${err.message}`);
      setStatus("error");
    }
  }

  // ── button release: commit ─────────────────────────────────────────────────
  function handlePressEnd(e) {
    e.preventDefault();
    recorderRef.current?.stop();
    recorderRef.current = null;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "commit" }));
      log("→ commit");
    }
    setStatus("waiting");
  }

  // ── status label ───────────────────────────────────────────────────────────
  const statusLabel = {
    idle: "Idle — hold button to record",
    recording: "🎙 Recording...",
    waiting: "⏳ Waiting for tone...",
    playing: "🔊 Playing tone...",
    done: "✅ Done — hold button to record again",
    error: "❌ Error — check console",
  }[status] || status;

  return (
    <div style={styles.page}>
      <h2 style={styles.title}>P9 Audio Spike</h2>
      <p style={styles.subtitle}>
        Hold the button → speak → release → hear 440 Hz tone back
      </p>

      {/* Status line */}
      <p style={styles.statusLine}>{statusLabel}</p>

      {/* Hold-to-talk button */}
      <button
        style={{
          ...styles.holdButton,
          background: status === "recording" ? "#c0392b" : "#2c3e50",
        }}
        onPointerDown={handlePressStart}
        onPointerUp={handlePressEnd}
        onPointerCancel={handlePressEnd}
        // Prevent the button from losing pointer capture on mobile scroll
        onTouchStart={(e) => e.preventDefault()}
      >
        {status === "recording" ? "🎙" : "🎤"}
        <br />
        <span style={{ fontSize: "14px" }}>Hold to Record</span>
      </button>

      {/* Event log */}
      <pre style={styles.log}>
        {lines.join("\n")}
      </pre>
    </div>
  );
}

// ── inline styles (no CSS file needed for a temp spike page) ──────────────────
const styles = {
  page: {
    fontFamily: "sans-serif",
    maxWidth: "480px",
    margin: "0 auto",
    padding: "16px",
    textAlign: "center",
  },
  title: {
    fontSize: "20px",
    marginBottom: "4px",
  },
  subtitle: {
    fontSize: "14px",
    color: "#666",
    marginBottom: "16px",
  },
  statusLine: {
    fontSize: "16px",
    minHeight: "24px",
    marginBottom: "24px",
    fontWeight: "bold",
  },
  holdButton: {
    width: "120px",
    height: "120px",
    borderRadius: "50%",
    border: "none",
    color: "white",
    fontSize: "32px",
    cursor: "pointer",
    touchAction: "none",  // WHY: prevents browser scroll/zoom while holding button
    userSelect: "none",
    marginBottom: "24px",
    display: "inline-flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "4px",
  },
  log: {
    textAlign: "left",
    background: "#1a1a2e",
    color: "#a8ff78",
    padding: "12px",
    borderRadius: "8px",
    fontSize: "13px",
    minHeight: "120px",
    maxHeight: "300px",
    overflowY: "auto",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
};
