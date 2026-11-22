// A scripted, fictional walkthrough for judges when voice credentials are unavailable.
export function createMockSocket() {
  let onmessage = null;
  let onopen = null;
  let onclose = null;
  let onerror = null;
  let closed = false;
  const timers = [];

  function emit(message) {
    if (!closed) onmessage?.({ data: JSON.stringify(message) });
  }

  function later(delay, action) {
    timers.push(setTimeout(() => {
      if (!closed) action();
    }, delay));
  }

  function runPreview() {
    emit({ type: "ready" });
    later(350, () => emit({
      type: "tts_start",
      sample_rate: 24000,
      text: "Preview mode is using fictional details. Speak a visit note and check the read-back before saving.",
    }));
    later(1800, () => emit({ type: "tts_end" }));
    later(2500, () => emit({
      type: "transcript",
      text: "Beneficiary 1001, weight 3.1 kilograms, the newborn feels hot to touch, next visit in seven days.",
    }));
    later(3200, () => emit({
      type: "card",
      draft: {
        beneficiary_id: "1001",
        visit_type: "NEWBORN",
        weight_kg: 3.1,
        vaccines_given_today: null,
        vaccines_due: null,
        next_visit_date: "2026-11-29",
      },
      uncertain: ["weight_kg"],
    }));
    later(4300, () => emit({
      type: "alert",
      signs: [{ id: "NB_FEVER_OR_COLD", label: "Feels hot or cold to touch" }],
    }));
    later(4700, () => emit({
      type: "tts_start",
      sample_rate: 24000,
      text: "A safety flag was recorded. Please review the visit details.",
    }));
    later(6000, () => emit({ type: "tts_end" }));
    later(6500, () => emit({
      type: "tts_start",
      sample_rate: 24000,
      text: "Beneficiary 1001. Weight 3.1 kilograms, please confirm. Vaccines given and due were not mentioned. Next visit November 29. Is this correct?",
    }));
    later(8500, () => emit({ type: "tts_end" }));
    later(9000, () => emit({ type: "transcript", text: "Yes, that is correct." }));
    later(9400, () => emit({
      type: "card",
      draft: {
        beneficiary_id: "1001",
        visit_type: "NEWBORN",
        weight_kg: 3.1,
        vaccines_given_today: null,
        vaccines_due: null,
        next_visit_date: "2026-11-29",
      },
      uncertain: [],
    }));
    later(10400, () => emit({ type: "saved", visit_id: "demo-visit-1001" }));
    later(10800, () => emit({
      type: "tts_start",
      sample_rate: 24000,
      text: "Preview visit saved.",
    }));
    later(12200, () => emit({ type: "tts_end" }));
  }

  const socket = {
    set onmessage(handler) { onmessage = handler; },
    get onmessage() { return onmessage; },
    set onopen(handler) { onopen = handler; },
    get onopen() { return onopen; },
    set onclose(handler) { onclose = handler; },
    get onclose() { return onclose; },
    set onerror(handler) { onerror = handler; },
    get onerror() { return onerror; },
    readyState: 1,
    send(data) {
      if (closed || typeof data !== "string") return;
      let message;
      try {
        message = JSON.parse(data);
      } catch {
        return;
      }
      if (message.type === "start") runPreview();
    },
    close() {
      if (closed) return;
      closed = true;
      socket.readyState = 3;
      timers.forEach(clearTimeout);
      onclose?.({ code: 1000, reason: "preview closed" });
    },
  };

  setTimeout(() => {
    if (!closed) onopen?.({});
  }, 40);
  return socket;
}
