import { useCallback, useEffect, useRef, useState } from "react";
import { AudioRecorder } from "./audio/recorder";
import { AudioPlayer } from "./audio/player";
import { useVisitSocket } from "./hooks/useVisitSocket";
import { apiUrl } from "./lib/backendUrl";
import "./App.css";

const LANGUAGES = [
  { code: "hi-IN", label: "हिन्दी", english: "Hindi" },
  { code: "kn-IN", label: "ಕನ್ನಡ", english: "Kannada" },
  { code: "en-IN", label: "English", english: "English" },
];

const MOCK_FOLLOWUPS = [
  {
    visit_id: "demo-visit-1",
    beneficiary_id: "1001",
    name: "Demo beneficiary",
    village: "Sample village",
    kind: "child",
    next_visit_date: "2026-11-29",
    flagged: true,
    danger_flags: ["preview"],
  },
];

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path d="M7 21c0-8 6-14 18-15-1 12-7 18-15 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
        <path d="M8 25c3-6 7-10 13-14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      </svg>
    </span>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-4 0h8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function LanguagePicker({ lang, onLanguageChange, onLiveStart, onDemoStart }) {
  return (
    <main className="welcome-page">
      <div className="welcome-layout">
        <section className="welcome-copy">
          <div className="brand-lockup">
            <BrandMark />
            <div>
              <div className="brand-name">ASHA Mitra</div>
              <div className="brand-subtitle">A voice companion for home visits</div>
            </div>
          </div>

          <p className="eyebrow">FIELD NOTES, MADE EASIER</p>
          <h1>Speak naturally.<br /><span>Keep a clear record.</span></h1>
          <p className="welcome-description">
            Capture a visit in the worker’s own words, review the details together, and save only after confirmation.
          </p>

          <div className="process-list" aria-label="Visit steps">
            <div className="process-step"><span>01</span><div><strong>Speak</strong><small>Share the home-visit note</small></div></div>
            <div className="process-step"><span>02</span><div><strong>Review</strong><small>Check the record and flags</small></div></div>
            <div className="process-step"><span>03</span><div><strong>Confirm</strong><small>Save after the read-back</small></div></div>
          </div>
        </section>

        <section className="start-card" aria-labelledby="start-title">
          <div className="start-card__topline">GET STARTED</div>
          <h2 id="start-title">Choose a language</h2>
          <p className="muted-copy">You can speak in Hindi, Kannada, English, or mix them naturally.</p>

          <div className="language-options" role="group" aria-label="Choose language">
            {LANGUAGES.map((item) => (
              <button
                type="button"
                key={item.code}
                className={`language-option ${lang === item.code ? "language-option--selected" : ""}`}
                aria-pressed={lang === item.code}
                onClick={() => onLanguageChange(item.code)}
              >
                <span className="language-option__native">{item.label}</span>
                <span className="language-option__english">{item.english}</span>
                <span className="language-option__check" aria-hidden="true">{lang === item.code ? "✓" : ""}</span>
              </button>
            ))}
          </div>

          <button type="button" className="button button--primary button--wide" onClick={onLiveStart}>
            Start a live visit <span aria-hidden="true">→</span>
          </button>
          <button type="button" className="button button--secondary button--wide" onClick={onDemoStart}>
            Preview the demo
          </button>
          <p className="demo-note">The preview uses fictional data and does not access your microphone or voice services.</p>
        </section>
      </div>
      <div className="welcome-footer">ASHA Mitra <span>•</span> Visit notes stay in your configured local or database store</div>
    </main>
  );
}

function StatusPill({ status, mock }) {
  const labels = {
    idle: "Not connected",
    connecting: "Connecting",
    connected: "Connected · ready to begin",
    starting: "Starting voice session",
    ready: "Voice session ready",
    closed: "Session ended",
    error: "Needs attention",
  };
  return (
    <span className={`status-pill status-pill--${status}`}>
      <span className="status-pill__dot" />
      {mock ? "Demo preview" : (labels[status] || "Connecting")}
    </span>
  );
}

function DangerBanner({ signs }) {
  if (!signs.length) return null;
  const namedSigns = signs.map((sign) => sign.label).filter(Boolean);
  return (
    <section className="safety-banner" role="alert">
      <span className="safety-banner__symbol" aria-hidden="true">!</span>
      <div>
        <strong>Safety flag recorded</strong>
        <p>{namedSigns.length ? namedSigns.join(" · ") : `${signs.length} sign${signs.length === 1 ? "" : "s"} marked for review`}</p>
      </div>
    </section>
  );
}

