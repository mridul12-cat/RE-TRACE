/* Phase 2 presentation helpers. No API requests or verification decisions here. */
let lastVerificationPresentation = null;
function workflowNode(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) {
    if (text?.__reUIMessage) REUI.write(el,text);
    else if (typeof text === 'number') REUI.set(el,'format.value',{value:text,suffix:''});
    else el.textContent = text;
  }
  return el;
}

function renderPassportList(passports, selectedId) {
  const container = document.getElementById('passports-list-container');
  const query = document.getElementById('passports-search-input').value.trim().toLocaleLowerCase(REUI.getLocale());
  const filter = document.getElementById('passports-filter-select').value;
  const focusedId = container.contains(document.activeElement) ? document.activeElement.dataset.passportId : null;
  const matches = passports.filter(p => (filter === 'ALL' || p.current_lifecycle_state === filter) &&
    [p.passport_id, p.product_name, p.manufacturer].some(value => String(value ?? '').toLocaleLowerCase(REUI.getLocale()).includes(query)));
  container.replaceChildren();
  document.getElementById('dpp-list-count').textContent = REUI.t('passport.count', {shown: matches.length, total: passports.length});
  if (!matches.length) container.append(workflowNode('p', 'workflow-empty', REUI.ref(passports.length ? 'passport.noMatches' : 'passport.noData')));
  matches.forEach(p => {
    const state = p.current_lifecycle_state ?? REUI.t('common.unavailable');
    const button = workflowNode('button', 'passport-choice');
    button.type = 'button';
    button.dataset.passportId = p.passport_id;
    button.setAttribute('aria-pressed', String(p.passport_id === selectedId));
    button.setAttribute('aria-controls', 'dpp-inspector-card');
    button.append(workflowNode('span', 'passport-choice-id', p.passport_id),
      workflowNode('strong', 'passport-choice-name', p.product_name),
      workflowNode('span', 'passport-choice-meta', p.manufacturer),
      workflowNode('span', `workflow-state ${state === 'FLAGGED' ? 'is-blocked' : ''}`, state),
      workflowNode('span', 'passport-choice-meta', `${REUI.number(p.initial_total_mass_kg)} kg · ${p.product_category}`));
    button.addEventListener('click', () => dppSelectPassport(p.passport_id));
    container.append(button);
    if (focusedId === p.passport_id) button.focus({preventScroll: true});
  });
}

function renderPassportInspector(passport) {
  document.getElementById('dpp-inspector-card').classList.toggle('hidden', !passport);
  document.getElementById('dpp-inspector-empty').classList.toggle('hidden', Boolean(passport));
  if (!passport) return;
  const p = passport;
  const state = p.current_lifecycle_state ?? REUI.t('common.unavailable');
  for (const [id, value] of Object.entries({
    'dpp-insp-id': p.passport_id, 'dpp-insp-name': p.product_name, 'dpp-insp-sku': p.product_id,
    'dpp-insp-cat': p.product_category, 'dpp-insp-mfg': p.manufacturer,
    'dpp-insp-mass': `${REUI.number(p.initial_total_mass_kg)} kg`, 'dpp-insp-state-badge': state,
  })) document.getElementById(id).textContent = value ?? REUI.t('common.unavailable');
  document.getElementById('dpp-insp-state-badge').className = `workflow-state ${state === 'FLAGGED' ? 'is-blocked' : ''}`;
  const map = {manufactured:'MANUFACTURED', 'in-use':'IN_USE', returned:'RETURNED', pending:'RECYCLING_PENDING', verified:'RECYCLING_VERIFIED', recovered:'MATERIALS_RECOVERED'};
  Object.entries(map).forEach(([id, value]) => {
    const node = document.getElementById(`state-node-${id}`);
    node.className = 'lifecycle-node';
    if (value === state) node.setAttribute('aria-current', 'step');
    else node.removeAttribute('aria-current');
  });
  const flag = document.getElementById('dpp-flagged-indicator');
  flag.textContent = REUI.t(state === 'FLAGGED' ? 'passport.quarantined' : 'passport.notFlagged');
  flag.className = `workflow-state ${state === 'FLAGGED' ? 'is-blocked' : ''}`;
  const tbody = document.getElementById('dpp-insp-bom-tbody');
  tbody.replaceChildren();
  (p.material_composition?.components ?? []).forEach(c => {
    const row = document.createElement('tr');
    // Preserve source precision for material quantities and percentages.
    [c.material_name, `${REUI.number(c.mass_kg)} kg`, `${REUI.number(c.percentage)}%`, `${REUI.number(100 - c.expected_yield_loss_pct)}%`,
      c.provenance ?? REUI.t('common.unavailable'), REUI.t(c.is_critical_raw_material ? 'common.yes' : 'common.no')]
      .forEach(value => row.append(workflowNode('td', '', value)));
    tbody.append(row);
  });
}

