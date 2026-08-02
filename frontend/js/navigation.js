const navigationItems = [
  { page: "users", label: "Users", href: "./index.html" },
  { page: "firms", label: "Firms", href: "./firms.html" },
  { page: "markets", label: "Markets", href: "./markets.html" },
];

let navigationInitialised = false;

function createNavigationLink(item, activePage) {
  const active = item.page === activePage ? ' aria-current="page"' : "";

  return `<a class="primary-nav-link" href="${item.href}" data-nav-page="${item.page}"${active}>${item.label}</a>`;
}

function createNavigationMarkup(activePage) {
  const links = navigationItems.map(function (item) {
    return createNavigationLink(item, activePage);
  }).join("");

  return `
    <div class="primary-nav-inner">
      <div class="primary-nav-links">
        ${links}
        <div class="more-menu">
          <button class="primary-nav-link primary-nav-link--button" type="button" data-more-menu-button aria-expanded="false" aria-controls="more-navigation-menu">
            <span>More</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 9 6 6 6-6"></path></svg>
          </button>
          <div class="more-dropdown" id="more-navigation-menu" data-more-menu-panel hidden>
            <p class="more-dropdown-label">Future modules</p>
            <button type="button" disabled><span>Sessions</span><small>Coming later</small></button>
            <button type="button" disabled><span>System events</span><small>Coming later</small></button>
            <button type="button" disabled><span>Reference data</span><small>Coming later</small></button>
          </div>
        </div>
      </div>
      <div class="primary-nav-context">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>
        <span>Live state</span>
      </div>
    </div>
  `;
}

function setExpanded(button, expanded) {
  button?.setAttribute("aria-expanded", String(expanded));
}

function closeMoreMenu() {
  const button = document.querySelector("[data-more-menu-button]");
  const panel = document.querySelector("[data-more-menu-panel]");

  if (panel) {
    panel.hidden = true;
  }

  setExpanded(button, false);
}

function closeMobileNavigation() {
  const navigation = document.querySelector("[data-primary-nav]");
  const button = document.querySelector("[data-mobile-nav-button]");

  navigation?.classList.remove("is-open");
  setExpanded(button, false);

  if (button) {
    button.setAttribute("aria-label", "Open navigation");
  }

  closeMoreMenu();
}

function initialiseNavigationEvents() {
  if (navigationInitialised) {
    return;
  }

  navigationInitialised = true;

  const navigation = document.querySelector("[data-primary-nav]");
  const mobileButton = document.querySelector("[data-mobile-nav-button]");

  navigation?.addEventListener("click", function (event) {
    const moreButton = event.target.closest("[data-more-menu-button]");

    if (moreButton) {
      const panel = document.querySelector("[data-more-menu-panel]");
      const opening = panel?.hidden === true;

      if (panel) {
        panel.hidden = !opening;
      }

      setExpanded(moreButton, opening);
      return;
    }

    if (event.target.closest("a")) {
      closeMobileNavigation();
    }
  });

  mobileButton?.addEventListener("click", function () {
    const opening = !navigation?.classList.contains("is-open");

    navigation?.classList.toggle("is-open", opening);
    setExpanded(mobileButton, opening);
    mobileButton.setAttribute("aria-label", opening ? "Close navigation" : "Open navigation");

    if (!opening) {
      closeMoreMenu();
    }
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest(".more-menu")) {
      closeMoreMenu();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeMobileNavigation();
    }
  });
}

export function renderNavigation(activePage = document.body.dataset.page) {
  const navigation = document.querySelector("[data-primary-nav]");

  if (!navigation) {
    return;
  }

  navigation.innerHTML = createNavigationMarkup(activePage);
  initialiseNavigationEvents();
}