// "Translate this page" -- opens Google Translate's proxy view for the
// current page in a new tab, rather than embedding Google's official
// website-translator widget (which injects third-party JS into every
// page load and has had pieces deprecated over time). Zero external
// script dependency, works for any language Google Translate supports.
// Reuses the existing `.fa-svg` class so it inherits the same padding/
// sizing as the built-in print/git-repository/git-edit icon buttons.
(function () {
  // mdBook renamed #menu-bar to #mdbook-menu-bar somewhere around
  // 0.5.x (this project's CI pins an older mdBook than the version
  // used for local dev builds, so the deployed HTML used the old,
  // unprefixed ID -- the button silently never appeared on the real
  // site, confirmed by diffing local-build vs deployed-site DOM).
  // Match both so this keeps working across an mdBook version bump
  // either way.
  var rightButtons = document.querySelector(
    "#mdbook-menu-bar .right-buttons, #menu-bar .right-buttons"
  );
  if (!rightButtons) {
    return;
  }
  var link = document.createElement("a");
  link.href =
    "https://translate.google.com/translate?sl=en&u=" +
    encodeURIComponent(window.location.href);
  link.title = "Translate this page";
  link.setAttribute("aria-label", "Translate this page");
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  var icon = document.createElement("span");
  icon.className = "fa-svg";
  icon.id = "translate-button";
  icon.textContent = "\u{1F310}"; // 🌐
  link.appendChild(icon);
  rightButtons.insertBefore(link, rightButtons.firstChild);
})();