function updateVerificationReview() {
  const selected = document.querySelector('#cv-passport-select option:checked');
  const mass = document.getElementById('cv-intake-mass').value;
  const rows = [...document.querySelectorAll('#cv-materials-tbody tr')];
  const claims = rows.filter(row => row.querySelector('.cv-mat-name')?.value.trim() && row.querySelector('.cv-mat-mass')?.value !== '');
  const values = {
    'review-product': selected?.value ? selected.textContent : REUI.t('passport.empty'),
    'review-intake': mass ? `${REUI.number(Number(mass))} kg` : REUI.t('common.unavailable'),
    'review-files': REUI.t('review.files', {count: _cvUploadedFiles.length}),
    'review-claims': REUI.t('review.claimCount', {mass: [...document.querySelectorAll('.cv-mat-mass')].reduce((sum,input) => sum+(Number(input.value)||0),0), count: claims.length}),
    'review-ai': document.getElementById('cv-ai-toggle').checked ? document.getElementById('cv-ai-force-mode').value : REUI.t('review.off'),
  };
  Object.entries(values).forEach(([id,value]) => { document.getElementById(id).textContent = value; });
}

function renderMaterialComparisons(data) {
  lastVerificationPresentation = data;
  const host = document.getElementById('cv-material-comparisons');
  host.replaceChildren();
  const claims = data.claims_breakdown ?? [];
  if (!claims.length) host.append(workflowNode('p', 'workflow-muted', REUI.ref('result.noClaims')));
  claims.forEach(c => {
    const card = workflowNode('div', 'material-comparison');
    const heading = workflowNode('div', 'comparison-heading');
    heading.append(workflowNode('strong', '', c.material_name), workflowNode('span', 'workflow-state', c.status));
    card.append(heading);
    const band = c.tolerance_band;
    const supported = Number.isFinite(c.claimed_mass_kg) && Number.isFinite(c.expected_kg) &&
      Array.isArray(band) && band.length === 2 && band.every(Number.isFinite) && band[0] >= 0 && band[1] >= band[0] && c.expected_kg >= 0 && c.claimed_mass_kg >= 0;
    if (supported) {
      // A shared scale within this material; no inferred ceilings or tolerance values.
      const max = Math.max(c.claimed_mass_kg, c.expected_kg, band[1]);
      const position = value => max > 0 ? value / max * 100 : 0;
      const plot = workflowNode('div', 'comparison-plot');
      plot.setAttribute('role', 'img');
      plot.setAttribute('aria-label', REUI.t('result.chartLabel', {material:c.material_name,claim:c.claimed_mass_kg,expected:c.expected_kg,low:band[0],high:band[1]}));
      const range = workflowNode('span', 'comparison-band');
      range.style.left = `${position(band[0])}%`;
      range.style.width = `${position(band[1]) - position(band[0])}%`;
      const expected = workflowNode('span', 'comparison-expected');
      expected.style.left = `${position(c.expected_kg)}%`;
      const claim = workflowNode('span', 'comparison-claim');
      claim.style.left = `${position(c.claimed_mass_kg)}%`;
      plot.append(range,expected,claim);
      const legend = workflowNode('dl', 'comparison-values');
      for (const [key,value] of [['result.claim',`${REUI.number(c.claimed_mass_kg)} kg`],['result.expected',`${REUI.number(c.expected_kg)} kg`],['result.band',`${REUI.number(band[0])}–${REUI.number(band[1])} kg`]]) {
        const item = document.createElement('div');
        item.append(workflowNode('dt','',REUI.ref(key)), workflowNode('dd','',value));
        legend.append(item);
      }
      card.append(plot,legend);
    } else {
      card.append(workflowNode('p','workflow-muted', REUI.ref('result.noComparison')));
    }
    if (c.reason) card.append(workflowNode('p','workflow-muted',c.reason));
    host.append(card);
  });
  const result = document.getElementById('cv-result-container');
  result.dataset.verdict = data.overall_decision;
  document.getElementById('cv-result-announcement').textContent = REUI.t('result.status', {verdict:data.overall_decision,mass:data.mass_balance_decision,integrity:data.evidence_integrity_status});
  // Full digests remain selectable, without prefixing or truncating source data.
  const full = {
    'cv-res-manifest-hash': data.evidence_bundle?.canonical_manifest_sha256,
    'cv-res-commitment-hash': data.evidence_bundle?.bundle_keccak256_commitment,
    'cv-res-blockchain-tx': data.blockchain?.tx_hash,
    'cv-res-cert-hash': data.certificate?.certificate_hash,
  };
  Object.entries(full).forEach(([id,value]) => { if (value) document.getElementById(id).textContent = value; });
}

document.addEventListener('DOMContentLoaded', () => {
  const view = document.getElementById('view-verification');
  view.addEventListener('input', updateVerificationReview);
  view.addEventListener('change', updateVerificationReview);
  view.querySelectorAll('i').forEach(icon => icon.setAttribute('aria-hidden', 'true'));
  view.querySelectorAll('th').forEach(th => th.setAttribute('scope','col'));
  document.querySelectorAll('#view-passports .overflow-x-auto, #view-verification .overflow-x-auto').forEach(region => {
    region.setAttribute('tabindex', '0');
  });
  const labels = {'cv-passport-select':'step.product','cv-evidence-files':'field.files','cv-ai-toggle':'field.ai','cv-custom-event-id':'field.event'};
  Object.entries(labels).forEach(([id,key]) => {
    document.getElementById(id).dataset.i18nLabel = key;
  });
  REUI.apply(view);
  updateVerificationReview();
});
document.addEventListener('retrace:localechange', () => {
  dppRenderList(); dppRenderInspector(); updateVerificationReview();
  cvRecalculateClaimedTotal();
  if (lastVerificationPresentation) renderMaterialComparisons(lastVerificationPresentation);
});
