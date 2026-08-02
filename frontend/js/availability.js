import { ApiError, getHealth } from "./api.js";

const foregroundCheckIntervalMilliseconds = 2000;
const backgroundCheckIntervalMilliseconds = 15000;

let availabilityTimer = null;
let checkingAvailability = false;
let lastKnownAvailable = null;
let reloadingAfterRecovery = false;

function getConnectionElements() {
  const connection = document.querySelector(".connection");

  return {
    connection,
    title: connection?.querySelector("strong"),
    subtitle: connection?.querySelector(".connection-copy span"),
  };
}

function setConnectionStatus(state, titleText, subtitleText) {
  const { connection, title, subtitle } = getConnectionElements();

  if (!connection) {
    return;
  }

  const currentState = connection.dataset.connectionState;

  if (
    currentState === state &&
    title?.textContent === titleText &&
    subtitle?.textContent === subtitleText
  ) {
    return;
  }

  connection.dataset.connectionState = state;
  connection.classList.remove("connection--checking", "connection--unavailable");

  if (state === "checking") {
    connection.classList.add("connection--checking");
  }

  if (state === "unavailable") {
    connection.classList.add("connection--unavailable");
  }

  connection.title = subtitleText;

  if (title) {
    title.textContent = titleText;
  }

  if (subtitle) {
    subtitle.textContent = subtitleText;
  }
}

function clearAvailabilityTimer() {
  if (availabilityTimer === null) {
    return;
  }

  window.clearTimeout(availabilityTimer);
  availabilityTimer = null;
}

function getNextCheckDelay() {
  return document.hidden
    ? backgroundCheckIntervalMilliseconds
    : foregroundCheckIntervalMilliseconds;
}

function scheduleAvailabilityCheck() {
  clearAvailabilityTimer();

  if (reloadingAfterRecovery) {
    return;
  }

  availabilityTimer = window.setTimeout(function () {
    void runAvailabilityCheck({ reloadOnRecovery: true });
  }, getNextCheckDelay());
}

function getUnavailablePage() {
  return document.querySelector("[data-service-unavailable]");
}

function createUnavailablePage() {
  const page = document.createElement("main");

  page.className = "service-unavailable-page";
  page.dataset.serviceUnavailable = "";

  page.innerHTML = `
    <section class="service-unavailable-card" role="status" aria-live="polite">
      <p class="service-unavailable-message" data-unavailable-message>
        Service temporarily unavailable — retrying automatically…
      </p>
    </section>
  `;

  return page;
}

function setUnavailableMessage(message) {
  let page = getUnavailablePage();

  if (!page) {
    page = createUnavailablePage();
    document.querySelector(".app-shell")?.appendChild(page);
  }

  const messageElement = page.querySelector("[data-unavailable-message]");

  if (messageElement) {
    messageElement.textContent = message;
  }
}

function hideApplicationContent() {
  const applicationPage = document.querySelector("main.page");
  const navigation = document.querySelector("[data-primary-nav]");

  if (applicationPage) {
    applicationPage.hidden = true;
    applicationPage.setAttribute("aria-hidden", "true");
  }

  if (navigation) {
    navigation.hidden = true;
  }
}

function showApplicationContent() {
  const applicationPage = document.querySelector("main.page");
  const navigation = document.querySelector("[data-primary-nav]");

  if (applicationPage) {
    applicationPage.hidden = false;
    applicationPage.removeAttribute("aria-hidden");
  }

  if (navigation) {
    navigation.hidden = false;
  }

  getUnavailablePage()?.remove();
}

function extractHealthPayload(error) {
  if (!(error instanceof ApiError)) {
    return null;
  }

  const body = error.body;

  if (!body || typeof body !== "object" || body.drop_configured === undefined) {
    return null;
  }

  return body;
}

function getUnavailableMessage(error, health = null) {
  if (
    error instanceof ApiError &&
    ["network_error", "backend_unavailable"].includes(error.code)
  ) {
    return "Backend unreachable — retrying automatically…";
  }

  if (error instanceof ApiError && error.status === 404) {
    return "Backend health endpoint not found (HTTP 404).";
  }

  if (health?.drop_connected === false) {
    return "DROP service unavailable — reconnecting automatically…";
  }

  if (error instanceof ApiError && error.status === 503) {
    return "Live state is temporarily unavailable — retrying automatically…";
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Service temporarily unavailable — retrying automatically…";
}

function showDropUnavailable(health, message = null) {
  lastKnownAvailable = false;
  hideApplicationContent();
  setUnavailableMessage(message || getUnavailableMessage(null, health));

  const connectionState = (health?.connection_state || "unavailable").toLowerCase();
  setConnectionStatus("unavailable", "Backend connected", `DROP ${connectionState}`);
}

function showBackendUnavailable(message) {
  lastKnownAvailable = false;
  hideApplicationContent();
  setUnavailableMessage(message);
  setConnectionStatus("unavailable", "Backend unavailable", "Retrying automatically");
}

async function evaluateAvailability() {
  if (lastKnownAvailable == null) {
    setConnectionStatus("checking", "Checking backend", "Checking DROP status");
  }
  
  try {
    const health = await getHealth();

    if (health?.data_available !== true) {
      showDropUnavailable(health, getUnavailableMessage(null, health));
      return { available: false, recovered: false };
    }

    const recovered = lastKnownAvailable === false || getUnavailablePage() !== null;

    lastKnownAvailable = true;
    showApplicationContent();
    setConnectionStatus("available", "Backend connected", "DROP live");

    return { available: true, recovered };
  } catch (error) {
    const health = extractHealthPayload(error);
    const message = getUnavailableMessage(error, health);

    if (health) {
      showDropUnavailable(health, message);
      return { available: false, recovered: false };
    }

    showBackendUnavailable(message);
    return { available: false, recovered: false };
  }
}

async function runAvailabilityCheck({ reloadOnRecovery = false } = {}) {
  if (checkingAvailability) {
    return lastKnownAvailable === true;
  }

  checkingAvailability = true;
  clearAvailabilityTimer();

  try {
    const result = await evaluateAvailability();

    if (result.available && result.recovered && reloadOnRecovery) {
      reloadingAfterRecovery = true;
      window.location.reload();
    }

    return result.available;
  } finally {
    checkingAvailability = false;
    scheduleAvailabilityCheck();
  }
}

function checkImmediatelyWhenVisible() {
  if (document.hidden) {
    scheduleAvailabilityCheck();
    return;
  }

  void runAvailabilityCheck({ reloadOnRecovery: true });
}

document.addEventListener("visibilitychange", checkImmediatelyWhenVisible);
window.addEventListener("online", checkImmediatelyWhenVisible);

window.addEventListener("offline", function () {
  showBackendUnavailable("Browser offline — waiting for the network connection…");
  scheduleAvailabilityCheck();
});

window.addEventListener("beforeunload", clearAvailabilityTimer);

export async function ensureApplicationAvailable() {
  return runAvailabilityCheck({ reloadOnRecovery: false });
}

export function showStateUnavailableError(error) {
  showDropUnavailable(null, getUnavailableMessage(error));
  scheduleAvailabilityCheck();
}