function FieldRow({ label, value, uncertain, className = "" }) {
  const empty = value == null || value === "";
  return (
    <div className={`field-row ${uncertain ? "field-row--uncertain" : ""} ${className}`}>
      <dt>{label}</dt>
      <dd>
        <span className={empty ? "field-row__empty" : ""}>{empty ? "Not mentioned" : value}</span>
        {uncertain && <span className="review-tag">Please confirm</span>}
      </dd>
    </div>
  );
}

function displayArray(value, emptyText = "Not mentioned") {
  if (!Array.isArray(value) || value.length === 0) return emptyText;
  return value.join(", ");
}

function VisitRecord({ draft, uncertain, savedId }) {
  const needsReview = new Set(uncertain || []);
  const weight = draft.weight_kg == null ? null : `${draft.weight_kg} kg`;
  const nextVisit = formatDate(draft.next_visit_date) || null;
  const vaccineDue = draft.vaccines_due == null
    ? null
    : displayArray(draft.vaccines_due, "None due");

  return (
    <section className="surface record-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">STRUCTURED NOTE</p>
          <h2>Visit record</h2>
        </div>
        <span className={`record-state ${savedId ? "record-state--saved" : ""}`}>
          <span className="record-state__dot" />{savedId ? "Saved" : "In progress"}
        </span>
      </div>

      <dl className="record-fields">
        <FieldRow label="Beneficiary ID" value={draft.beneficiary_id} uncertain={needsReview.has("beneficiary_id")} />
        <FieldRow label="Visit type" value={draft.visit_type} uncertain={needsReview.has("visit_type")} />
        <FieldRow label="Weight" value={weight} uncertain={needsReview.has("weight_kg")} />
        <FieldRow label="Vaccines given" value={displayArray(draft.vaccines_given_today)} uncertain={needsReview.has("vaccines_given_today")} />
        <FieldRow label="Vaccines due" value={vaccineDue} uncertain={needsReview.has("vaccines_due")} />
        <FieldRow label="Next visit" value={nextVisit} uncertain={needsReview.has("next_visit_date")} />
      </dl>

      <div className="record-footnote">
        <span aria-hidden="true">i</span>
        Not-mentioned details stay blank. Check uncertain values before confirming by voice.
      </div>
      {savedId && <div className="saved-confirmation" role="status">Visit saved <span>·</span> {savedId}</div>}
    </section>
  );
}

function ConversationPanel({ transcript, agentText, status, mock, latencyMs, savedId, btnState, onToggle, disabled }) {
  const buttonLabel = btnState === "recording"
    ? "Tap to stop listening"
    : btnState === "starting"
      ? "Tap to cancel microphone start"
      : btnState === "speaking"
        ? "Tap to interrupt and speak"
        : "Tap to start listening";
  const buttonHint = btnState === "recording"
    ? "Listening now. Tap again to finish and send."
    : btnState === "starting"
      ? "Starting the microphone. Tap again to cancel."
      : btnState === "speaking"
        ? "Tap once to stop playback and start speaking."
        : "Tap once to listen, then tap again to send your note.";

  return (
    <section className="surface conversation-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">VOICE SESSION</p>
          <h2>Conversation</h2>
        </div>
        {latencyMs != null && <span className="latency-tag">First audio {(latencyMs / 1000).toFixed(1)}s</span>}
      </div>

      <div className="conversation-turn">
        <span className="turn-label">LAST HEARD</span>
        <p>{transcript || <span className="conversation-placeholder">Your words will appear here after you speak.</span>}</p>
      </div>
      <div className="conversation-turn conversation-turn--agent">
        <span className="turn-label">ASHA MITRA</span>
        <p>{agentText || <span className="conversation-placeholder">The read-back and next question will appear here.</span>}</p>
      </div>

      {mock ? (
        <div className="preview-running" role="status">
          <span className="preview-running__dot" />
          Scripted preview is running with fictional visit details.
        </div>
      ) : (
        <div className="voice-control">
          <button
            type="button"
            className={`mic-button mic-button--${btnState}`}
            disabled={disabled || (status !== "connected" && status !== "ready")}
            aria-label={buttonLabel}
            aria-pressed={btnState === "recording"}
            onClick={onToggle}
          >
            <MicIcon />
          </button>
          <strong>{buttonLabel}</strong>
          <span>{buttonHint}</span>
        </div>
      )}

      {savedId && <div className="next-visit-prompt">This visit is complete. Start another when you’re ready.</div>}
    </section>
  );
}

