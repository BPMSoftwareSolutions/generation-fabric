const playbackElement = document.getElementById("observability-playback-data");
const playbackData = playbackElement ? JSON.parse(playbackElement.textContent || "{}") : {};
const tracks = Array.isArray(playbackData.tracks) ? playbackData.tracks : [];
const timeline = [];
for (let trackIndex = 0; trackIndex < tracks.length; trackIndex += 1) {
  const track = tracks[trackIndex] || {};
  const steps = Array.isArray(track.steps) ? track.steps : [];
  for (let stepIndex = 0; stepIndex < steps.length; stepIndex += 1) {
    timeline.push({ trackIndex, stepIndex, track, step: steps[stepIndex] || {} });
  }
}

const state = {
  timelineIndex: 0,
  playing: false,
  speed: 1,
  timer: null,
};

const nodes = {
  executionList: document.getElementById("execution-list"),
  stepList: document.getElementById("step-list"),
  activeExecutionTitle: document.getElementById("active-execution-title"),
  activeExecutionMeta: document.getElementById("active-execution-meta"),
  activeStepType: document.getElementById("active-step-type"),
  activeStepLabel: document.getElementById("active-step-label"),
  activeStepSource: document.getElementById("active-step-source"),
  activeStepTarget: document.getElementById("active-step-target"),
  activeStepMessage: document.getElementById("active-step-message"),
  activeStepAnchor: document.getElementById("active-step-anchor"),
  activeStepDuration: document.getElementById("active-step-duration"),
  speedSelect: document.getElementById("playback-speed"),
  buttons: {
    previous: document.querySelector('[data-action="previous"]'),
    play: document.querySelector('[data-action="play"]'),
    pause: document.querySelector('[data-action="pause"]'),
    next: document.querySelector('[data-action="next"]'),
    reset: document.querySelector('[data-action="reset"]'),
  },
};

const executionButtonMap = new Map();
const stepButtonMap = new Map();

function stepId(entry) {
  return `${entry.track.execution_id}.${entry.step.step_index}`;
}

function trackLabel(track) {
  return track.title || track.execution_id || "Execution";
}

function stepClass(stepType) {
  const normalized = String(stepType || "idle").toLowerCase();
  if (normalized === "call") return "call-step";
  if (normalized === "data") return "data-step";
  if (normalized === "mutation") return "mutation-step";
  if (normalized === "branch") return "branch-step";
  if (normalized === "return") return "return-step";
  if (normalized === "error") return "error-step";
  return "idle-step";
}

