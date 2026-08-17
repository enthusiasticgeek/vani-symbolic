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
  // Reported directly: the button appeared but "cannot translate" --
  // the link never passed a `tl` (target language), so Google's own
  // redirect from translate.google.com/translate to the real
  // <host>.translate.goog proxy defaulted `tl` to match `sl` (en->en,
  // a same-language no-op that renders the page completely unchanged
  // even though the request itself succeeds). Confirmed by curling
  // the redirect chain with and without an explicit `tl`: identical
  // request otherwise, only the target-language default differs.
  // Fixed by always passing a real target language, read from the
  // visitor's own browser locale (the best available signal for
  // "what language does this reader actually want") rather than
  // asking or hardcoding one.
  var SOURCE_LANG = "en"; // every page on this site is authored in English
  var targetLang = ((navigator.language || navigator.userLanguage || "en").split("-")[0] || "en").toLowerCase();
  // Found while re-verifying the fix below: translate.goog returns a
  // hard 400 (not a harmless same-language no-op) whenever tl equals
  // sl -- confirmed by curling sl=en&tl=en (400) against sl=en&tl=de
  // (200) and sl=auto&tl=en (200), isolating it to the tl==sl case
  // specifically. An English-locale visitor (the majority case) would
  // otherwise always hit this error, independent of either fix below
  // -- likely the actual root cause of "cannot translate" on a phone
  // whose Chrome/OS language is English. There's nothing meaningful to
  // translate into the page's own source language anyway, so skip
  // rendering the button entirely in that case rather than link to a
  // request Google will reject.
  if (targetLang === SOURCE_LANG) {
    return;
  }
  // Reported again on Chrome for Android specifically: tapping the
  // (now correctly tl-targeted) translate.google.com/translate link
  // produced Chrome's own native "Couldn't translate this page" error
  // instead of navigating anywhere -- the mobile Chrome app appears to
  // specially intercept links to that exact host+path and hand them to
  // its built-in translate-infobar flow rather than treating them as
  // an ordinary external URL, and that native flow fails independently
  // of whether the link itself is correct (confirmed the link's own
  // request chain still returns a real 200 via curl with a mobile
  // Chrome User-Agent). Sidestepped by building the actual
  // <host>.translate.goog proxy URL directly instead of going through
  // translate.google.com/translate's redirect -- from Chrome's
  // perspective this is just an ordinary link to an ordinary external
  // domain, no special interception applies. Escapes a literal "-" in
  // the hostname first (as "--") before substituting "." with "-",
  // matching Google's own reversible host-encoding scheme (not
  // exercised by this site's own "enthusiasticgeek.github.io" host,
  // which has no hyphens, but correct in general).
  var host = window.location.hostname
    .replace(/-/g, "--")
    .replace(/\./g, "-");
  var link = document.createElement("a");
  link.href =
    "https://" +
    host +
    ".translate.goog" +
    window.location.pathname +
    "?_x_tr_sl=" +
    SOURCE_LANG +
    "&_x_tr_tl=" +
    encodeURIComponent(targetLang) +
    "&_x_tr_hl=" +
    encodeURIComponent(targetLang) +
    "&_x_tr_pto=wapp";
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
