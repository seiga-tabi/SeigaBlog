const state = {
  lang: localStorage.getItem("seiga-lang") || "ko",
  category: "all",
  query: "",
  savedOnly: false,
  saved: new Set(JSON.parse(localStorage.getItem("seiga-saved") || "[]")),
};

const app = document.querySelector("#app");
const searchInput = document.querySelector("#searchInput");
const resultCount = document.querySelector("#resultCount");
const emptyState = document.querySelector("#emptyState");
const notifyButton = document.querySelector("#notifyButton");

function localized(node, key = state.lang) {
  return node?.dataset?.[key] || "";
}

function setLocalizedText() {
  document.documentElement.lang = state.lang;

  document.querySelectorAll("[data-ko][data-ja]").forEach((node) => {
    if ([...node.childNodes].some((child) => child.nodeType === Node.ELEMENT_NODE)) {
      return;
    }

    node.textContent = localized(node);
  });

  document.querySelectorAll("[data-placeholder-ko][data-placeholder-ja]").forEach((node) => {
    node.placeholder = node.dataset[`placeholder${suffix()}`];
  });

  document.querySelectorAll("[data-label-ko][data-label-ja]").forEach((node) => {
    node.setAttribute("aria-label", node.dataset[`label${suffix()}`]);
  });

  document.querySelectorAll("[data-alt-ko][data-alt-ja]").forEach((node) => {
    node.alt = node.dataset[`alt${suffix()}`];
  });

  document.querySelectorAll(".lang-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.lang === state.lang);
  });
}

function suffix() {
  return state.lang === "ja" ? "Ja" : "Ko";
}

function postCards() {
  return [...document.querySelectorAll("[data-post-card]")];
}

function detailPanels() {
  return [...document.querySelectorAll("[data-detail-panel]")];
}

function selectedPostId() {
  return document.querySelector("[data-detail-panel].is-active")?.dataset.postId;
}

function visibleCards() {
  return postCards().filter((card) => !card.hidden);
}

function normalize(value) {
  return value.trim().toLocaleLowerCase();
}

function matchesCard(card) {
  const inCategory = state.category === "all" || card.dataset.category === state.category;
  const inSaved = !state.savedOnly || state.saved.has(card.dataset.postId);
  const searchText = card.dataset[`search${suffix()}`]?.toLocaleLowerCase() || "";

  return inCategory && inSaved && (!state.query || searchText.includes(normalize(state.query)));
}

function updateFilters() {
  let count = 0;

  postCards().forEach((card) => {
    const isVisible = matchesCard(card);
    card.hidden = !isVisible;
    count += isVisible ? 1 : 0;
  });

  updateResultCount(count);
  updateEmptyState(count);
  ensureActivePost();
}

function updateResultCount(count) {
  if (!resultCount) {
    return;
  }

  const suffixText = resultCount.dataset[`suffix${suffix()}`];
  resultCount.textContent = `${count}${suffixText}`;
}

function updateEmptyState(count) {
  if (!emptyState) {
    return;
  }

  emptyState.hidden = count > 0;
  emptyState.textContent = state.savedOnly
    ? app.dataset[`savedEmpty${suffix()}`]
    : app.dataset[`empty${suffix()}`];
}

function ensureActivePost() {
  const currentId = selectedPostId();
  const currentCardVisible = visibleCards().some((card) => card.dataset.postId === currentId);
  const fallbackId = visibleCards()[0]?.dataset.postId;

  if (!currentCardVisible && fallbackId) {
    activatePost(fallbackId, false);
  }
}

function activatePost(postId, openDetail = true) {
  document.querySelectorAll("[data-post-card], [data-open-post]").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.postId === postId || node.dataset.openPost === postId);
  });

  detailPanels().forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.postId === postId);
  });

  if (openDetail) {
    app?.classList.add("show-detail");
    history.replaceState(null, "", `#${postId}`);
  }
}

function closeDetail() {
  app?.classList.remove("show-detail");
  if (location.hash) {
    history.replaceState(null, "", location.pathname);
  }
}

function updateBookmarks() {
  document.querySelectorAll("[data-bookmark]").forEach((button) => {
    const isSaved = state.saved.has(button.dataset.bookmark);
    button.classList.toggle("is-saved", isSaved);
    button.setAttribute(
      "aria-label",
      isSaved ? button.dataset[`removeLabel${suffix()}`] : button.dataset[`label${suffix()}`],
    );
  });
}

function persistBookmarks() {
  localStorage.setItem("seiga-saved", JSON.stringify([...state.saved]));
}

function toggleBookmark(postId) {
  const wasSaved = state.saved.has(postId);

  if (wasSaved) {
    state.saved.delete(postId);
  } else {
    state.saved.add(postId);
  }

  persistBookmarks();
  render();
  showToast(wasSaved ? app.dataset[`removed${suffix()}`] : app.dataset[`saved${suffix()}`]);
}

function showToast(message) {
  document.querySelector(".toast")?.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.append(toast);
  window.setTimeout(() => toast.remove(), 1800);
}

function syncFromHash() {
  const postId = location.hash.replace("#", "");
  if (postId && document.querySelector(`[data-detail-panel][data-post-id="${postId}"]`)) {
    activatePost(postId, true);
  }
}

function refreshIcons() {
  window.lucide?.createIcons();
}

function render() {
  setLocalizedText();
  updateFilters();
  updateBookmarks();
  refreshIcons();
}

document.addEventListener("click", (event) => {
  const langButton = event.target.closest("[data-lang]");
  const categoryButton = event.target.closest(".chip[data-category]");
  const bookmarkButton = event.target.closest("[data-bookmark]");
  const postLink = event.target.closest("[data-open-post]");
  const actionButton = event.target.closest("[data-action]");
  const closeButton = event.target.closest("[data-close-detail]");

  if (langButton) {
    state.lang = langButton.dataset.lang;
    localStorage.setItem("seiga-lang", state.lang);
    render();
    return;
  }

  if (categoryButton) {
    state.category = categoryButton.dataset.category;
    state.savedOnly = false;
    document.querySelectorAll(".chip[data-category]").forEach((button) => {
      const isActive = button === categoryButton;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
    render();
    return;
  }

  if (bookmarkButton) {
    event.preventDefault();
    event.stopPropagation();
    toggleBookmark(bookmarkButton.dataset.bookmark);
    return;
  }

  if (postLink && app?.dataset.page === "home") {
    event.preventDefault();
    activatePost(postLink.dataset.openPost);
    return;
  }

  if (closeButton && app?.dataset.page === "home") {
    event.preventDefault();
    closeDetail();
    return;
  }

  if (!actionButton) {
    return;
  }

  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("is-active", button === actionButton);
  });

  if (actionButton.dataset.action === "home") {
    state.savedOnly = false;
    state.category = "all";
    closeDetail();
    document.querySelector('.chip[data-category="all"]')?.click();
  }

  if (actionButton.dataset.action === "search") {
    searchInput?.focus();
  }

  if (actionButton.dataset.action === "bookmarks") {
    state.savedOnly = true;
    state.category = "all";
    closeDetail();
    render();
  }

  if (actionButton.dataset.action === "language") {
    state.lang = state.lang === "ko" ? "ja" : "ko";
    localStorage.setItem("seiga-lang", state.lang);
    render();
  }
});

searchInput?.addEventListener("input", (event) => {
  state.query = event.target.value;
  render();
});

notifyButton?.addEventListener("click", () => {
  showToast(notifyButton.dataset[`label${suffix()}`]);
});

window.addEventListener("hashchange", syncFromHash);

syncFromHash();
render();