function formatDuration(durationMs) {
  const value = Number(durationMs || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "—";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}s`;
  }
  return `${value}ms`;
}

function currentEntry() {
  if (!timeline.length) {
    return null;
  }
  const index = Math.max(0, Math.min(state.timelineIndex, timeline.length - 1));
  return timeline[index];
}

function firstTimelineIndexForTrack(trackIndex) {
  return timeline.findIndex((entry) => entry.trackIndex === trackIndex);
}

function setTimelineIndex(index) {
  if (!timeline.length) {
    return;
  }
  const clamped = Math.max(0, Math.min(index, timeline.length - 1));
  state.timelineIndex = clamped;
  renderState();
  if (state.playing) {
    scheduleNextStep();
  }
}

function pausePlayback() {
  state.playing = false;
  if (state.timer) {
    window.clearTimeout(state.timer);
    state.timer = null;
  }
  if (nodes.buttons.play) {
    nodes.buttons.play.disabled = false;
  }
}

function scheduleNextStep() {
  if (state.timer) {
    window.clearTimeout(state.timer);
    state.timer = null;
  }
  const entry = currentEntry();
  if (!entry) {
    pausePlayback();
    return;
  }
  const step = entry.step || {};
  const durationMs = Math.max(250, Math.round(Number(step.duration_ms || 0) / state.speed) || 600);
  state.timer = window.setTimeout(() => {
    const nextIndex = state.timelineIndex + 1;
    if (nextIndex >= timeline.length) {
      pausePlayback();
      return;
    }
    state.timelineIndex = nextIndex;
    renderState();
    if (state.playing) {
      scheduleNextStep();
    }
  }, durationMs);
}

function playPlayback() {
  if (!timeline.length) {
    return;
  }
  state.playing = true;
  if (nodes.buttons.play) {
    nodes.buttons.play.disabled = true;
  }
  scheduleNextStep();
}

function resetPlayback() {
  pausePlayback();
  state.timelineIndex = 0;
  renderState();
}

function nextStep() {
  if (!timeline.length) {
    return;
  }
  const nextIndex = Math.min(state.timelineIndex + 1, timeline.length - 1);
  setTimelineIndex(nextIndex);
}

function previousStep() {
  if (!timeline.length) {
    return;
  }
  const previousIndex = Math.max(state.timelineIndex - 1, 0);
  setTimelineIndex(previousIndex);
}

function setSpeed(multiplier) {
  const parsed = Number(multiplier);
  if (Number.isFinite(parsed) && parsed > 0) {
    state.speed = parsed;
    if (state.playing) {
      scheduleNextStep();
    }
  }
}

function clearActiveClasses() {
  for (const button of executionButtonMap.values()) {
    button.classList.remove("is-active");
  }
  for (const button of stepButtonMap.values()) {
    button.classList.remove("is-active");
  }
  document.querySelectorAll(".diagram-shell").forEach((element) => {
    element.classList.remove("is-active");
  });
}

function updateActivePanels(entry) {
  if (!entry) {
    if (nodes.activeExecutionTitle) {
      nodes.activeExecutionTitle.textContent = "No execution tracks available";
    }
    if (nodes.activeExecutionMeta) {
      nodes.activeExecutionMeta.textContent = "Generate an observation report to enable playback.";
    }
    return;
  }

  const track = entry.track || {};
  const step = entry.step || {};
  const trackSteps = Array.isArray(track.steps) ? track.steps : [];
  const stepNumber = entry.stepIndex + 1;

  if (nodes.activeExecutionTitle) {
    nodes.activeExecutionTitle.textContent = trackLabel(track);
  }
  if (nodes.activeExecutionMeta) {
    nodes.activeExecutionMeta.textContent = `${track.execution_id || "execution"} · diagram ${track.diagram_index || 0} · ${trackSteps.length} step(s)`;
  }
  if (nodes.activeStepType) {
    nodes.activeStepType.textContent = String(step.step_type || "idle");
  }
  if (nodes.activeStepLabel) {
    nodes.activeStepLabel.textContent = String(step.label || "—");
  }
  if (nodes.activeStepSource) {
    nodes.activeStepSource.textContent = String(step.source || "—");
  }
  if (nodes.activeStepTarget) {
    nodes.activeStepTarget.textContent = String(step.target || "—");
  }
  if (nodes.activeStepMessage) {
    nodes.activeStepMessage.textContent = String(step.message || "—");
  }
  if (nodes.activeStepAnchor) {
    nodes.activeStepAnchor.textContent = String(step.source_anchor || "—");
  }
  if (nodes.activeStepDuration) {
    nodes.activeStepDuration.textContent = formatDuration(step.duration_ms);
  }

  const executionButton = executionButtonMap.get(entry.trackIndex);
  if (executionButton) {
    executionButton.classList.add("is-active");
  }

  const stepButton = stepButtonMap.get(stepId(entry));
  if (stepButton) {
    stepButton.classList.add("is-active");
  }

  const diagramIndex = Number(track.diagram_index || 0);
  if (diagramIndex > 0) {
    const diagram = document.querySelector(`.diagram-shell[data-diagram-index="${diagramIndex}"]`);
    if (diagram) {
      diagram.classList.add("is-active");
    }
  }

  if (nodes.activeExecutionMeta) {
    nodes.activeExecutionMeta.dataset.activeStep = String(stepNumber);
  }
}

function renderExecutionList() {
  if (!nodes.executionList) {
    return;
  }

  nodes.executionList.innerHTML = "";
  executionButtonMap.clear();

  if (!tracks.length) {
    const empty = document.createElement("p");
    empty.className = "panel-summary";
    empty.textContent = "No execution tracks were extracted from the observation JSON.";
    nodes.executionList.appendChild(empty);
    return;
  }

  tracks.forEach((track, trackIndex) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "execution-track";
    button.dataset.trackIndex = String(trackIndex);

    const title = document.createElement("span");
    title.className = "execution-track__title";
    title.textContent = trackLabel(track);

    const meta = document.createElement("span");
    meta.className = "execution-track__meta";
    const steps = Array.isArray(track.steps) ? track.steps.length : 0;
    meta.textContent = `${track.execution_id || "execution"} · ${steps} step(s) · diagram ${track.diagram_index || 0}`;

    button.append(title, meta);
    button.addEventListener("click", () => {
      const firstIndex = firstTimelineIndexForTrack(trackIndex);
      if (firstIndex >= 0) {
        setTimelineIndex(firstIndex);
      }
    });

    executionButtonMap.set(trackIndex, button);
    nodes.executionList.appendChild(button);
  });
}

function renderStepList(trackIndex) {
  if (!nodes.stepList) {
    return;
  }

  nodes.stepList.innerHTML = "";
  stepButtonMap.clear();

  const track = tracks[trackIndex];
  if (!track || !Array.isArray(track.steps)) {
    const empty = document.createElement("li");
    empty.className = "panel-summary";
    empty.textContent = "Select an execution to inspect its steps.";
    nodes.stepList.appendChild(empty);
    return;
  }

  track.steps.forEach((step, stepIndex) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `step-card ${stepClass(step.step_type)}`;
    button.dataset.stepId = `${track.execution_id || "execution"}.${stepIndex + 1}`;

    const top = document.createElement("div");
    top.className = "step-card__top";

    const type = document.createElement("span");
    type.className = "step-card__type";
    type.textContent = `${step.step_type || "idle"} · #${stepIndex + 1}`;

    const route = document.createElement("span");
    route.className = "step-card__route";
    route.textContent = `${step.source || "—"} → ${step.target || "—"}`;

    top.append(type, route);

    const message = document.createElement("div");
    message.className = "step-card__message";
    const messageParts = [step.label || "", step.message || ""].filter(Boolean);
    message.textContent = messageParts.join(" · ");

    button.append(top, message);
    button.addEventListener("click", () => {
      const index = timeline.findIndex((entry) => entry.trackIndex === trackIndex && entry.stepIndex === stepIndex);
      if (index >= 0) {
        setTimelineIndex(index);
      }
    });

    stepButtonMap.set(`${track.execution_id || "execution"}.${stepIndex + 1}`, button);
    nodes.stepList.appendChild(button);
  });
}

