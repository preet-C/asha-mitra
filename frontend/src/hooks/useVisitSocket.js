// frontend/src/hooks/useVisitSocket.js
// WHY this file: single place that owns the WebSocket connection for one visit session.
// Returns reactive state (transcript, card draft, alerts, etc.) and action functions
// (sendAudio, sendCommit, sendBargeIn) so components stay simple and dumb.
//
// When mock=true (URL has ?mock=1) it plugs in mockSocket instead of a real WebSocket.
// The rest of the app cannot tell the difference — same interface, same message shapes.

import { useCallback, useEffect, useRef, useState } from "react";
import { createMockSocket } from "../mock/mockSocket";

// ── reconnect settings ─────────────────────────────────────────────────────────
const MAX_RETRIES = 3;        // give up after this many failed reconnects
const BACKOFF_BASE_MS = 1000; // first retry after 1 s, then 2 s, then 4 s

// ── WebSocket URL helper ───────────────────────────────────────────────────────
function wsUrl(path) {
  // WHY: cloudflared tunnel uses HTTPS → wss; local dev uses HTTP → ws.
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}

/**
 * useVisitSocket — React hook for the visit session WebSocket.
 *
 * @param {string}   lang     - Selected language code, e.g. "hi-IN".
 * @param {boolean}  mock     - If true, use mockSocket instead of a real server.
 * @param {function} onTtsStart  - Called with { sampleRate } when TTS stream begins.
 * @param {function} onTtsChunk  - Called with ArrayBuffer for each binary audio chunk.
 * @param {function} onTtsEnd    - Called when TTS stream finishes.
 *
 * @returns {object} Reactive state + action functions (see return statement).
 */
export function useVisitSocket({ lang, mock, enabled = true, onTtsStart, onTtsChunk, onTtsEnd }) {
  // ── reactive state ───────────────────────────────────────────────────────────
  const [status, setStatus] = useState("connecting"); // connecting | ready | error | closed
  const [transcript, setTranscript] = useState("");
  const [draft, setDraft] = useState({});        // VisitDraft shape (contract 4.1)
  const [uncertain, setUncertain] = useState([]); // list of uncertain field names
  const [alerts, setAlerts] = useState([]);       // accumulated danger sign objects
  const [latencyMs, setLatencyMs] = useState(null);
  const [savedId, setSavedId] = useState(null);
  const [currentLang, setCurrentLang] = useState(lang);
  const [speed, setSpeed] = useState(1.0);

  // ── internal refs ────────────────────────────────────────────────────────────
  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const ttsActiveRef = useRef(false); // true while receiving TTS binary frames

  // ── open (or re-open) the WebSocket ──────────────────────────────────────────
  const connect = useCallback(() => {
    // Clean up any existing socket before making a new one.
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      try { wsRef.current.close(); } catch (_) {}
    }

    const ws = mock ? createMockSocket() : new WebSocket(wsUrl("/ws/session"));
    wsRef.current = ws;
    ws.binaryType = "arraybuffer"; // WHY: binary audio comes as ArrayBuffer

    ws.onopen = () => {
      retriesRef.current = 0; // reset retry count on successful connect
      setStatus("connecting"); // still connecting until "ready" message
      // Send the "start" frame immediately so the backend knows the language.
      ws.send(JSON.stringify({ type: "start", lang, sample_rate: 16000 }));
    };

    ws.onmessage = (evt) => {
      // Binary frame = PCM16 audio chunk (TTS stream)
      if (evt.data instanceof ArrayBuffer) {
        if (ttsActiveRef.current && onTtsChunk) {
          onTtsChunk(evt.data);
        }
        return;
      }

      // Text frame = JSON control message
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }

      switch (msg.type) {
        case "ready":
          setStatus("ready");
          break;

        case "transcript":
          setTranscript(msg.text || "");
          break;

        case "card":
          // Replace draft and uncertain list entirely (server sends full state).
          setDraft(msg.draft || {});
          setUncertain(msg.uncertain || []);
          break;

        case "alert":
          // Append new signs; never clear — banner stays for whole session.
          setAlerts((prev) => {
            const existingIds = new Set(prev.map((s) => s.id));
            const newSigns = (msg.signs || []).filter((s) => !existingIds.has(s.id));
            return [...prev, ...newSigns];
          });
          break;

        case "tts_start":
          ttsActiveRef.current = true;
          if (onTtsStart) onTtsStart({ sampleRate: msg.sample_rate });
          break;

        case "tts_end":
          ttsActiveRef.current = false;
          if (onTtsEnd) onTtsEnd();
          break;

        case "latency":
          if (msg.what === "first_audio") setLatencyMs(msg.ms);
          break;

        case "saved":
          setSavedId(msg.visit_id || "saved");
          break;

        case "setting":
          // Voice command changed language or speed.
          if (msg.lang) setCurrentLang(msg.lang);
          if (msg.speed != null) setSpeed(msg.speed);
          break;

        case "error":
          console.error("[socket] server error:", msg.message);
          setStatus("error");
          break;

        default:
          // Unknown message types are silently ignored (forward compatibility).
          break;
      }
    };

    ws.onerror = () => {
      // onerror always fires before onclose on connection failure.
      // We handle retry in onclose to avoid double-triggering.
      console.warn("[socket] WebSocket error");
    };

    ws.onclose = (evt) => {
      ttsActiveRef.current = false;
      const isNormalClose = evt.code === 1000 || evt.code === 1001;

      if (isNormalClose) {
        setStatus("closed");
        return;
      }

      // Abnormal close — try to reconnect with exponential backoff.
      if (retriesRef.current < MAX_RETRIES) {
        const delay = BACKOFF_BASE_MS * Math.pow(2, retriesRef.current);
        retriesRef.current++;
        console.warn(`[socket] closed (code ${evt.code}), retrying in ${delay} ms (attempt ${retriesRef.current})`);
        setStatus("connecting");
        setTimeout(connect, delay);
      } else {
        console.error("[socket] max retries reached — giving up");
        setStatus("error");
      }
    };
  }, [lang, mock, onTtsStart, onTtsChunk, onTtsEnd]);

  // Open socket only when enabled (i.e. after language is picked).
  // WHY: if we connect at mount, the mock session fires during the language
  // picker screen and is already finished by the time the user reaches the
  // session screen — they'd see empty state. enabled=false = no socket at all.
  useEffect(() => {
    if (!enabled) return; // wait until language is chosen
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        try { wsRef.current.close(1000); } catch (_) {}
      }
    };
  }, [connect, enabled]);

  // ── action functions ───────────────────────────────────────────────────────
  // These are stable references (no deps that change) so components can use
  // them in event handlers without re-subscribing.

  const sendAudio = useCallback((arrayBuffer) => {
    if (wsRef.current?.readyState === 1 /* OPEN */) {
      wsRef.current.send(arrayBuffer);
    }
  }, []);

  const sendCommit = useCallback(() => {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify({ type: "commit" }));
    }
  }, []);

  const sendBargeIn = useCallback(() => {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify({ type: "barge_in" }));
    }
  }, []);

  const sendEnd = useCallback(() => {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify({ type: "end" }));
    }
  }, []);

  return {
    status,
    transcript,
    draft,
    uncertain,
    alerts,
    latencyMs,
    savedId,
    currentLang,
    speed,
    sendAudio,
    sendCommit,
    sendBargeIn,
    sendEnd,
  };
}
