// frontend/src/App.jsx
// WHY: Root component. State machine: pick_language → session.
// ?mock=1 in URL → uses fake WebSocket (no backend needed for UI demo).

import { useCallback, useEffect, useRef, useState } from "react";
import { AudioRecorder } from "./audio/recorder";
import { AudioPlayer }   from "./audio/player";
import { useVisitSocket } from "./hooks/useVisitSocket";
import "./App.css";

const params     = new URLSearchParams(window.location.search);
const IS_MOCK    = params.get("mock") === "1";

// Language display labels
const LANG_LABEL = { "hi-IN": "हिन्दी", "kn-IN": "ಕನ್ನಡ", "en-IN": "EN" };
const LANG_FLAG  = { "hi-IN": "🇮🇳",    "kn-IN": "🇮🇳",    "en-IN": "🌐" };

// ── Language picker screen ──────────────────────────────────────
function LanguagePicker({ onSelect }) {
  return (
    <div className="lang-picker">
      <div className="lang-picker__title">ASHA Mitra</div>
      <div className="lang-picker__sub">आशा मित्र · ಆಶಾ ಮಿತ್ರ</div>
      <div className="lang-picker__sub" style={{ fontSize: 14, marginBottom: 8 }}>
        Select your language to begin
      </div>
      {[
        ["hi-IN", "हिन्दी",  "🇮🇳"],
        ["kn-IN", "ಕನ್ನಡ",  "🇮🇳"],
        ["en-IN", "English", "🌐"],
      ].map(([code, label, flag]) => (
        <button key={code} className="lang-btn" onClick={() => onSelect(code)}>
          <span className="lang-btn__flag">{flag}</span>
          {label}
        </button>
      ))}
    </div>
  );
}

// ── Danger banner ───────────────────────────────────────────────
function DangerBanner({ signs }) {
  if (!signs.length) return null;
  return (
    <div className="danger-banner">
      <div className="danger-banner__title">⚠ Refer to PHC now</div>
      {signs.map((s) => (
        <div key={s.id} className="danger-banner__sign">• {s.label}</div>
      ))}
    </div>
  );
}

// ── Record card ─────────────────────────────────────────────────
function RecordCard({ draft, uncertain }) {
  const unc = new Set(uncertain || []);

  function row(label, field, display) {
    const val     = draft[field];
    const hasVal  = val != null && val !== "" && (!Array.isArray(val) || val.length > 0);
    const isUnc   = unc.has(field);
    const cls     = hasVal ? (isUnc ? "record-card__row--uncertain" : "record-card__row--ok") : "";
    return (
      <div key={field} className={`record-card__row ${cls}`}>
        <span className="record-card__label">{label}</span>
        {hasVal ? (
          <>
            <span className="record-card__value">{display(val)}</span>
            {isUnc
              ? <span className="record-card__badge record-card__badge--warn">check</span>
              : <span className="record-card__badge record-card__badge--ok">✓</span>
            }
          </>
        ) : (
          <span className="record-card__value record-card__value--empty">—</span>
        )}
      </div>
    );
  }

  return (
    <div className="record-card">
      <div className="record-card__header">Visit Record</div>
      {row("ID",           "beneficiary_id",      (v) => v)}
      {row("Weight",       "weight_kg",            (v) => `${v} kg`)}
      {row("Vaccines given","vaccines_given_today", (v) => Array.isArray(v) ? v.join(", ") : v)}
      {row("Vaccines due", "vaccines_due",          (v) => Array.isArray(v) && v.length ? v.join(", ") : "none")}
      {row("Next visit",   "next_visit_date",       (v) => v)}
    </div>
  );
}

// ── Latency badge ───────────────────────────────────────────────
function LatencyBadge({ ms }) {
  if (ms == null) return null;
  return <span className="latency-badge">⚡ {(ms / 1000).toFixed(1)}s</span>;
}

