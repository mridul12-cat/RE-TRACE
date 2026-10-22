# Dashboard localization boundary

The active dashboard is FastAPI-served HTML and vanilla JavaScript. English is the
initial default. Desktop and mobile headers offer native EN / TR selectors. The
`retrace.locale` localStorage value persists the explicit preference. Missing,
invalid, or blocked storage falls back safely; storage is not required to switch.

## Catalogs and bindings

- `dashboard-messages.js` contains the English catalog and the dependency-free
  runtime. `dashboard-tr.js` registers the Turkish catalog before DOMContentLoaded.
- Both catalogs currently contain 495 keys, with matching named placeholders.
- Static UI text uses `data-i18n`; accessible names, tooltips and placeholders use
  `data-i18n-label`, `data-i18n-title`, and `data-i18n-placeholder`.
- Use `REUI.set(node, key, values)` or pass `REUI.ref(key, values)` to
  `workflowNode` for dynamic UI. Bindings update in place on locale changes.
  `REUI.attribute` binds accessible names, including chart and copy descriptions.
- `REUI.raw(node, value)` removes prior UI bindings before displaying an API value.
  Plain text is never looked up automatically in a translation dictionary.
- A MutationObserver applies only explicit UI markers on newly inserted elements.
  It does not translate arbitrary text. Escape API/user strings inserted into
  legacy HTML templates; prefer textContent for new renderers.
- Locale changes update `document.documentElement.lang`, both selectors, and a
  polite live announcement. They do not send API requests, rerun scenarios, prefill
  material rows, or replace entered form values. Technical disclosures stay open.
- UI numbers use `Intl.NumberFormat` for `en-GB` / `tr-TR`. Numeric input values,
  calculation operands, API payloads, and raw JSON remain canonical. No translated
  string is parsed back into verification input. Computed displayed claim totals
  retain their existing two-decimal presentation.

## Deliberate untranslated content

API field names, enum codes, hashes, IDs, transaction references, units, filenames,
product/material/manufacturer names, provider/model names, user-entered content,
AI notes, anomaly codes, backend explanations and full technical JSON retain their
original values. Backend scenario titles/stage names also remain verbatim. Results
explain this source-language boundary in both languages. UI explanations are
translated; backend explanations are not fabricated or machine translated.

`LOCAL TESTNET · Chain 31337` remains unchanged in both languages. The selector
self-names `EN · English` and `TR · Türkçe` are intentionally bilingual.

## Checks

Run `node --test tests/test_dashboard_localization.cjs` for catalog parity,
placeholder preservation, persistence, storage failure, dynamic bindings, raw-data
isolation, accessibility labels, and numeric formatting. Run the existing complete
Python regression suite separately; backend tests and expectations are unchanged.