function FollowUpList({ mock }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  const fetchFollowups = useCallback(async (signal) => {
    if (mock) return MOCK_FOLLOWUPS;
    const response = await fetch(apiUrl("/api/followups"), { signal });
    if (!response.ok) throw new Error("Follow-up request failed");
    return response.json();
  }, [mock]);

  const loadFollowups = useCallback(() => {
    setItems(null);
    setError("");
    fetchFollowups()
      .then(setItems)
      .catch(() => setError("Follow-ups could not be loaded. Check the backend connection and try again."));
  }, [fetchFollowups]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.resolve()
      .then(() => fetchFollowups(controller.signal))
      .then((result) => {
        if (!controller.signal.aborted) setItems(result);
      })
      .catch((requestError) => {
        if (!controller.signal.aborted && requestError.name !== "AbortError") {
          setError("Follow-ups could not be loaded. Check the backend connection and try again.");
        }
      });
    return () => controller.abort();
  }, [fetchFollowups]);

  if (error) {
    return <div className="empty-state empty-state--error"><p>{error}</p><button className="button button--secondary" onClick={() => loadFollowups()}>Try again</button></div>;
  }
  if (items === null) return <div className="empty-state">Loading follow-ups…</div>;
  if (items.length === 0) {
    return <div className="empty-state"><span className="empty-state__icon">✓</span><strong>No follow-ups yet</strong><p>Upcoming and flagged visits will appear here.</p></div>;
  }

  return (
    <div className="followup-list">
      {items.map((item) => {
        const flagged = Boolean(item.flagged || item.danger_flags?.length);
        return (
          <article className={`followup-card ${flagged ? "followup-card--flagged" : ""}`} key={item.visit_id || item.beneficiary_id}>
            <span className={`followup-card__marker ${flagged ? "followup-card__marker--flagged" : ""}`} aria-hidden="true" />
            <div className="followup-card__body">
              <div className="followup-card__title-row">
                <h3>{item.name || "Synthetic beneficiary"}</h3>
                <span className="followup-card__id">#{item.beneficiary_id}</span>
              </div>
              <p>{item.village || "Village not listed"} <span>·</span> {item.kind || "Visit"}</p>
              {flagged && <span className="followup-flag">Flagged visit · review record</span>}
            </div>
            <div className="followup-card__date">
              <span>NEXT VISIT</span>
              <strong>{formatDate(item.next_visit_date) || "Not set"}</strong>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function statusHint(status) {
  if (status === "connecting") return "Connecting to the backend…";
  if (status === "starting") return "Opening the voice session…";
  if (status === "connected") return "Connected. Press the microphone to begin.";
  if (status === "ready") return "Voice session ready.";
  if (status === "error") return "The session needs attention.";
  return "Choose a language to begin.";
}

function microphoneErrorMessage(error) {
  if (error.name === "MicrophoneUnavailableError" || error.name === "AudioCaptureUnavailableError") {
    return error.message;
  }
  if (error.name === "NotAllowedError" || error.name === "SecurityError") {
    return "Microphone access is blocked. Allow it for this site in Chrome or Edge settings, then reload the page.";
  }
  if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
    return "No microphone was found. Connect or enable a microphone, then try again.";
  }
  if (error.name === "NotReadableError" || error.name === "TrackStartError") {
    return "The microphone is busy or unavailable to the browser. Close other apps using it and try again.";
  }
  if (error.name === "OverconstrainedError") {
    return "The selected microphone does not support the requested audio settings. Try another input device.";
  }
  return `Microphone setup failed (${error.name || "unknown error"}). Check the browser permission and selected input device.`;
}

export default function App() {
  const [screen, setScreen] = useState("welcome");
  const [lang, setLang] = useState("en-IN");
  const [demoMode, setDemoMode] = useState(false);
  const [tab, setTab] = useState("visit");
  const [btnState, setBtnState] = useState("idle");
  const [micError, setMicError] = useState("");
  const recorderRef = useRef(null);
  const playerRef = useRef(null);

  const handleTtsStart = useCallback(({ sampleRate }) => {
    playerRef.current?.close();
    playerRef.current = new AudioPlayer();
    playerRef.current._rate = sampleRate || 24000;
    setBtnState("speaking");
  }, []);
  const handleTtsChunk = useCallback((chunk) => {
    playerRef.current?.enqueue(chunk, playerRef.current._rate || 24000);
  }, []);
  const handleTtsEnd = useCallback(() => setBtnState("idle"), []);

  const sessionActive = screen === "session";
  const socket = useVisitSocket({
    lang,
    mock: demoMode,
    enabled: sessionActive,
    onTtsStart: demoMode ? null : handleTtsStart,
    onTtsChunk: demoMode ? null : handleTtsChunk,
    onTtsEnd: demoMode ? null : handleTtsEnd,
  });

  function startSession(useDemo) {
    setDemoMode(useDemo);
    setMicError("");
    setBtnState("idle");
    setTab("visit");
    setScreen("session");
  }

  async function handleMicrophoneToggle() {
    if (demoMode) return;

    // The same tap button starts and ends a recording. A pending start can be cancelled too.
    const activeRecorder = recorderRef.current;
    if (activeRecorder) {
      const wasReady = activeRecorder.isReady;
      activeRecorder.stop();
      recorderRef.current = null;
      setBtnState("idle");
      if (wasReady) socket.sendCommit();
      return;
    }

    setMicError("");
    if (btnState === "speaking") {
      playerRef.current?.stop();
      socket.sendBargeIn();
    }

    const recorder = new AudioRecorder();
    recorderRef.current = recorder;
    setBtnState("starting");
    try {
      await recorder.start(
        (chunk) => socket.sendAudio(chunk),
        (sampleRate) => socket.sendStart(sampleRate),
      );
      if (recorderRef.current !== recorder) return;
      setBtnState("recording");
    } catch (error) {
      if (recorderRef.current !== recorder) {
        recorder.stop();
        return;
      }
      recorder.stop();
      recorderRef.current = null;
      setBtnState("idle");
      setMicError(microphoneErrorMessage(error));
    }
  }

  function startNewVisit() {
    recorderRef.current?.stop();
    playerRef.current?.close();
    setMicError("");
    setBtnState("idle");
    socket.reconnect();
  }

  if (!sessionActive) {
    return (
      <LanguagePicker
        lang={lang}
        onLanguageChange={setLang}
        onLiveStart={() => startSession(false)}
        onDemoStart={() => startSession(true)}
      />
    );
  }

  const activeLanguage = LANGUAGES.find((item) => item.code === socket.currentLang) || LANGUAGES[2];
  const canRecord = !demoMode && !micError && !socket.error;

  return (
    <div className="app-page">
      <header className="app-header">
        <div className="brand-lockup brand-lockup--compact">
          <BrandMark />
          <div><div className="brand-name">ASHA Mitra</div><div className="brand-subtitle">Home-visit voice notes</div></div>
        </div>
        <div className="app-header__actions">
          <StatusPill status={socket.status} mock={demoMode} />
          <button className="text-button" type="button" onClick={() => setScreen("welcome")}>Change language</button>
        </div>
      </header>

      <main className="workspace">
        {demoMode && <div className="demo-banner"><span>DEMO PREVIEW</span> Fictional data only · no microphone or provider calls</div>}
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">{tab === "visit" ? "HOME VISIT" : "FIELDWORK OVERVIEW"}</p>
            <h1>{tab === "visit" ? "Visit workspace" : "Follow-up list"}</h1>
            <p className="workspace-heading__description">{tab === "visit" ? statusHint(socket.status) : "Upcoming visits and records marked for review."}</p>
          </div>
          <div className="language-chip"><span className="language-chip__dot" />{activeLanguage.english}</div>
        </div>

        {socket.error && (
          <section className="connection-alert" role="alert">
            <div className="connection-alert__icon">!</div>
            <div className="connection-alert__body"><strong>Voice session unavailable</strong><p>{socket.error}</p></div>
            <button type="button" className="button button--secondary" onClick={socket.reconnect}>Retry connection</button>
          </section>
        )}
        {micError && (
          <section className="connection-alert connection-alert--mic" role="alert">
            <div className="connection-alert__icon">!</div>
            <div className="connection-alert__body"><strong>Microphone unavailable</strong><p>{micError}</p></div>
            <button type="button" className="button button--secondary" onClick={() => setMicError("")}>Dismiss</button>
          </section>
        )}

        <DangerBanner signs={socket.alerts} />

        {tab === "visit" ? (
          <div className="workspace-grid">
            <VisitRecord draft={socket.draft} uncertain={socket.uncertain} savedId={socket.savedId} />
            <ConversationPanel
              transcript={socket.transcript}
              agentText={socket.agentText}
              status={socket.status}
              mock={demoMode}
              latencyMs={socket.latencyMs}
              savedId={socket.savedId}
              btnState={btnState}
              onToggle={handleMicrophoneToggle}
              disabled={!canRecord}
            />
          </div>
        ) : <FollowUpList mock={demoMode} />}

        {socket.savedId && <button type="button" className="button button--primary new-visit-button" onClick={startNewVisit}>Start another visit <span aria-hidden="true">→</span></button>}
      </main>

      <nav className="bottom-nav" aria-label="Main navigation">
        <button type="button" className={tab === "visit" ? "bottom-nav__item bottom-nav__item--active" : "bottom-nav__item"} aria-current={tab === "visit" ? "page" : undefined} onClick={() => setTab("visit")}>
          <span aria-hidden="true">01</span>Visit
        </button>
        <button type="button" className={tab === "followups" ? "bottom-nav__item bottom-nav__item--active" : "bottom-nav__item"} aria-current={tab === "followups" ? "page" : undefined} onClick={() => setTab("followups")}>
          <span aria-hidden="true">02</span>Follow-ups
        </button>
      </nav>
    </div>
  );
}
