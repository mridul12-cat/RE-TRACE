/* Technical audit presentation. Existing read-only endpoints and captured API responses only.
 * Session observations/findings are deliberately not reconstructed from storage or labels.
 */
const auditState = { files: new Map(), bundles: new Map(), ai: null, events: [], certificates: [], passports: [], pending: {}, certificateRequest: 0 };
const auditText = key => REUI.t(key);
function auditNode(tag, className, text) { return workflowNode(tag, className, text); }
function auditEmpty(host, key = 'audit.noRecords') { host.replaceChildren(auditNode('p', 'workflow-empty', REUI.ref(key))); }
function auditFacts(values) {
  const list = auditNode('dl', 'technical-facts');
  values.forEach(([key, value]) => {
    const row = document.createElement('div');
    row.append(auditNode('dt', '', REUI.ref(key)), auditNode('dd', '', value ?? REUI.ref('audit.unknown')));
    list.append(row);
  });
  return list;
}
function auditDetails(value, key = 'audit.technical') {
  const details = auditNode('details', 'technical-details');
  details.append(auditNode('summary', '', REUI.ref(key)), auditNode('pre', '', JSON.stringify(value, null, 2)));
  return details;
}
function auditHash(key, value) {
  const details = auditNode('details', 'technical-details technical-hash');
  details.append(auditNode('summary', '', REUI.ref(key)));
  if (typeof value !== 'string' || !value) { details.append(auditNode('p', 'workflow-muted', REUI.ref('audit.unknown'))); return details; }
  const code = auditNode('code', '', value);
  code.tabIndex = 0;
  const copy = auditNode('button', 'technical-button', REUI.ref('audit.copy'));
  copy.type = 'button';
  REUI.attribute(copy,'aria-label','audit.copyFor',{label:REUI.ref(key)});
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(value); REUI.set(copy,'audit.copied'); REUI.set(status,'audit.copied'); }
    catch { REUI.set(status,'audit.copyFailed'); code.focus(); }
  });
  const status = auditNode('span', 'workflow-muted');
  status.setAttribute('role', 'status');
  details.append(code, copy, status);
  return details;
}
async function auditRequest(path) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(path, {cache:'no-store', signal:controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const reason = data.message ?? data.error ?? data.detail ?? response.status;
      const error = new Error(typeof reason === 'string' ? reason : JSON.stringify(reason));
      error.response = data; throw error;
    }
    return data;
  } finally { clearTimeout(timer); }
}
function auditStatus(id, key, state, values = {}) {
  const node = document.getElementById(id);
  REUI.set(node,key,values); node.dataset.state = state;
}
async function auditLoad(kind, statusId, work) {
  if (auditState.pending[kind]) return auditState.pending[kind];
  const button = document.getElementById(`audit-refresh-${kind}`);
  if (button) button.disabled = true;
  auditStatus(statusId, 'audit.loading', 'pending');
  const operation = (async () => {
    try { await work(); auditStatus(statusId, 'audit.loaded', 'success'); }
    catch (error) { auditStatus(statusId, 'audit.failed', 'failed', {reason:error.message}); }
    finally { if (button) button.disabled = false; delete auditState.pending[kind]; }
  })();
  auditState.pending[kind] = operation;
  return operation;
}
function auditMergeFiles(files) {
  files.forEach(file => auditState.files.set(file.file_id, file));
  auditRenderFiles();
}
function auditRenderFiles() {
  const host = document.getElementById('evidence-audit-list');
  host.replaceChildren();
  document.getElementById('evidence-audit-count').textContent = String(auditState.files.size);
  if (!auditState.files.size) return auditEmpty(host);
  [...auditState.files.values()].forEach(file => {
    const card = auditNode('article', 'technical-record');
    const heading = auditNode('div', 'technical-panel-heading');
    heading.append(auditNode('h4', '', file.filename), auditNode('span', 'workflow-state', file.provenance ?? REUI.ref('audit.unknown')));
    card.append(heading, auditNode('p', 'technical-uploaded', REUI.ref('audit.uploaded')),
      auditFacts([['audit.fileId',file.file_id],['audit.fileType',file.mime_type],['audit.bytes',file.file_size_bytes]]),
      auditHash('audit.fileHash',file.sha256_hash), auditDetails(file));
    host.append(card);
  });
}
function auditRefreshEvidence() {
  return auditLoad('evidence','audit-evidence-status',async () => {
    const files = await auditRequest('/api/v1/evidence');
    if (!Array.isArray(files)) throw new Error(auditText('audit.unknown'));
    auditState.files = new Map(files.map(file => [file.file_id,file]));
    auditRenderFiles();
  });
}
function auditRenderAI() {
  const session = auditState.ai;
  const observation = session?.observation;
  let key = 'audit.noObservation';
  if (session && !observation) key = 'audit.unavailable';
  if (observation) key = observation.execution_mode === 'LIVE_GEMINI' ? 'audit.live' : observation.execution_mode === 'DETERMINISTIC_FIXTURE' ? 'audit.fixture' : 'audit.observed';
  if (session?.skipped) key = 'audit.skipped';
  if (session?.fallback && observation) key = 'audit.fallbackState';
  REUI.set(document.getElementById('ai-audit-mode-badge'),key);
  const values = {
    'ai-audit-requested': session?.requested,
    'ai-audit-mode': observation?.execution_mode,
    'ai-audit-model': [observation?.provider,observation?.model].filter(v => v != null).join(' / ') || null,
    'ai-audit-units': observation?.estimated_item_count,
    'ai-audit-conf': observation?.confidence,
    'ai-audit-prov': observation?.provenance_category ?? observation?.provenance,
    'ai-audit-evid': observation?.evidence_id,
    'ai-audit-sha': observation?.evidence_sha256,
    'ai-audit-anomalies': Array.isArray(observation?.anomaly_flags) ? (observation.anomaly_flags.length ? observation.anomaly_flags.join(', ') : REUI.ref('audit.noAnomalies')) : null,
    'ai-audit-fallback': session?.reason ?? session?.notice,
  };
  Object.entries(values).forEach(([id,value]) => {
    const node = document.getElementById(id);
    REUI.write(node,typeof value === 'number' ? REUI.ref('format.value',{value,suffix:''}) : value ?? '');
    node.parentElement.hidden = value == null;
  });
  const technical = document.getElementById('ai-audit-technical');
  technical.replaceChildren();
  if (session) {
    if (observation?.evidence_sha256) technical.append(auditHash('audit.fileHash',observation.evidence_sha256));
    technical.append(auditDetails(session));
  }
}
function auditRenderBundles() {
  const host = document.getElementById('audit-bundles'); host.replaceChildren();
  if (!auditState.bundles.size) return auditEmpty(host);
  auditState.bundles.forEach(bundle => {
    const card = auditNode('article','technical-record');
    card.append(auditFacts([['audit.event',bundle.event_id],['audit.passport',bundle.passport_id]]),
      auditHash('audit.manifest',bundle.canonical_manifest_sha256), auditHash('audit.keccak',bundle.bundle_keccak256_commitment), auditDetails(bundle));
    host.append(card);
  });
}
function auditRefreshLedger() {
  return auditLoad('ledger','audit-ledger-status',async () => {
    const [status,events,certificates] = await Promise.all(['/api/v1/blockchain/status','/api/v1/blockchain/events','/api/v1/blockchain/certificates'].map(auditRequest));
    if (!Array.isArray(events) || !Array.isArray(certificates)) throw new Error(auditText('audit.unknown'));
    auditState.events = events; auditState.certificates = certificates;
    auditRenderLedger();
    const node = document.getElementById('audit-ledger-status');
    node.dataset.reported = status.is_local_simulation === true ? (status.is_connected === true ? 'ledger.available' : 'ledger.offline') : 'ledger.reported';
  }).then(() => {
    const node = document.getElementById('audit-ledger-status');
    if (node.dataset.state === 'success') {
      REUI.set(node,node.dataset.reported);
      if (node.dataset.reported === 'ledger.offline') node.dataset.state = 'unavailable';
    }
  });
}
function auditRenderLedger() {
  const events = document.getElementById('audit-ledger-events'); events.replaceChildren();
  if (!auditState.events.length) auditEmpty(events);
  [...auditState.events].reverse().forEach(event => {
    const card = auditNode('article','technical-record');
    card.append(auditFacts([['audit.event',event.event_id],['audit.passport',event.passport_id],['ledger.block',event.block_number]]),auditHash('ledger.tx',event.tx_hash),auditHash('audit.keccak',event.evidence_commitment),auditDetails(event));
    events.append(card);
  });
  const latest = auditState.events[auditState.events.length - 1];
  REUI.write(document.getElementById('bc-view-tx'),latest?.tx_hash ?? REUI.ref('audit.unknown'));
  REUI.write(document.getElementById('bc-view-commitment'),latest?.evidence_commitment ?? REUI.ref('audit.unknown'));
  const certificates = document.getElementById('audit-certificate-list'); certificates.replaceChildren();
  if (!auditState.certificates.length) auditEmpty(certificates);
  [...auditState.certificates].reverse().forEach(cert => {
    const card = auditNode('article','technical-record');
    const open = auditNode('button','technical-button',REUI.ref('ledger.open')); open.type='button';
    REUI.attribute(open,'aria-label','ledger.openRecord',{id:cert.certificate_id});
    open.addEventListener('click',() => auditLookupCertificate(cert.certificate_id));
    card.append(auditNode('h4','',cert.certificate_id),auditFacts([['audit.passport',cert.passport_id],['audit.event',cert.event_id]]),auditHash('ledger.certHash',cert.certificate_hash),auditHash('audit.keccak',cert.evidence_commitment),open);
    certificates.append(card);
  });
}
function auditRenderCertificate(record) {
  REUI.write(document.getElementById('cert-id'),record.certificate_id ?? REUI.ref('audit.unknown'));
  REUI.write(document.getElementById('cert-commitment'),record.evidence_commitment ?? REUI.ref('audit.unknown'));
  REUI.write(document.getElementById('cert-tx'),record.blockchain_transaction_reference ?? record.tx_hash ?? REUI.ref('audit.unknown'));
  const host = document.getElementById('audit-cert-details'); host.replaceChildren();
  host.append(auditFacts([['audit.passport',record.passport_id],['audit.event',record.event_id],['ledger.facility',record.facility_id],['ledger.issued',record.issued_at]]),auditHash('ledger.certHash',record.certificate_hash),auditHash('audit.keccak',record.evidence_commitment),auditHash('ledger.tx',record.blockchain_transaction_reference ?? record.tx_hash));
  if (Array.isArray(record.verified_material_quantities)) {
    const region = auditNode('div','technical-table'); region.tabIndex=0;
    region.setAttribute('role','region');REUI.attribute(region,'aria-label','ledger.materials');
    const table = document.createElement('table');table.append(auditNode('caption','',REUI.ref('ledger.materials')));
    const head = document.createElement('thead'); const header = document.createElement('tr');
    ['ledger.material','ledger.mass','ledger.purity','ledger.yield'].forEach(key => { const cell=auditNode('th','',REUI.ref(key));cell.scope='col';header.append(cell); });head.append(header);table.append(head);
    const body = document.createElement('tbody');
    record.verified_material_quantities.forEach(material => { const row=document.createElement('tr');[material.material_name,material.recovered_mass_kg,material.purity_pct,material.recovery_yield_pct].forEach(value => row.append(auditNode('td','',value)));body.append(row); });
    table.append(body);region.append(table);host.append(region);
  }
  host.append(auditDetails(record));
}
async function auditLookupCertificate(id, verify = false) {
  const input = document.getElementById('bc-cert-input');
  const certId = (id ?? input.value).trim();
  if (!certId) { auditStatus('cert-auth-status','ledger.noId','unavailable'); input.focus(); return; }
  input.value = certId;
  const request = ++auditState.certificateRequest;
  const buttons = ['audit-cert-lookup','audit-cert-verify'].map(id => document.getElementById(id));
  buttons.forEach(button => {button.disabled=true;});
  auditStatus('cert-auth-status',verify ? 'ledger.verifying' : 'ledger.pending','pending');
  ['cert-id','cert-commitment','cert-tx'].forEach(id => {document.getElementById(id).textContent='—';});
  document.getElementById('audit-cert-details').replaceChildren();
  try {
    const record = await auditRequest(`/api/v1/certificates/${encodeURIComponent(certId)}`);
    if (request !== auditState.certificateRequest) return;
    auditRenderCertificate(record);
    if (verify) {
      const response = await auditRequest(`/api/v1/certificates/verify/${encodeURIComponent(certId)}`);
      if (request !== auditState.certificateRequest) return;
      if (response.status !== 'VALID_AND_AUTHENTICATED') throw new Error(auditText('audit.unknown'));
      auditStatus('cert-auth-status','ledger.verified','success',{status:response.status ?? auditText('audit.unknown')});
      document.getElementById('audit-cert-details').append(auditDetails(response,'ledger.verificationResponse'));
    } else auditStatus('cert-auth-status','ledger.recordLoaded','loaded');
  } catch (error) {
    if (request !== auditState.certificateRequest) return;
    auditStatus('cert-auth-status','ledger.failure','failed',{reason:error.message});
    if (error.response) document.getElementById('audit-cert-details').append(auditDetails(error.response));
  } finally { if (request === auditState.certificateRequest) buttons.forEach(button => {button.disabled=false;}); }
}
function auditRefreshInvestigations() {
  return auditLoad('investigations','audit-investigation-status',async () => {
    const passports = await auditRequest('/api/v1/blockchain/passports');
    if (!Array.isArray(passports)) throw new Error(auditText('audit.unknown'));
    auditState.passports=passports; auditRenderInvestigations();
  });
}
function auditRenderInvestigations() {
  [['investigation-flagged-list','investigation-flagged-count',_flaggedEvents],['investigation-tampered-list','investigation-tampered-count',_tamperedEvents]].forEach(([listId,countId,records]) => {
    const host = document.getElementById(listId);host.replaceChildren();document.getElementById(countId).textContent=String(records.length);
    if (!records.length) return auditEmpty(host,'investigation.noCases');
    records.forEach(record => {
      const current = auditState.passports.find(p => p.passport_id === record.passport_id);
      const card = auditNode('article','technical-record technical-finding');
      card.append(auditNode('p','workflow-muted',REUI.ref('audit.inSession')),auditFacts([['audit.event',record.event_id],['audit.passport',record.passport_id],['investigation.capturedState',record.state],['investigation.currentState',current?.state],['audit.certificateConsequence',record.certificate_consequence]]));
      if (record.reason) card.append(auditNode('h4','',REUI.ref('audit.reason')),auditNode('p','technical-reason',record.reason));
      if (record.original_file_sha256) card.append(auditHash('audit.originalHash',record.original_file_sha256));
      if (record.tampered_sha256) card.append(auditHash('audit.changedHash',record.tampered_sha256));
      if (record.expected) card.append(auditHash('audit.keccak',record.expected));
      card.append(auditDetails(record));host.append(card);
    });
  });
  const host=document.getElementById('audit-quarantined-passports');host.replaceChildren();
  const flagged=auditState.passports.filter(p => p.state === 'FLAGGED');
  if (!flagged.length) return auditEmpty(host);
  flagged.forEach(p => {const card=auditNode('article','technical-record');card.append(auditFacts([['audit.passport',p.passport_id],['audit.state',p.state]]),auditNode('p','workflow-muted',REUI.ref('investigation.quarantinePolicy')),auditDetails(p));host.append(card);});
}
function auditAdoptCertificate(record) {
  // A newly issued record must not inherit the status of an older in-flight lookup.
  auditState.certificateRequest++;
  document.getElementById('bc-cert-input').value = record.certificate_id;
  ['audit-cert-lookup','audit-cert-verify'].forEach(id => { document.getElementById(id).disabled = false; });
  auditRenderCertificate(record);
  auditStatus('cert-auth-status','ledger.recordLoaded','loaded');
}
function auditCaptureVerification(data, request) {
  if (data.certificate) auditAdoptCertificate(data.certificate);
  const bundle = data.evidence_bundle;
  if (bundle) auditState.bundles.set(data.event_id,{...bundle,event_id:data.event_id,passport_id:data.passport_id});
  auditState.ai = {requested:data.ai_requested_mode ?? (request.run_ai_observation ? request.ai_force_mode : null), observation:data.ai_observation, fallback:data.ai_fallback_occurred, reason:data.ai_fallback_reason, notice:data.ai_notice, skipped:!request.run_ai_observation && !data.ai_observation};
  auditRenderAI();auditRenderBundles();
  const record={event_id:data.event_id,passport_id:data.passport_id,state:data.lifecycle_state,reason:data.concise_explanation ?? data.mathematical_explanation,certificate_consequence:data.certificate_block_reason,expected:bundle?.bundle_keccak256_commitment,verification_response:data};
  if (data.mass_balance_decision === 'IMPOSSIBLE') addInvestigationFlaggedRecord(record);
  if (data.evidence_integrity_status === 'BREACHED') addInvestigationTamperedRecord({...record,reason:data.evidence_integrity_message});
}
async function auditCaptureScenario(data) {
  const stages=data.stages ?? [];
  if (data.scenario === 'A') {
    if (data.certificate) auditAdoptCertificate(data.certificate);
    const anchor=stages.find(stage => stage.canonical_sha256);
    if (anchor) auditState.bundles.set(data.certificate?.event_id ?? anchor.tx_hash,{event_id:data.certificate?.event_id,passport_id:data.certificate?.passport_id,canonical_manifest_sha256:anchor.canonical_sha256,bundle_keccak256_commitment:anchor.keccak256_commitment});
    const observation=stages.find(stage => stage.detected_units != null);
    if (observation) auditState.ai={observation:{estimated_item_count:observation.detected_units,confidence:observation.confidence,anomaly_flags:observation.anomaly_flags,provenance_category:observation.provenance}};
    auditRenderAI();auditRenderBundles();
  }
  if (data.scenario === 'B') {
    const product=stages.find(stage => stage.passport_id);
    const state=stages.find(stage => stage.lifecycle_state);
    addInvestigationFlaggedRecord({passport_id:product?.passport_id,state:state?.lifecycle_state,reason:data.mathematical_proof,certificate_consequence:state?.certificate_issuance,stages});
  }
  // Refresh read-only indexes without changing demo success/failure behavior.
  await Promise.all([auditRefreshEvidence(),auditRefreshLedger(),auditRefreshInvestigations()]);
  if (data.scenario === 'C') {
    const original=stages.find(stage => stage.original_file_sha256);
    const changed=stages.find(stage => stage.tampered_sha256);
    const failure=stages.find(stage => stage.error_flag);
    const event=auditState.events.find(event => event.tx_hash === original?.tx_hash);
    addInvestigationTamperedRecord({event_id:event?.event_id,passport_id:event?.passport_id,state:failure?.lifecycle_state,reason:failure?.message,original_file_sha256:original?.original_file_sha256,tampered_sha256:changed?.tampered_sha256,expected:original?.anchored_keccak256_commitment,stages});
    if (original) auditState.bundles.set(event?.event_id ?? original.tx_hash,{event_id:event?.event_id,passport_id:event?.passport_id,bundle_keccak256_commitment:original.anchored_keccak256_commitment});
    auditRenderBundles();
  }
}
function auditViewEntered(view) {
  if (view === 'evidence') auditRefreshEvidence();
  if (view === 'blockchain') auditRefreshLedger();
  if (view === 'investigation') auditRefreshInvestigations();
}
document.addEventListener('DOMContentLoaded',() => {auditRenderFiles();auditRenderAI();auditRenderBundles();auditRenderLedger();auditRenderInvestigations();});
// Locale changes update bound UI labels in place, preserving expanded evidence and certificate details.

