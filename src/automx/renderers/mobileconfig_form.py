"""Credential-free browser UI for Apple configuration profiles."""

from __future__ import annotations


def render_mobileconfig_form() -> str:
    """Return the Mobileconfig request form."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Apple Mail configuration · automx</title>
  <link rel="stylesheet" href="/mobileconfig.css">
  <script src="/mobileconfig.js" defer></script>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/mobileconfig">automx</a>
    <div class="preferences">
      <label class="language-control"><span data-i18n="language">Language</span>
        <select data-language-select aria-label="Language">
          <option value="de">Deutsch</option>
          <option value="en">English</option>
        </select>
      </label>
      <label class="theme-control"><span data-i18n="appearance">Appearance</span>
        <select data-theme-select>
          <option value="auto">Auto</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>
    </div>
  </header>
  <main class="shell narrow">
    <section class="card">
      <p class="eyebrow" data-i18n="eyebrow">Apple Mail</p>
      <h1 data-i18n="heading">Configure your account</h1>
      <p class="muted" data-i18n="intro">Enter the mail address and optional display name for this device.</p>
      <form action="/mobileconfig" method="post">
        <input type="hidden" name="_mobileconfig" value="true">
        <label for="emailaddress" data-i18n="email">Mail address</label>
        <input id="emailaddress" name="emailaddress" type="email"
               autocomplete="email" inputmode="email" required>
        <label for="cn"><span data-i18n="displayName">Display name</span>
          <span data-i18n="optional">(optional)</span>
        </label>
        <input id="cn" name="cn" type="text" autocomplete="name">
        <button type="submit" data-i18n="button">Download configuration profile</button>
      </form>
      <p class="footnote muted" data-i18n="footnote">The device requests account credentials when it first connects.</p>
    </section>
  </main>
</body>
</html>
"""


def render_mobileconfig_styles() -> str:
    """Return styles aligned with the RNS Crypto service design system."""
    return """:root {
  color-scheme: light dark;
  --bg: #f4f7f6;
  --surface: #ffffff;
  --text: #16201d;
  --muted: #5b6b66;
  --line: #d8e2df;
  --accent: #087f5b;
  --accent-strong: #056246;
  --accent-text: #ffffff;
  --shadow: 0 18px 50px rgb(20 50 40 / 9%);
}

:root[data-theme="light"] {
  color-scheme: light;
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0e1513;
  --surface: #17201d;
  --text: #eff8f4;
  --muted: #a5b9b2;
  --line: #32443e;
  --accent: #42d3a1;
  --accent-strong: #2bb587;
  --accent-text: #04120d;
  --shadow: 0 18px 50px rgb(0 0 0 / 30%);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0e1513;
    --surface: #17201d;
    --text: #eff8f4;
    --muted: #a5b9b2;
    --line: #32443e;
    --accent: #42d3a1;
    --accent-strong: #2bb587;
    --accent-text: #04120d;
    --shadow: 0 18px 50px rgb(0 0 0 / 30%);
  }
}

* {
  box-sizing: border-box;
}

html {
  background: var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}

body {
  min-height: 100vh;
  margin: 0;
  background:
    radial-gradient(
      circle at 20% 0%,
      color-mix(in srgb, var(--accent) 12%, transparent),
      transparent 34rem
    ),
    var(--bg);
}

.topbar {
  min-height: 4.5rem;
  padding: 1rem clamp(1rem, 5vw, 4rem);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--surface) 88%, transparent);
}

.brand {
  color: var(--accent);
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  text-decoration: none;
}

.preferences {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.theme-control,
.language-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  font-size: 0.85rem;
  font-weight: 700;
}

.theme-control select,
.language-control select {
  width: auto;
}

.shell {
  width: min(72rem, calc(100% - 2rem));
  margin: clamp(2rem, 7vw, 6rem) auto;
}

.shell.narrow {
  width: min(46rem, calc(100% - 2rem));
}

.card {
  padding: clamp(1.4rem, 4vw, 2.6rem);
  border: 1px solid var(--line);
  border-radius: 1.25rem;
  background: var(--surface);
  box-shadow: var(--shadow);
}

.card h1 {
  margin: 0.25rem 0 1rem;
  font-size: clamp(2rem, 5vw, 3.6rem);
  letter-spacing: -0.055em;
  line-height: 1.02;
}

.eyebrow {
  margin: 0;
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.muted {
  color: var(--muted);
  line-height: 1.55;
}

form {
  margin-top: 1.75rem;
}

form label {
  display: block;
  margin: 1.2rem 0 0.45rem;
  font-weight: 700;
}

form label span {
  color: var(--muted);
  font-size: 0.86rem;
  font-weight: 500;
}

input,
select {
  width: 100%;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}

button {
  width: 100%;
  margin-top: 1.25rem;
  padding: 0.72rem 1rem;
  border: 1px solid transparent;
  border-radius: 0.7rem;
  background: var(--accent);
  color: var(--accent-text);
  cursor: pointer;
  font: inherit;
  font-weight: 750;
}

button:hover {
  background: var(--accent-strong);
}

button:focus-visible,
a:focus-visible,
input:focus-visible,
select:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--accent) 45%, transparent);
  outline-offset: 2px;
}

.footnote {
  margin: 1.25rem 0 0;
  font-size: 0.9rem;
}

@media (max-width: 760px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .preferences {
    align-items: flex-start;
    width: 100%;
  }
}
"""


