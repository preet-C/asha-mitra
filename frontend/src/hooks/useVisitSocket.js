import { useCallback, useEffect, useRef, useState } from "react";
import { createMockSocket } from "../mock/mockSocket";

const MAX_RETRIES = 3;
const MAX_QUEUED_AUDIO_BYTES = 512 * 1024;

function wsUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}${path}`;
}

export function useVisitSocket({
  lang,
  mock,
  enabled = true,
  onTtsStart,
  onTtsChunk,
  onTtsEnd,
}) {
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState("");
  const [agentText, setAgentText] = useState("");
  const [draft, setDraft] = useState({});
  const [uncertain, setUncertain] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [latencyMs, setLatencyMs] = useState(null);
  const [savedId, setSavedId] = useState(null);
  const [currentLang, setCurrentLang] = useState(lang);
  const [speed, setSpeed] = useState(1);

  const wsRef = useRef(null);
  const connectRef = useRef(null);
  const retryTimerRef = useRef(null);
  const retriesRef = useRef(0);
  const startRateRef = useRef(null);
  const sessionReadyRef = useRef(false);
  const serverErrorRef = useRef(false);
  const queuedAudioRef = useRef([]);
  const queuedAudioBytesRef = useRef(0);
  const queuedCommitRef = useRef(false);
  const ttsActiveRef = useRef(false);

  const clearSession = useCallback(() => {
    setError("");
    setTranscript("");
    setAgentText("");
    setDraft({});
    setUncertain([]);
    setAlerts([]);
    setLatencyMs(null);
    setSavedId(null);
    retriesRef.current = 0;
    startRateRef.current = null;
    sessionReadyRef.current = false;
    serverErrorRef.current = false;
    queuedAudioRef.current = [];
    queuedAudioBytesRef.current = 0;
    queuedCommitRef.current = false;
    ttsActiveRef.current = false;
  }, []);

  const sendStartFrame = useCallback((ws) => {
    if (ws?.readyState !== WebSocket.OPEN || startRateRef.current == null) return;
    sessionReadyRef.current = false;
    serverErrorRef.current = false;
    setError("");
    setStatus("starting");
    ws.send(JSON.stringify({
      type: "start",
      lang,
      sample_rate: startRateRef.current,
    }));
  }, [lang]);

  const connect = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }

    const oldSocket = wsRef.current;
    if (oldSocket) {
      oldSocket.onopen = null;
      oldSocket.onmessage = null;
      oldSocket.onerror = null;
      oldSocket.onclose = null;
      try {
        oldSocket.close(1000);
      } catch {
        // The previous socket may already be closed.
      }
    }

    setStatus("connecting");
    const ws = mock ? createMockSocket() : new WebSocket(wsUrl("/ws/session"));
    wsRef.current = ws;
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      if (mock) {
        startRateRef.current = 16000;
        sendStartFrame(ws);
      } else if (startRateRef.current != null) {
        sendStartFrame(ws);
      } else {
        setStatus("connected");
      }
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        if (ttsActiveRef.current && onTtsChunk) onTtsChunk(event.data);
        return;
      }

      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }

      switch (message.type) {
        case "ready": {
          sessionReadyRef.current = true;
          serverErrorRef.current = false;
          retriesRef.current = 0;
          setError("");
          setStatus("ready");
          for (const chunk of queuedAudioRef.current) ws.send(chunk);
          queuedAudioRef.current = [];
          queuedAudioBytesRef.current = 0;
          if (queuedCommitRef.current) {
            ws.send(JSON.stringify({ type: "commit" }));
            queuedCommitRef.current = false;
          }
          break;
        }
        case "transcript":
          setTranscript(message.text || "");
          break;
        case "card":
          setDraft(message.draft || {});
          setUncertain(message.uncertain || []);
          break;
        case "alert":
          setAlerts((current) => {
            const known = new Set(current.map((item) => item.id));
            return [...current, ...(message.signs || []).filter((item) => !known.has(item.id))];
          });
          break;
        case "tts_start":
          ttsActiveRef.current = true;
          setAgentText(message.text || "");
          onTtsStart?.({ sampleRate: message.sample_rate, text: message.text || "" });
          break;
        case "tts_end":
          ttsActiveRef.current = false;
          onTtsEnd?.();
          break;
        case "latency":
          if (message.what === "first_audio") setLatencyMs(message.ms);
          break;
        case "saved":
          setSavedId(message.visit_id || "saved");
          break;
        case "setting":
          if (message.lang) setCurrentLang(message.lang);
          if (message.speed != null) setSpeed(message.speed);
          break;
        case "error":
          serverErrorRef.current = true;
          sessionReadyRef.current = false;
          queuedAudioRef.current = [];
          queuedAudioBytesRef.current = 0;
          setError(message.message || "The voice session could not start.");
          setStatus("error");
          break;
        default:
          break;
      }
    };

    ws.onerror = () => {
      setError("The connection was interrupted. Check that both servers are running.");
    };

    ws.onclose = (event) => {
      if (wsRef.current !== ws) return;
      sessionReadyRef.current = false;
      ttsActiveRef.current = false;
      if (event.code === 1000 || event.code === 1001) {
        setStatus("closed");
        return;
      }
      if (serverErrorRef.current) return;

      if (retriesRef.current < MAX_RETRIES) {
        const delay = 750 * (2 ** retriesRef.current);
        retriesRef.current += 1;
        setError("The connection dropped. Trying to reconnect…");
        setStatus("connecting");
        retryTimerRef.current = setTimeout(() => connectRef.current?.(), delay);
      } else {
        setError("Could not reconnect. Check the backend and try again.");
        setStatus("error");
      }
    };
  }, [mock, onTtsChunk, onTtsEnd, onTtsStart, sendStartFrame]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    // Start the socket after React finishes this effect's synchronous pass.
    let active = true;
    Promise.resolve().then(() => {
      if (active) connectRef.current?.();
    });
    return () => {
      active = false;
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        try {
          ws.close(1000);
        } catch {
          // The socket is already closed.
        }
      }
    };
  }, [connect, enabled]);

  const sendStart = useCallback((sampleRate) => {
    startRateRef.current = sampleRate;
    if (wsRef.current?.readyState === WebSocket.OPEN) sendStartFrame(wsRef.current);
  }, [sendStartFrame]);

  const sendAudio = useCallback((chunk) => {
    const ws = wsRef.current;
    if (ws?.readyState !== WebSocket.OPEN || !startRateRef.current) return;
    if (sessionReadyRef.current) {
      ws.send(chunk);
      return;
    }
    if (queuedAudioBytesRef.current + chunk.byteLength <= MAX_QUEUED_AUDIO_BYTES) {
      queuedAudioRef.current.push(chunk);
      queuedAudioBytesRef.current += chunk.byteLength;
    }
  }, []);

  const sendCommit = useCallback(() => {
    const ws = wsRef.current;
    if (ws?.readyState !== WebSocket.OPEN || !startRateRef.current) return;
    if (sessionReadyRef.current) {
      ws.send(JSON.stringify({ type: "commit" }));
    } else {
      queuedCommitRef.current = true;
    }
  }, []);

  const sendBargeIn = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "barge_in" }));
    }
  }, []);

  const reconnect = useCallback(() => {
    clearSession();
    connect();
  }, [clearSession, connect]);

  return {
    status: enabled ? status : "idle",
    error,
    transcript,
    agentText,
    draft,
    uncertain,
    alerts,
    latencyMs,
    savedId,
    currentLang,
    speed,
    sendAudio,
    sendStart,
    sendCommit,
    sendBargeIn,
    reconnect,
  };
}