// ── Follow-up list ──────────────────────────────────────────────
function FollowUpList() {
  const [items, setItems] = useState(null);
  const [err,   setErr]   = useState(false);

  // WHY useEffect: fetch once when this component mounts (tab is opened)
  useEffect(() => {
    fetch("/api/followups")
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(setItems)
      .catch(() => setErr(true));
  }, []);

  if (err)            return <div className="followup-loading">Could not load follow-ups.</div>;
  if (items === null) return <div className="followup-loading">Loading...</div>;
  if (!items.length)  return <div className="followup-loading">No upcoming visits.</div>;

  return (
    <div className="followup-list">
      {items.map((b) => {
        const flagged = b.last_flags && b.last_flags.length > 0;
        return (
          <div key={b.id} className={`followup-card ${flagged ? "followup-card--flagged" : ""}`}>
            <div className="followup-card__icon">{flagged ? "⚠️" : "👶"}</div>
            <div className="followup-card__info">
              <div className="followup-card__name">{b.name} <span style={{ fontWeight: 400, fontSize: 13, color: "#888" }}>#{b.id}</span></div>
              <div className="followup-card__meta">{b.village} · {b.kind}</div>
              {flagged && <div className="followup-card__meta" style={{ color: "var(--danger)", fontWeight: 600 }}>Danger flag on record</div>}
              <div className="followup-card__date">📅 {b.next_visit_date || "Date not set"}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Hold button ─────────────────────────────────────────────────
function HoldButton({ onPress, onRelease, state }) {
  const icon  = state === "recording" ? "🎙" : state === "speaking" ? "🔊" : "🎙";
  const label = state === "recording" ? "Release to send"
              : state === "speaking"  ? "Tap to interrupt"
              : "Hold to speak";
  return (
    <div className="hold-btn-wrap">
      <button
        className={`hold-btn hold-btn--${state}`}
        onPointerDown={onPress}
        onPointerUp={onRelease}
        onPointerCancel={onRelease}
      >
        {icon}
      </button>
      <div className="hold-btn__label">{label}</div>
    </div>
  );
}

// ── Main App ────────────────────────────────────────────────────
export default function App() {
  const [screen,   setScreen]   = useState("pick_language");
  const [lang,     setLang]     = useState("en-IN");
  const [tab,      setTab]      = useState("visit");
  const [btnState, setBtnState] = useState("idle");

  const recorderRef = useRef(null);
  const playerRef   = useRef(null);

  // TTS callbacks — called by useVisitSocket when audio arrives
  const handleTtsStart = useCallback(({ sampleRate }) => {
    playerRef.current?.close?.();
    playerRef.current = new AudioPlayer();
    playerRef.current._rate = sampleRate;
    setBtnState("speaking");
  }, []);

  const handleTtsChunk = useCallback((buf) => {
    playerRef.current?.enqueue(buf, playerRef.current._rate || 24000);
  }, []);

  const handleTtsEnd = useCallback(() => {
    setBtnState("idle");
  }, []);

  const sessionActive = screen === "session";

  const {
    status, transcript, draft, uncertain,
    alerts, latencyMs, savedId, currentLang,
    sendAudio, sendCommit, sendBargeIn,
  } = useVisitSocket({
    lang,
    mock:     IS_MOCK,
    enabled:  sessionActive,
    onTtsStart: sessionActive ? handleTtsStart : null,
    onTtsChunk: sessionActive ? handleTtsChunk : null,
    onTtsEnd:   sessionActive ? handleTtsEnd   : null,
  });

  // Hold button: press = start recording, release = commit
  async function handlePress() {
    if (btnState === "speaking") {
      playerRef.current?.stop?.();
      sendBargeIn();
    }
    recorderRef.current?.stop?.();
    const rec = new AudioRecorder();
    recorderRef.current = rec;
    setBtnState("recording");
    try {
      await rec.start((chunk) => sendAudio(chunk));
    } catch (err) {
      console.error("[app] recorder:", err);
      setBtnState("idle");
    }
  }

  function handleRelease() {
    recorderRef.current?.stop?.();
    recorderRef.current = null;
    if (btnState === "recording") {
      setBtnState("idle");
      sendCommit();
    }
  }

  function handleLanguageSelect(selectedLang) {
    setLang(selectedLang);
    setScreen("session");
  }

  // Status text shown when no transcript yet
  function statusHint() {
    if (savedId)                 return "✅ Visit saved";
    if (status === "connecting") return "Connecting...";
    if (status === "error")      return "⚠ Connection error — refresh to retry";
    return "Tap and hold the button, then speak";
  }

  // ── Language picker screen
  if (screen === "pick_language") {
    return <LanguagePicker onSelect={handleLanguageSelect} />;
  }

  // ── Session screen
  return (
    <div className="app-outer">
      <div className="app-shell">

        {/* Top bar */}
        <div className="top-bar">
          <span className="top-bar__title">ASHA Mitra</span>
          <div className="top-bar__right">
            <LatencyBadge ms={latencyMs} />
            <span className="lang-chip">
              {LANG_FLAG[currentLang] || "🌐"} {LANG_LABEL[currentLang] || currentLang}
            </span>
          </div>
        </div>

        {/* Danger banner — sticky below top bar */}
        <DangerBanner signs={alerts} />

        {/* Scrollable content */}
        <div className="scroll-area">
          {tab === "visit" ? (
            <>
              {/* What the agent last heard */}
              <div className="transcript-box">
                <div className="transcript-box__label">Last heard</div>
                <div className="transcript-box__text">
                  {transcript
                    ? `"${transcript}"`
                    : <span className="transcript-box__hint">{statusHint()}</span>
                  }
                </div>
              </div>

              {/* Visit record card */}
              <RecordCard draft={draft} uncertain={uncertain} />

              {/* Saved confirmation */}
              {savedId && <div className="saved-badge">✅ Visit saved — ID {savedId}</div>}
            </>
          ) : (
            <FollowUpList />
          )}
        </div>

        {/* Mic button — fixed above tab bar */}
        {tab === "visit" && (
          <div className="btn-area">
            <HoldButton
              onPress={handlePress}
              onRelease={handleRelease}
              state={btnState}
            />
          </div>
        )}

        {/* Tab bar */}
        <div className="tab-bar">
          {[["visit", "🏠 Visit"], ["followups", "📋 Follow-ups"]].map(([id, label]) => (
            <button
              key={id}
              className={`tab-btn ${tab === id ? "tab-btn--active" : ""}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Dev hint */}
        {IS_MOCK && (
          <div style={{ position: "fixed", top: 60, right: 8, fontSize: 11, color: "rgba(255,255,255,0.6)", zIndex: 30, background: "var(--brand)", padding: "2px 8px", borderRadius: 8 }}>
            MOCK
          </div>
        )}

      </div>
    </div>
  );
}