def render_mobileconfig_script() -> str:
    """Return local-only persisted theme and language behavior."""
    return """(() => {
  const translations = {
    "de": {
      pageTitle: "Apple-Mail-Konfiguration · automx",
      language: "Sprache",
      appearance: "Darstellung",
      eyebrow: "Apple Mail",
      heading: "Konto konfigurieren",
      intro: "Gib die Mailadresse und optional den Anzeigenamen für dieses Gerät ein.",
      email: "Mailadresse",
      displayName: "Anzeigename",
      optional: "(optional)",
      button: "Konfigurationsprofil laden",
      footnote: "Das Gerät fragt beim ersten Verbindungsaufbau nach den Zugangsdaten.",
      auto: "Auto",
      light: "Hell",
      dark: "Dunkel"
    },
    "en": {
      pageTitle: "Apple Mail configuration · automx",
      language: "Language",
      appearance: "Appearance",
      eyebrow: "Apple Mail",
      heading: "Configure your account",
      intro: "Enter the mail address and optional display name for this device.",
      email: "Mail address",
      displayName: "Display name",
      optional: "(optional)",
      button: "Download configuration profile",
      footnote: "The device requests account credentials when it first connects.",
      auto: "Auto",
      light: "Light",
      dark: "Dark"
    }
  };

  const applyTheme = (theme) => {
    if (theme === "light" || theme === "dark") {
      document.documentElement.dataset.theme = theme;
    } else {
      delete document.documentElement.dataset.theme;
    }
    document.querySelectorAll("[data-theme-select]").forEach((select) => {
      select.value = theme;
    });
  };

  const applyLanguage = (language) => {
    if (!translations[language]) language = "en";
    const copy = translations[language];
    document.documentElement.lang = language;
    document.title = copy.pageTitle;
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = copy[element.dataset.i18n];
    });
    document.querySelectorAll("[data-language-select]").forEach((select) => {
      select.value = language;
      select.setAttribute("aria-label", copy.language);
    });
    document.querySelectorAll("[data-theme-select]").forEach((select) => {
      select.querySelector('option[value="auto"]').textContent = copy.auto;
      select.querySelector('option[value="light"]').textContent = copy.light;
      select.querySelector('option[value="dark"]').textContent = copy.dark;
    });
  };

  let theme = "auto";
  try {
    theme = localStorage.getItem("automx-theme") || "auto";
  } catch (_) {
    theme = "auto";
  }
  applyTheme(theme);

  let language;
  try {
    language = localStorage.getItem("automx-language");
  } catch (_) {
    language = null;
  }
  if (!translations[language]) {
    language = navigator.language.toLowerCase().startsWith("de") ? "de" : "en";
  }
  applyLanguage(language);

  document.querySelectorAll("[data-theme-select]").forEach((select) => {
    select.addEventListener("change", () => {
      const selected = select.value;
      try {
        localStorage.setItem("automx-theme", selected);
      } catch (_) {
        // The visual choice still applies when storage is unavailable.
      }
      applyTheme(selected);
    });
  });

  document.querySelectorAll("[data-language-select]").forEach((select) => {
    select.addEventListener("change", () => {
      const selected = select.value;
      try {
        localStorage.setItem("automx-language", selected);
      } catch (_) {
        // The language still applies when storage is unavailable.
      }
      applyLanguage(selected);
    });
  });
})();
"""
