import { getUsers } from "./api.js";

async function testUsersApi() {
  try {
    const response = await getUsers();

    console.log("Users API response:", response);
    console.log("Users:", response.items);
  } catch (error) {
    console.error("Unable to load users:", error);
  }
}

testUsersApi();

(function () {
    "use strict";

    function setExpanded(button, expanded) {
        if (button) {
            button.setAttribute("aria-expanded", String(expanded));
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

    const userMenuButton = document.querySelector("[data-user-menu-button]");
    const userMenuPanel = document.querySelector("[data-user-menu-panel]");
    const moreMenuButton = document.querySelector("[data-more-menu-button]");
    const moreMenuPanel = document.querySelector("[data-more-menu-panel]");
    const mobileNavButton = document.querySelector("[data-mobile-nav-button]");
    const primaryNavigation = document.querySelector("[data-primary-nav]");

    userMenuButton?.addEventListener("click", function (event) {
        event.stopPropagation();
        closeMenu(moreMenuButton, moreMenuPanel);
        toggleMenu(userMenuButton, userMenuPanel);
    });

    moreMenuButton?.addEventListener("click", function (event) {
        event.stopPropagation();
        closeMenu(userMenuButton, userMenuPanel);
        toggleMenu(moreMenuButton, moreMenuPanel);
    });

    mobileNavButton?.addEventListener("click", function () {
        const willOpen = !primaryNavigation.classList.contains("is-open");
        primaryNavigation.classList.toggle("is-open", willOpen);
        setExpanded(mobileNavButton, willOpen);
        mobileNavButton.setAttribute("aria-label", willOpen ? "Close navigation" : "Open navigation");

        if (!willOpen) {
            closeMenu(moreMenuButton, moreMenuPanel);
        }
    });

    primaryNavigation?.querySelectorAll("a").forEach(function (link) {
        link.addEventListener("click", function () {
            primaryNavigation.classList.remove("is-open");
            setExpanded(mobileNavButton, false);
        });
    });

    document.addEventListener("click", function (event) {
        if (!event.target.closest(".user-menu")) {
            closeMenu(userMenuButton, userMenuPanel);
        }

        if (!event.target.closest(".more-menu")) {
            closeMenu(moreMenuButton, moreMenuPanel);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }

        closeMenu(userMenuButton, userMenuPanel);
        closeMenu(moreMenuButton, moreMenuPanel);
        primaryNavigation?.classList.remove("is-open");
        setExpanded(mobileNavButton, false);
    });

    const table = document.querySelector("[data-entity-table]");
    if (!table) {
        return;
    }

    const entityType = table.dataset.entityType || "entity";
    const searchInput = document.querySelector("[data-search]");
    const stateFilter = document.querySelector("[data-state-filter]");
    const rows = Array.from(table.querySelectorAll("tbody tr[data-row]"));
    const visibleCount = document.querySelector("[data-visible-count]");
    const emptyState = document.querySelector("[data-empty-state]");
    const refreshedTime = document.querySelector("[data-refreshed-time]");
    const refreshButton = document.querySelector("[data-refresh]");
    const dialog = document.getElementById("state-dialog");
    const dialogTitle = document.querySelector("[data-dialog-title]");
    const dialogDescription = document.querySelector("[data-dialog-description]");
    const dialogEntity = document.querySelector("[data-dialog-entity]");
    const dialogIdentifier = document.querySelector("[data-dialog-identifier]");
    const dialogCurrentState = document.querySelector("[data-dialog-current-state]");
    const dialogRequestedState = document.querySelector("[data-dialog-requested-state]");
    const dialogIcon = document.querySelector("[data-dialog-icon]");
    const confirmButton = document.querySelector("[data-dialog-confirm]");
    const cancelButton = document.querySelector("[data-dialog-cancel]");
    const toastRegion = document.querySelector("[data-toast-region]");

    let selectedRow = null;
    let selectedAction = null;

    function formatTime() {
        return new Intl.DateTimeFormat("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        }).format(new Date());
    }

    function updateRefreshedTime() {
        if (refreshedTime) {
            refreshedTime.textContent = formatTime();
        }
    }

    function applyFilters() {
        const query = (searchInput?.value || "").trim().toLowerCase();
        const requestedState = stateFilter?.value || "all";
        let count = 0;

        rows.forEach(function (row) {
            const searchable = (row.dataset.search || row.textContent || "").toLowerCase();
            const rowState = row.dataset.state || "";
            const matchesQuery = !query || searchable.includes(query);
            const matchesState = requestedState === "all" || rowState === requestedState;
            const visible = matchesQuery && matchesState;

            row.hidden = !visible;
            if (visible) {
                count += 1;
            }
        });

        if (visibleCount) {
            visibleCount.textContent = String(count);
        }

        emptyState?.classList.toggle("is-visible", count === 0);
    }

    function titleCase(value) {
        return value.charAt(0).toUpperCase() + value.slice(1);
    }

    function configureDialog(row, action) {
        const displayName = row.dataset.name || "Unknown";
        const identifier = row.dataset.id || "—";
        const currentState = row.dataset.state === "active" ? "Active" : "Suspended";
        const requestedState = action === "suspend" ? "Suspended" : "Active";
        const actionWord = action === "suspend" ? "Suspend" : "Activate";

        selectedRow = row;
        selectedAction = action;

        dialogTitle.textContent = `${actionWord} ${entityType}?`;
        dialogDescription.textContent = `This static preview will update the ${entityType} row locally. The backend API will be connected later.`;
        dialogEntity.textContent = displayName;
        dialogIdentifier.textContent = identifier;
        dialogCurrentState.textContent = currentState;
        dialogRequestedState.textContent = requestedState;
        confirmButton.textContent = action === "suspend" ? "Confirm suspension" : "Confirm activation";
        confirmButton.className = `dialog-button ${action === "suspend" ? "dialog-button--confirm-danger" : "dialog-button--confirm-success"}`;
        dialogIcon.className = `dialog-icon ${action === "suspend" ? "dialog-icon--danger" : "dialog-icon--success"}`;

        dialog.showModal();
    }

    function updateRowState(row, action) {
        const newState = action === "suspend" ? "suspended" : "active";
        const badge = row.querySelector("[data-state-badge]");
        const button = row.querySelector("[data-state-action]");
        const timestamp = row.querySelector("[data-updated-time]");

        row.dataset.state = newState;

        if (badge) {
            badge.textContent = titleCase(newState);
            badge.className = `state-badge state-badge--${newState}`;
        }

        if (button) {
            const nextAction = newState === "active" ? "suspend" : "activate";
            button.dataset.action = nextAction;
            button.textContent = titleCase(nextAction);
            button.className = `action-button action-button--${nextAction}`;
        }

        if (timestamp) {
            timestamp.textContent = formatTime();
        }

        showToast(
            `${titleCase(entityType)} ${newState}`,
            `${row.dataset.name} is now ${newState}.`,
        );

        applyFilters();
        updateRefreshedTime();
    }

    function showToast(title, message) {
        if (!toastRegion) {
            return;
        }

        const toast = document.createElement("div");
        toast.className = "toast";
        toast.setAttribute("role", "status");
        toast.innerHTML = `
            <div class="toast-icon" aria-hidden="true">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <path d="m5 12 4 4L19 6"></path>
                </svg>
            </div>
            <div>
                <div class="toast-title"></div>
                <div class="toast-message"></div>
            </div>
        `;
        toast.querySelector(".toast-title").textContent = title;
        toast.querySelector(".toast-message").textContent = message;
        toastRegion.appendChild(toast);

        window.setTimeout(function () {
            toast.remove();
        }, 3200);
    }

    table.addEventListener("click", function (event) {
        const button = event.target.closest("[data-state-action]");
        if (!button) {
            return;
        }

        const row = button.closest("tr[data-row]");
        configureDialog(row, button.dataset.action);
    });

    searchInput?.addEventListener("input", applyFilters);
    stateFilter?.addEventListener("change", applyFilters);

    refreshButton?.addEventListener("click", function () {
        updateRefreshedTime();
        showToast("Static data refreshed", "Mock table data is ready. API loading will be added later.");
    });

    cancelButton?.addEventListener("click", function () {
        dialog.close();
    });

    confirmButton?.addEventListener("click", function () {
        if (selectedRow && selectedAction) {
            updateRowState(selectedRow, selectedAction);
        }
        dialog.close();
        selectedRow = null;
        selectedAction = null;
    });

    dialog?.addEventListener("click", function (event) {
        const bounds = dialog.getBoundingClientRect();
        const clickedOutside =
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom;

        if (clickedOutside) {
            dialog.close();
        }
    });

    updateRefreshedTime();
    applyFilters();
})();