function renderState() {
  clearActiveClasses();
  const entry = currentEntry();
  if (!entry) {
    updateActivePanels(null);
    return;
  }

  renderStepList(entry.trackIndex);
  updateActivePanels(entry);
}

async function renderMermaidDiagrams() {
  const mermaidBlocks = document.querySelectorAll(".mermaid");
  if (!mermaidBlocks.length) {
    return;
  }

  try {
    const module = await import("https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs");
    const mermaid = module.default || module;
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "default",
    });
    await mermaid.run({ querySelector: ".mermaid" });
  } catch (error) {
    console.warn("Mermaid rendering failed", error);
  }
}

function attachControls() {
  if (nodes.buttons.previous) {
    nodes.buttons.previous.addEventListener("click", () => previousStep());
  }
  if (nodes.buttons.play) {
    nodes.buttons.play.addEventListener("click", () => playPlayback());
  }
  if (nodes.buttons.pause) {
    nodes.buttons.pause.addEventListener("click", () => pausePlayback());
  }
  if (nodes.buttons.next) {
    nodes.buttons.next.addEventListener("click", () => nextStep());
  }
  if (nodes.buttons.reset) {
    nodes.buttons.reset.addEventListener("click", () => resetPlayback());
  }
  if (nodes.speedSelect) {
    nodes.speedSelect.addEventListener("change", () => setSpeed(nodes.speedSelect.value));
  }
}

async function bootstrapObservability() {
  renderExecutionList();
  renderState();
  attachControls();
  await renderMermaidDiagrams();
  renderState();
}

bootstrapObservability().catch((error) => {
  console.error("observability bootstrap failed", error);
});
