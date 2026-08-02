import { getUsers } from "./api.js";
import {
  ensureApplicationAvailable,
  showStateUnavailableError,
} from "./availability.js";
import { renderNavigation } from "./navigation.js";

renderNavigation();

(function () {
  "use strict";

  const pageName = document.body.dataset.page || "";

  /*
   * Header navigation
   */

  function setExpanded(button, expanded) {
    if (button) {
      button.setAttribute(
        "aria-expanded",
        String(expanded),
      );
    }
  }

  function closeMenu(button, panel) {
    if (!button || !panel) {
      return;
    }

    panel.hidden = true;
    setExpanded(button, false);
  }

  function toggleMenu(button, panel) {
    if (!button || !panel) {
      return;
    }

    const willOpen = panel.hidden;

    panel.hidden = !willOpen;
    setExpanded(button, willOpen);
  }

  const userMenuButton = document.querySelector(
    "[data-user-menu-button]",
  );

  const userMenuPanel = document.querySelector(
    "[data-user-menu-panel]",
  );

  const moreMenuButton = document.querySelector(
    "[data-more-menu-button]",
  );

  const moreMenuPanel = document.querySelector(
    "[data-more-menu-panel]",
  );

  const mobileNavButton = document.querySelector(
    "[data-mobile-nav-button]",
  );

  const primaryNavigation = document.querySelector(
    "[data-primary-nav]",
  );

  userMenuButton?.addEventListener(
    "click",
    function (event) {
      event.stopPropagation();

      closeMenu(
        moreMenuButton,
        moreMenuPanel,
      );

      toggleMenu(
        userMenuButton,
        userMenuPanel,
      );
    },
  );

  moreMenuButton?.addEventListener(
    "click",
    function (event) {
      event.stopPropagation();

      closeMenu(
        userMenuButton,
        userMenuPanel,
      );

      toggleMenu(
        moreMenuButton,
        moreMenuPanel,
      );
    },
  );

  mobileNavButton?.addEventListener(
    "click",
    function () {
      if (!primaryNavigation) {
        return;
      }

      const willOpen =
        !primaryNavigation.classList.contains(
          "is-open",
        );

      primaryNavigation.classList.toggle(
        "is-open",
        willOpen,
      );

      setExpanded(
        mobileNavButton,
        willOpen,
      );

      mobileNavButton.setAttribute(
        "aria-label",
        willOpen
          ? "Close navigation"
          : "Open navigation",
      );

      if (!willOpen) {
        closeMenu(
          moreMenuButton,
          moreMenuPanel,
        );
      }
    },
  );

  primaryNavigation
    ?.querySelectorAll("a")
    .forEach(function (link) {
      link.addEventListener(
        "click",
        function () {
          primaryNavigation.classList.remove(
            "is-open",
          );

          setExpanded(
            mobileNavButton,
            false,
          );
        },
      );
    });

  document.addEventListener(
    "click",
    function (event) {
      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      if (!target.closest(".user-menu")) {
        closeMenu(
          userMenuButton,
          userMenuPanel,
        );
      }

      if (!target.closest(".more-menu")) {
        closeMenu(
          moreMenuButton,
          moreMenuPanel,
        );
      }
    },
  );

  document.addEventListener(
    "keydown",
    function (event) {
      if (event.key !== "Escape") {
        return;
      }

      closeMenu(
        userMenuButton,
        userMenuPanel,
      );

      closeMenu(
        moreMenuButton,
        moreMenuPanel,
      );

      primaryNavigation?.classList.remove(
        "is-open",
      );

      setExpanded(
        mobileNavButton,
        false,
      );
    },
  );

  /*
   * Table elements
   */

  const table = document.querySelector(
    "[data-entity-table]",
  );

  if (!table) {
    return;
  }

  const entityType =
    table.dataset.entityType || "entity";

  const searchInput = document.querySelector(
    "[data-search]",
  );

  const stateFilter = document.querySelector(
    "[data-state-filter]",
  );

  const emptyState = document.querySelector(
    "[data-empty-state]",
  );

  const summaryText = document.querySelector(
    ".summary-text",
  );

  const refreshedTime = document.querySelector(
    "[data-refreshed-time]",
  );

  const refreshButton = document.querySelector(
    "[data-refresh]",
  );

  const dialog = document.getElementById(
    "state-dialog",
  );

  const dialogTitle = document.querySelector(
    "[data-dialog-title]",
  );

  const dialogDescription =
    document.querySelector(
      "[data-dialog-description]",
    );

  const dialogEntity = document.querySelector(
    "[data-dialog-entity]",
  );

  const dialogIdentifier =
    document.querySelector(
      "[data-dialog-identifier]",
    );

  const dialogCurrentState =
    document.querySelector(
      "[data-dialog-current-state]",
    );

  const dialogRequestedState =
    document.querySelector(
      "[data-dialog-requested-state]",
    );

  const dialogIcon = document.querySelector(
    "[data-dialog-icon]",
  );

  const confirmButton = document.querySelector(
    "[data-dialog-confirm]",
  );

  const cancelButton = document.querySelector(
    "[data-dialog-cancel]",
  );

  const toastRegion = document.querySelector(
    "[data-toast-region]",
  );

  let selectedRow = null;
  let selectedAction = null;
  let loadingUsers = false;

  /*
   * General helpers
   */

  function titleCase(value) {
    if (!value) {
      return "";
    }

    return (
      value.charAt(0).toUpperCase() +
      value.slice(1)
    );
  }

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

  function updateRefreshedTime() {
    if (refreshedTime) {
      refreshedTime.textContent =
        formatTime();
    }
  }

  function formatTimestampNs(timestampNs) {
    if (
      timestampNs === null ||
      timestampNs === undefined ||
      timestampNs === ""
    ) {
      return "—";
    }

    let timestampMs;

    try {
      if (typeof timestampNs === "bigint") {
        timestampMs = Number(
          timestampNs / 1_000_000n,
        );
      } else {
        timestampMs =
          Number(timestampNs) / 1_000_000;
      }
    } catch {
      return "—";
    }

    const date = new Date(timestampMs);

    if (Number.isNaN(date.getTime())) {
      return "—";
    }

    return new Intl.DateTimeFormat(
      "en-GB",
      {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      },
    ).format(date);
  }

  function createTableCell(
    text,
    className = "",
  ) {
    const cell =
      document.createElement("td");

    cell.className = className;
    cell.textContent = text;

    return cell;
  }

  function showToast(title, message) {
    if (!toastRegion) {
      return;
    }

    const toast =
      document.createElement("div");

    toast.className = "toast";
    toast.setAttribute(
      "role",
      "status",
    );

    toast.innerHTML = `
      <div class="toast-icon" aria-hidden="true">
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
        >
          <path d="m5 12 4 4L19 6"></path>
        </svg>
      </div>

      <div>
        <div class="toast-title"></div>
        <div class="toast-message"></div>
      </div>
    `;

    const toastTitle =
      toast.querySelector(".toast-title");

    const toastMessage =
      toast.querySelector(
        ".toast-message",
      );

    if (toastTitle) {
      toastTitle.textContent = title;
    }

    if (toastMessage) {
      toastMessage.textContent = message;
    }

    toastRegion.appendChild(toast);

    window.setTimeout(
      function () {
        toast.remove();
      },
      3200,
    );
  }

  /*
   * User state helpers
   */

  function getUserStateLabel(state) {
    if (state === "A") {
      return "Active";
    }

    if (state === "S") {
      return "Suspended";
    }

    return state || "Unknown";
  }

  function getUserStateValue(state) {
    if (state === "A") {
      return "active";
    }

    if (state === "S") {
      return "suspended";
    }

    return "unknown";
  }

  /*
   * Users table rendering
   */

  function createUserRow(user) {
    const row =
      document.createElement("tr");

    const state =
      getUserStateValue(user.state);

    const action =
      state === "active"
        ? "suspend"
        : "activate";

    row.dataset.row = "";
    row.dataset.state = state;
    row.dataset.userId =
      String(user.user_id ?? "");

    row.dataset.id =
      String(user.user_id ?? "");

    row.dataset.name =
      user.user_name || "Unknown";

    const searchableValues = [
      user.user_id,
      user.user_name,
      user.firm_id,
      user.capacity,
      user.user_type_name,
      user.user_type_id,
      getUserStateLabel(user.state),
    ];

    row.dataset.search =
      searchableValues
        .filter(
          function (value) {
            return (
              value !== null &&
              value !== undefined
            );
          },
        )
        .join(" ")
        .toLowerCase();

    row.className =
      "border-b border-slate-100 last:border-b-0 hover:bg-slate-50";

    /*
     * User ID
     */

    row.appendChild(
      createTableCell(
        String(user.user_id ?? "—"),
        "whitespace-nowrap px-6 py-4 text-sm font-medium text-slate-900",
      ),
    );

    /*
     * Username
     */

    row.appendChild(
      createTableCell(
        user.user_name || "—",
        "whitespace-nowrap px-6 py-4 text-sm text-slate-700",
      ),
    );

    /*
     * Firm
     */

    row.appendChild(
      createTableCell(
        String(user.firm_id ?? "—"),
        "whitespace-nowrap px-6 py-4 text-sm text-slate-600",
      ),
    );

    /*
     * Capacity
     */

    row.appendChild(
      createTableCell(
        user.capacity || "—",
        "whitespace-nowrap px-6 py-4 text-sm text-slate-600",
      ),
    );

    /*
     * User type
     */

    row.appendChild(
      createTableCell(
        String(
          user.user_type_name ??
            user.user_type_id ??
            "—",
        ),
        "whitespace-nowrap px-6 py-4 text-sm text-slate-600",
      ),
    );

    /*
     * State badge
     */

    const stateCell =
      document.createElement("td");

    stateCell.className =
      "whitespace-nowrap px-6 py-4";

    const stateBadge =
      document.createElement("span");

    stateBadge.dataset.stateBadge = "";

    stateBadge.className =
      `state-badge state-badge--${state}`;

    stateBadge.textContent =
      getUserStateLabel(user.state);

    stateCell.appendChild(stateBadge);
    row.appendChild(stateCell);

    /*
     * Last updated
     */

    const updatedCell =
      createTableCell(
        formatTimestampNs(
          user.state_timestamp_ns,
        ),
        "whitespace-nowrap px-6 py-4 text-sm text-slate-500",
      );

    updatedCell.dataset.updatedTime = "";

    row.appendChild(updatedCell);

    /*
     * Action button
     */

    const actionCell =
      document.createElement("td");

    actionCell.className =
      "whitespace-nowrap px-6 py-4 text-right";

    const actionButton =
      document.createElement("button");

    actionButton.type = "button";
    actionButton.dataset.stateAction = "";
    actionButton.dataset.action = action;

    actionButton.dataset.userId =
      String(user.user_id ?? "");

    actionButton.className =
      `action-button action-button--${action}`;

    actionButton.textContent =
      titleCase(action);

    if (state === "unknown") {
      actionButton.disabled = true;
      actionButton.textContent =
        "Unavailable";
    }

    actionCell.appendChild(
      actionButton,
    );

    row.appendChild(actionCell);

    return row;
  }

  function renderUsers(users) {
    const tableBody =
      document.querySelector(
        "#users-table-body",
      );

    if (!tableBody) {
      return;
    }

    tableBody.replaceChildren();

    if (users.length === 0) {
      renderUsersMessage(
        "No users were returned by the backend.",
      );

      return;
    }

    const fragment =
      document.createDocumentFragment();

    for (const user of users) {
      fragment.appendChild(
        createUserRow(user),
      );
    }

    tableBody.appendChild(fragment);
  }

  function renderUsersMessage(
    message,
    isError = false,
  ) {
    const tableBody =
      document.querySelector(
        "#users-table-body",
      );

    if (!tableBody) {
      return;
    }

    const row =
      document.createElement("tr");

    const cell =
      document.createElement("td");

    cell.colSpan = 8;

    cell.className = isError
      ? "px-6 py-10 text-center text-sm text-red-600"
      : "px-6 py-10 text-center text-sm text-slate-500";

    cell.textContent = message;

    row.appendChild(cell);
    tableBody.replaceChildren(row);

    emptyState?.classList.remove(
      "is-visible",
    );
  }

  /*
   * Search and filtering
   */

  function updateSummary(
    visibleCount,
    totalCount,
  ) {
    if (!summaryText) {
      return;
    }

    const strong =
      document.createElement("strong");

    strong.textContent =
      String(visibleCount);

    const label =
      entityType === "user"
        ? "users"
        : `${entityType}s`;

    summaryText.replaceChildren(
      strong,
      document.createTextNode(
        ` of ${totalCount} ${label}`,
      ),
    );
  }

  function applyFilters() {
    const rows = Array.from(
      table.querySelectorAll(
        "tbody tr[data-row]",
      ),
    );

    const query =
      (searchInput?.value || "")
        .trim()
        .toLowerCase();

    const requestedState =
      stateFilter?.value || "all";

    let visibleRows = 0;

    for (const row of rows) {
      const searchable =
        (
          row.dataset.search ||
          row.textContent ||
          ""
        ).toLowerCase();

      const rowState =
        row.dataset.state || "";

      const matchesQuery =
        !query ||
        searchable.includes(query);

      const matchesState =
        requestedState === "all" ||
        rowState === requestedState;

      const visible =
        matchesQuery &&
        matchesState;

      row.hidden = !visible;

      if (visible) {
        visibleRows += 1;
      }
    }

    updateSummary(
      visibleRows,
      rows.length,
    );

    emptyState?.classList.toggle(
      "is-visible",
      rows.length > 0 &&
        visibleRows === 0,
    );
  }

  /*
   * Confirmation dialog
   */

  function configureDialog(
    row,
    action,
  ) {
    if (
      !dialog ||
      !row ||
      !action
    ) {
      return;
    }

    const displayName =
      row.dataset.name || "Unknown";

    const identifier =
      row.dataset.id || "—";

    const currentState =
      row.dataset.state === "active"
        ? "Active"
        : "Suspended";

    const requestedState =
      action === "suspend"
        ? "Suspended"
        : "Active";

    const actionWord =
      action === "suspend"
        ? "Suspend"
        : "Activate";

    selectedRow = row;
    selectedAction = action;

    if (dialogTitle) {
      dialogTitle.textContent =
        `${actionWord} ${entityType}?`;
    }

    if (dialogDescription) {
      dialogDescription.textContent =
        `This preview updates the ${entityType} row locally. The backend control API will be connected next.`;
    }

    if (dialogEntity) {
      dialogEntity.textContent =
        displayName;
    }

    if (dialogIdentifier) {
      dialogIdentifier.textContent =
        identifier;
    }

    if (dialogCurrentState) {
      dialogCurrentState.textContent =
        currentState;
    }

    if (dialogRequestedState) {
      dialogRequestedState.textContent =
        requestedState;
    }

    if (confirmButton) {
      confirmButton.textContent =
        action === "suspend"
          ? "Confirm suspension"
          : "Confirm activation";

      confirmButton.className =
        `dialog-button ${
          action === "suspend"
            ? "dialog-button--confirm-danger"
            : "dialog-button--confirm-success"
        }`;
    }

    if (dialogIcon) {
      dialogIcon.className =
        `dialog-icon ${
          action === "suspend"
            ? "dialog-icon--danger"
            : "dialog-icon--success"
        }`;
    }

    dialog.showModal();
  }

  function updateRowState(
    row,
    action,
  ) {
    const newState =
      action === "suspend"
        ? "suspended"
        : "active";

    const badge = row.querySelector(
      "[data-state-badge]",
    );

    const button = row.querySelector(
      "[data-state-action]",
    );

    const timestamp = row.querySelector(
      "[data-updated-time]",
    );

    row.dataset.state = newState;

    if (badge) {
      badge.textContent =
        titleCase(newState);

      badge.className =
        `state-badge state-badge--${newState}`;
    }

    if (button) {
      const nextAction =
        newState === "active"
          ? "suspend"
          : "activate";

      button.dataset.action =
        nextAction;

      button.textContent =
        titleCase(nextAction);

      button.className =
        `action-button action-button--${nextAction}`;
    }

    if (timestamp) {
      timestamp.textContent =
        formatTime();
    }

    showToast(
      `${titleCase(entityType)} ${newState}`,
      `${row.dataset.name} is now ${newState}.`,
    );

    applyFilters();
    updateRefreshedTime();
  }

  /*
   * Users API loading
   */

  function updateUsersNavigationCount(
    count,
  ) {
    const countElement =
      document.querySelector(
        'a[href="index.html"] .primary-nav-count',
      );

    if (countElement) {
      countElement.textContent =
        String(count);
    }
  }

  function updateConnectionStatus(
    connected,
  ) {
    const connection =
      document.querySelector(
        ".connection",
      );

    const title =
      connection?.querySelector(
        "strong",
      );

    const subtitle =
      connection?.querySelector(
        ".connection-copy span",
      );

    if (title) {
      title.textContent = connected
        ? "Backend connected"
        : "Backend unavailable";
    }

    if (subtitle) {
      subtitle.textContent = connected
        ? "DROP live"
        : "Connection failed";
    }
  }

  async function loadUsersPage() {
    if (loadingUsers) {
      return;
    }

    loadingUsers = true;

    if (refreshButton) {
      refreshButton.disabled = true;
    }

    renderUsersMessage(
      "Loading users...",
    );

    try {
      const response =
        await getUsers();

      const users =
        Array.isArray(response.items)
          ? response.items
          : [];

      renderUsers(users);
      updateUsersNavigationCount(
        users.length,
      );

      updateConnectionStatus(true);
      updateRefreshedTime();
      applyFilters();

      console.log(
        `Loaded ${users.length} users`,
      );
    } catch (error) {
      console.error(
        "Unable to load users:",
        error,
      );

      if (
        error &&
        error.code === "state_unavailable"
      ) {
        showStateUnavailableError(error);
        updateSummary(0, 0);
        return;
      }

      const message =
        error instanceof Error
          ? error.message
          : "Unknown Users API error";

      renderUsersMessage(
        `Unable to load users: ${message}`,
        true,
      );

      updateConnectionStatus(false);
      updateSummary(0, 0);
    } finally {
      loadingUsers = false;

      if (refreshButton) {
        refreshButton.disabled = false;
      }
    }
  }

  /*
   * Event listeners
   */

  table.addEventListener(
    "click",
    function (event) {
      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      const button = target.closest(
        "[data-state-action]",
      );

      if (!button || button.disabled) {
        return;
      }

      const row = button.closest(
        "tr[data-row]",
      );

      configureDialog(
        row,
        button.dataset.action,
      );
    },
  );

  searchInput?.addEventListener(
    "input",
    applyFilters,
  );

  stateFilter?.addEventListener(
    "change",
    applyFilters,
  );

  refreshButton?.addEventListener(
    "click",
    function () {
      if (pageName === "users") {
        void loadUsersPage();
        return;
      }

      updateRefreshedTime();
      applyFilters();
    },
  );

  cancelButton?.addEventListener(
    "click",
    function () {
      dialog?.close();

      selectedRow = null;
      selectedAction = null;
    },
  );

  confirmButton?.addEventListener(
    "click",
    function () {
      if (
        selectedRow &&
        selectedAction
      ) {
        updateRowState(
          selectedRow,
          selectedAction,
        );
      }

      dialog?.close();

      selectedRow = null;
      selectedAction = null;
    },
  );

  dialog?.addEventListener(
    "click",
    function (event) {
      const bounds =
        dialog.getBoundingClientRect();

      const clickedOutside =
        event.clientX < bounds.left ||
        event.clientX > bounds.right ||
        event.clientY < bounds.top ||
        event.clientY > bounds.bottom;

      if (clickedOutside) {
        dialog.close();

        selectedRow = null;
        selectedAction = null;
      }
    },
  );

  /*
   * Page startup
   */

  async function startPage() {
    const available =
      await ensureApplicationAvailable();

    if (!available) {
      return;
    }

    if (pageName === "users") {
      await loadUsersPage();
      return;
    }

    updateRefreshedTime();
    applyFilters();
  }

  void startPage();
})();