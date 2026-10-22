# Phase 5 UI audit

## Scenario B: what the three numbers mean

No backend service, API contract, verification formula, fixture or existing test
expectation was changed.

Sources:

- `backend/app/api/v1/demo.py`, Scenario B: batch intake 1,000 kg; the submitted
  `ClaimedMaterial` for Cobalt is 95 kg. The returned `claimed_cobalt_kg` is also
  the literal 95.0. Returned ceiling fields are literals of 60.3 for this fixture.
- `shared/fixtures/reference_materials.py`, EV NMC622 composition: cobalt is 6%
  of intake, nominal BAT recovery is 93% (7% expected loss), material tolerance
  is 5%. The passport's nominal module mass is 25 kg; the recycling event is a
  separate 1,000 kg batch, so 25 kg is not the intake used in these calculations.
- `backend/app/services/mass_balance_service.py` delegates to
  `shared/domain/mass_balance.py` without changing the operands. The demo passes
  `scale_uncertainty_pct=0.5`.

| Quantity | Calculation | Meaning |
| --- | --- | --- |
| 95 kg | Submitted recovery claim | Claimed cobalt output |
| 60 kg | 1,000 × 0.06 | Physical cobalt content at 100% recovery, before scale uncertainty |
| 60.3 kg | 60 × (1 + 0.005) | Absolute stoichiometric ceiling including scale uncertainty |
| 55.8 kg | 1,000 × 0.06 × 0.93 | Expected nominal BAT recovery |
| 39.2 kg | 95 − 55.8 | Deviation above nominal recovery |
| 34.7 kg | 95 − 60.3 | Excess above the physical ceiling; this is an audit calculation, not a returned field |

The normal nominal envelope is 53.01–58.59 kg (55.8 ± 5%). The upper borderline
bound is clamped to min(55.8 × 1.10, 60.3) = 60.3 kg. The 95 kg claim exceeds the
absolute ceiling and the clamped upper threshold. The domain verifier computes
`dev = m_claim - m_exp`; the demo's literal `95.0 - 55.8` agrees with that
nominal-baseline deviation. The difference is a different baseline, not an extra
tolerance adjustment.

The raw mathematical explanation says the claim exceeds a ceiling/threshold
“by” the nominal deviation, which is ambiguous wording. It remains an original
backend response. The UI now labels `discrepancy_kg` as **Deviation from nominal
recovery (kg)** and explicitly says it is not the excess above the displayed
ceiling. Both language catalogs explain this. Charts still use only returned
95 and 60.3 kg values; no tolerance band is invented. No 34.7 kg quantity is added
to application results. Future changes to the endpoint literals or backend
explanation need separate approval and corresponding backend tests.

## CDN dependency assessment

The active dashboard loads:

- `https://cdn.tailwindcss.com`: runtime utility generation, unversioned URL.
- Font Awesome 6.4.0 CSS from cdnjs, plus the font files it references.

No matching local assets or build pipeline exist for this FastAPI dashboard.
The optional Next.js frontend's Tailwind configuration is not the active dashboard.
There was no framework migration, package installation, or CDN replacement in
Phase 5. These existing resources loaded in preview tests. Tailwind emits its
existing production-use warning.

Recommendation: separately approve a version-pinned, reproducible local asset
bundle before claiming offline or production reliability. Compile the existing
utility CSS with an inventory/safelist covering classes generated in JavaScript;
self-host the required Font Awesome assets with license notices, or evaluate an
explicit icon subset. Compare all seven populated views across breakpoints and
languages before swapping URLs. A large CSS rewrite is unnecessary for this UI
release. Keeping the current dependencies in this phase avoids an unrelated asset
migration; network access remains a documented presentation prerequisite.

## Release boundary

This is a local hackathon/presentation UI. The ledger remains accurately labeled
`LOCAL TESTNET · Chain 31337`, with a local-simulation disclosure. This is not a
public-chain settlement or regulatory-certification claim. Live Gemini requires
configured credentials/network access; deterministic scenario fixtures remain
explicitly labeled. Backend prose stays in its original language by design.

## Final verification results

Executed against the FastAPI dashboard on the `ui-redesign` branch, with preview
uploads isolated under `/tmp/retrace-phase5`:

- Complete existing Python suite: **145 passed, 0 failed, 1 skipped**. The optional
  live Gemini test skipped because `GEMINI_API_KEY` was not configured. Two existing
  pytest import-rewrite warnings remained. Existing Python tests were unchanged.
- Localization boundary tests (`node --test tests/test_dashboard_localization.cjs`):
  **13 passed, 0 failed**.
- Targeted demo and audit presentation regressions: **21 + 16 passed**, including
  overlapping-request prevention, pending/error cleanup, raw outcome preservation,
  certificate lookup/verification separation, and full-value copy behavior.
- Live API checks: **15 passed**. Eight downloaded evidence files matched their
  returned SHA-256 records. Successful uploads retained all five provenance
  categories; an invalid signature was rejected. Scenario C restored original
  bytes after completion. Unknown certificate operations retained 404/422 behavior.
- All three scenarios ran in both EN and TR: A `VERIFIED`, B `CLAIM FLAGGED`, C
  `EVIDENCE_INTEGRITY_FAILURE`. Scenario A certificates passed independent checks.
- **70** baseline layout checks covered seven views × two languages × five widths
  (320, 390, 768, 1274, 1440 px). **55** additional populated passport, workbench,
  and scenario layout checks found no horizontal page overflow.
- Both header selectors, native keyboard menu selection, EN/TR refresh persistence,
  Turkish characters, and 45 unchanged form values were checked. Dynamic validation,
  result labels, copy feedback and accessible names changed language in place.
- Real file upload and custom verification were exercised. The workbench verified
  with deterministic AI and with AI disabled. Completed/flagged passports stayed
  ineligible after cleanup; the normal lifecycle action reached RECYCLING_PENDING.
- No browser-console errors, duplicate DOM IDs, missing visible workbench form
  labels, or missing local frontend assets were found. Seven local assets returned
  HTTP 200. The existing Tailwind production-use warning remained.
- JavaScript syntax checks and `git diff --check` passed. Reduced-motion navigation
  and focus management were checked in the localization tests; keyboard operation
  and accessibility-tree labels were inspected in the in-app browser.

Assessment: **PASS for the local hackathon UI**. Offline/production readiness is
conditional on the dependency recommendation above. Full physical screen-reader
and cross-browser certification was not performed. Original-language backend prose
is an intentional localization boundary. No backend changes, commits, pushes,
merges, or deployments were made.
