"""One place that starts the browser used by the page audits.

Locally we drive the installed Chrome (it is what the reader sees). On a runner there is no
Chrome until one is installed, so the bundled Chromium is the fallback — the audits measure text,
paint order and contrast, none of which depend on the brand of the engine.
"""

from __future__ import annotations


def launch(playwright):
    """Return a browser: installed Chrome, else Playwright's Chromium, else a clear error."""
    try:
        return playwright.chromium.launch(channel="chrome")
    except Exception as chrome_error:                              # noqa: BLE001
        try:
            return playwright.chromium.launch()
        except Exception as chromium_error:                         # noqa: BLE001
            raise RuntimeError(
                "no browser for the page audit: install Chrome, or run "
                "`python -m playwright install chromium`\n"
                f"chrome: {type(chrome_error).__name__}; "
                f"chromium: {type(chromium_error).__name__}") from chromium_error
