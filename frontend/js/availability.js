import { ApiError, getHealth } from "./api.js";

const foregroundCheckIntervalMilliseconds = 2000;
const backgroundCheckIntervalMilliseconds = 15000;

let availabilityTimer = null;
let checkingAvailability = false;
let lastKnownAvailable = null;
let reloadingAfterRecovery = false;

function formatTime() {
  return new Intl.DateTimeFormat(
    "en-GB",
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    },
  ).format(new Date());
}

function getConnectionElements() {
  const connection = document.querySelector(
    ".connection",
  );

  return {
    connection,
    title: connection?.querySelector(
      "strong",
    ),
    subtitle: connection?.querySelector(
      ".connection-copy span",
    ),
  };
}

function setConnectionStatus(
  state,
  titleText,
  subtitleText,
) {
  const {
    connection,
    title,
    subtitle,
  } = getConnectionElements();

  if (!connection) {
    return;
  }

  connection.classList.remove(
    "connection--checking",
    "connection--unavailable",
  );

  if (state === "checking") {
    connection.classList.add(
      "connection--checking",
    );
  }

  if (state === "unavailable") {
    connection.classList.add(
      "connection--unavailable",
    );
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

  window.clearTimeout(
    availabilityTimer,
  );

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

  availabilityTimer = window.setTimeout(
    function () {
      void runAvailabilityCheck({
        reloadOnRecovery: true,
      });
    },
    getNextCheckDelay(),
  );
}

function getUnavailablePage() {
  return document.querySelector(
    "[data-service-unavailable]",
  );
}

function createUnavailablePage() {
  const page = document.createElement(
    "main",
  );

  page.className =
    "service-unavailable-page";

  page.dataset.serviceUnavailable = "";

  page.innerHTML = `
    <section
      class="service-unavailable-card"
      role="status"
      aria-live="polite"
      aria-labelledby="service-unavailable-title"
    >
      <div
        class="service-unavailable-icon"
        aria-hidden="true"
      >
        <svg
          width="30"
          height="30"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M12 9v4"></path>
          <path d="M12 17h.01"></path>
          <path d="M10.3 3.6 2.5 17.1A2 2 0 0 0 4.2 20h15.6a2 2 0 0 0 1.7-2.9L13.7 3.6a2 2 0 0 0-3.4 0Z"></path>
        </svg>
      </div>

      <p class="service-unavailable-eyebrow">
        Market Control
      </p>

      <h1
        class="service-unavailable-title"
        id="service-unavailable-title"
        data-unavailable-title
      >
        DROP Service Unavailable
      </h1>

      <p
        class="service-unavailable-message"
        data-unavailable-message
      >
        DROP is not connected. State data is temporarily unavailable.
      </p>

      <p
        class="service-unavailable-description"
        data-unavailable-description
      >
        The backend service is running and attempting to reconnect.
      </p>

      <dl class="service-status-list">
        <div>
          <dt>Backend</dt>
          <dd data-unavailable-backend>Connected</dd>
        </div>
        <div>
          <dt>DROP</dt>
          <dd data-unavailable-drop>Reconnecting</dd>
        </div>
        <div>
          <dt>Session</dt>
          <dd data-unavailable-session>—</dd>
        </div>
      </dl>

      <div class="service-unavailable-actions">
        <button
          class="service-retry-button"
          type="button"
          data-service-retry
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 4v5h5"></path>
            <path d="M4 13a8.1 8.1 0 0 0 15.5 2M20 20v-5h-5"></path>
          </svg>
          <span data-service-retry-label>
            Retry connection
          </span>
        </button>
      </div>

      <p class="service-unavailable-footnote">
        Automatic status check every 2 seconds · Last checked
        <strong data-unavailable-checked>--:--:--</strong>
      </p>
    </section>
  `;

  const retryButton = page.querySelector(
    "[data-service-retry]",
  );

  retryButton?.addEventListener(
    "click",
    function () {
      void runAvailabilityCheck({
        reloadOnRecovery: true,
        manual: true,
      });
    },
  );

  return page;
}

function hideApplicationContent() {
  const applicationPage =
    document.querySelector(
      "main.page",
    );

  const navigation =
    document.querySelector(
      "[data-primary-nav]",
    );

  if (applicationPage) {
    applicationPage.hidden = true;
    applicationPage.setAttribute(
      "aria-hidden",
      "true",
    );
  }

  if (navigation) {
    navigation.hidden = true;
  }
}

function showApplicationContent() {
  const applicationPage =
    document.querySelector(
      "main.page",
    );

  const navigation =
    document.querySelector(
      "[data-primary-nav]",
    );

  if (applicationPage) {
    applicationPage.hidden = false;
    applicationPage.removeAttribute(
      "aria-hidden",
    );
  }

  if (navigation) {
    navigation.hidden = false;
  }

  getUnavailablePage()?.remove();
}

function normaliseConnectionState(value) {
  if (!value) {
    return "Unavailable";
  }

  return (
    value.charAt(0).toUpperCase() +
    value.slice(1)
  );
}

function updateUnavailablePage(options) {
  let page = getUnavailablePage();

  if (!page) {
    page = createUnavailablePage();

    const appShell = document.querySelector(
      ".app-shell",
    );

    appShell?.appendChild(page);
  }

  const title = page.querySelector(
    "[data-unavailable-title]",
  );

  const message = page.querySelector(
    "[data-unavailable-message]",
  );

  const description = page.querySelector(
    "[data-unavailable-description]",
  );

  const backend = page.querySelector(
    "[data-unavailable-backend]",
  );

  const drop = page.querySelector(
    "[data-unavailable-drop]",
  );

  const session = page.querySelector(
    "[data-unavailable-session]",
  );

  const checked = page.querySelector(
    "[data-unavailable-checked]",
  );

  if (title) {
    title.textContent = options.title;
  }

  if (message) {
    message.textContent = options.message;
  }

  if (description) {
    description.textContent =
      options.description;
  }

  if (backend) {
    backend.textContent =
      options.backendStatus;
  }

  if (drop) {
    drop.textContent = options.dropStatus;
  }

  if (session) {
    session.textContent =
      options.session || "—";
  }

  if (checked) {
    checked.textContent = formatTime();
  }
}

function extractHealthPayload(error) {
  if (!(error instanceof ApiError)) {
    return null;
  }

  const body = error.body;

  if (
    !body ||
    typeof body !== "object" ||
    body.drop_configured === undefined
  ) {
    return null;
  }

  return body;
}

function showDropUnavailable(health, message) {
  lastKnownAvailable = false;
  hideApplicationContent();

  const connectionState =
    normaliseConnectionState(
      health?.connection_state,
    );

  updateUnavailablePage({
    title: "DROP Service Unavailable",
    message:
      message ||
      "DROP is not connected. State data is temporarily unavailable.",
    description:
      "The backend service is running and attempting to reconnect.",
    backendStatus:
      health?.drop_service_running === false
        ? "Stopped"
        : "Connected",
    dropStatus: connectionState,
    session: health?.drop_session,
  });

  setConnectionStatus(
    "unavailable",
    "Backend connected",
    `DROP ${(
      health?.connection_state ||
      "unavailable"
    ).toLowerCase()}`,
  );
}

function showBackendUnavailable(message) {
  lastKnownAvailable = false;
  hideApplicationContent();

  updateUnavailablePage({
    title: "Backend Unavailable",
    message:
      message ||
      "The Market Control backend cannot be reached.",
    description:
      "Check the backend service or network connection, then retry.",
    backendStatus: "Unavailable",
    dropStatus: "Unknown",
    session: null,
  });

  setConnectionStatus(
    "unavailable",
    "Backend unavailable",
    "Connection failed",
  );
}

async function evaluateAvailability() {
  setConnectionStatus(
    "checking",
    "Checking backend",
    "Checking DROP status",
  );

  try {
    const health = await getHealth();

    if (health?.data_available !== true) {
      showDropUnavailable(health);

      return {
        available: false,
        recovered: false,
      };
    }

    const recovered =
      lastKnownAvailable === false ||
      getUnavailablePage() !== null;

    lastKnownAvailable = true;
    showApplicationContent();

    setConnectionStatus(
      "available",
      "Backend connected",
      "DROP live",
    );

    return {
      available: true,
      recovered,
    };
  } catch (error) {
    const health =
      extractHealthPayload(error);

    if (health) {
      showDropUnavailable(health);

      return {
        available: false,
        recovered: false,
      };
    }

    const message =
      error instanceof Error
        ? error.message
        : "The Market Control backend cannot be reached.";

    showBackendUnavailable(message);

    return {
      available: false,
      recovered: false,
    };
  }
}

async function runAvailabilityCheck({
  reloadOnRecovery = false,
  manual = false,
} = {}) {
  if (checkingAvailability) {
    return lastKnownAvailable === true;
  }

  checkingAvailability = true;
  clearAvailabilityTimer();

  const retryButton = document.querySelector(
    "[data-service-retry]",
  );

  const retryLabel = document.querySelector(
    "[data-service-retry-label]",
  );

  if (manual && retryButton) {
    retryButton.disabled = true;
  }

  if (manual && retryLabel) {
    retryLabel.textContent = "Checking...";
  }

  try {
    const result =
      await evaluateAvailability();

    if (
      result.available &&
      result.recovered &&
      reloadOnRecovery
    ) {
      reloadingAfterRecovery = true;
      window.location.reload();
    }

    return result.available;
  } finally {
    checkingAvailability = false;

    if (manual && retryButton) {
      retryButton.disabled = false;
    }

    if (manual && retryLabel) {
      retryLabel.textContent =
        "Retry connection";
    }

    scheduleAvailabilityCheck();
  }
}

function checkImmediatelyWhenVisible() {
  if (document.hidden) {
    scheduleAvailabilityCheck();
    return;
  }

  void runAvailabilityCheck({
    reloadOnRecovery: true,
  });
}

document.addEventListener(
  "visibilitychange",
  checkImmediatelyWhenVisible,
);

window.addEventListener(
  "online",
  checkImmediatelyWhenVisible,
);

window.addEventListener(
  "offline",
  function () {
    showBackendUnavailable(
      "The browser is offline. The backend cannot be reached.",
    );

    scheduleAvailabilityCheck();
  },
);

window.addEventListener(
  "beforeunload",
  clearAvailabilityTimer,
);

export async function ensureApplicationAvailable() {
  return runAvailabilityCheck({
    reloadOnRecovery: false,
  });
}

export function showStateUnavailableError(error) {
  const message =
    error instanceof Error
      ? error.message
      : "DROP is not connected. State data is temporarily unavailable.";

  showDropUnavailable(
    null,
    message,
  );

  scheduleAvailabilityCheck();
}
