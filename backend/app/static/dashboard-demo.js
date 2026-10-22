/* Demo presentation: one mutating request at a time, completed API stages only.
 * Scenario configuration is labelled separately from returned evidence/results.
 * No verification rules, API enums, quantities, or tolerances are inferred here.
 */
window.REDemo = (() => {
  let busy = false;
  const el = id => document.getElementById(id);
  const text = (key, values) => REUI.t(key, values);
  const node = (tag, cls, value) => workflowNode(tag, cls, value);
  const controls = () => [...document.querySelectorAll('[data-demo-control], [onclick="cvResetDemoPassports()"]')];
  function lock() {
    busy = true;
    const previous = controls().map(button => [button, button.disabled]);
    previous.forEach(([button]) => { button.disabled = true; });
    return () => { previous.forEach(([button, disabled]) => { button.disabled = disabled; }); busy = false; };
  }
  function announce(key, state, values) {
    REUI.set(el('demo-status'),key,values);
    el('demo-status').dataset.state = state;
  }
  function clearOutput() {
    ['scenario-summary','scenario-stages','scenario-math','scenario-technical'].forEach(id => el(id).replaceChildren());
    el('scenario-math').classList.add('hidden');
    el('scenario-sequence-heading').classList.add('hidden');
    el('scenario-output').classList.remove('hidden');
    el('scenario-verdict').className = 'workflow-state';
    REUI.raw(el('scenario-verdict'),'');
    el('scenario-verdict').removeAttribute('data-outcome');
    REUI.set(el('demo-outcome-label'),'demo.execution');
  }
  function uiError(key,values) {const error=new Error(text(key,values));error.uiMessage=REUI.ref(key,values);return error;}
  async function post(path, body) {
    // No automatic retry: an interrupted mutating request may already have created records.
    const response = await fetch(path, {method:'POST', ...(body ? {headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
    let data;
    try { data = await response.json(); }
    catch { throw uiError('demo.httpError',{status:response.status}); }
    if (!response.ok) {
      const error = typeof data.detail === 'string' ? new Error(data.detail) : uiError('demo.httpError',{status:response.status});
      error.response = data; throw error;
    }
    return data;
  }
  function addFacts(host, stage, fields) {
    const supplied = fields.filter(([field]) => stage[field] != null).map(([field,key]) => [key, typeof stage[field] === 'object' ? JSON.stringify(stage[field]) : stage[field]]);
    if (supplied.length) host.append(auditFacts(supplied));
  }
  function addHashes(host, data) {
    [['file_id','audit.fileId'],['passport_id','audit.passport'],['event_id','audit.event'],['certificate_id','ledger.certificateId'],
      ['sha256','audit.fileHash'],['original_file_sha256','audit.originalHash'],['tampered_sha256','audit.changedHash'],
      ['canonical_sha256','audit.manifest'],['keccak256_commitment','audit.keccak'],['anchored_keccak256_commitment','audit.keccak'],
      ['evidence_commitment','audit.keccak'],['cert_hash','ledger.certHash'],['certificate_hash','ledger.certHash'],
      ['tx_hash','ledger.tx'],['blockchain_transaction_reference','ledger.tx']].forEach(([field,key]) => {
        if (typeof data[field] === 'string' && data[field]) host.append(auditHash(key,data[field]));
      });
  }
  function renderComparison(host, stages) {
    const comparison = stages.find(stage => Number.isFinite(stage.claimed_cobalt_kg) && Number.isFinite(stage.stoichiometric_ceiling_kg));
    if (!comparison) return;
    const claim = comparison.claimed_cobalt_kg, ceiling = comparison.stoichiometric_ceiling_kg;
    const card = node('section','demo-comparison'); card.append(node('h4','',REUI.ref('demo.comparison')));
    const chart = node('div','demo-chart'); chart.setAttribute('role','img');
    REUI.attribute(chart,'aria-label','demo.chartLabel',{claim,ceiling});
    const scale = Math.max(claim,ceiling,1);
    [['demo.claimed',claim,'claim'],['demo.ceiling',ceiling,'ceiling']].forEach(([key,value,cls]) => {
      const row = node('div','demo-bar-row');
      row.append(node('span','',REUI.ref(key)),node('strong','',value));
      const track=node('div','demo-bar-track'), bar=node('span',`demo-bar demo-bar-${cls}`);
      bar.style.width=`${Math.max(0,value)/scale*100}%`; track.append(bar); row.append(track); chart.append(row);
    });
    card.append(chart,node('p','workflow-muted',REUI.ref('demo.chartHelp')));
    if (claim > ceiling) card.append(node('p','demo-explanation',REUI.ref('demo.bWhy')));
    if (Number.isFinite(comparison.discrepancy_kg)) card.append(auditFacts([['demo.nominalDeviation',comparison.discrepancy_kg]]),node('p','workflow-muted',REUI.ref('demo.discrepancyHelp')));
    host.append(card);
  }
  function renderCertificate(host, certificate, stages) {
    const card=node('section','technical-record'); card.append(node('h4','',REUI.ref('demo.materials')));
    card.append(node('p','workflow-muted',REUI.ref('demo.materialHelp')));
    addHashes(card,certificate);
    const list=node('dl','demo-materials');
    (certificate.verified_material_quantities ?? []).forEach(material => {
      const row=node('div','');row.append(node('dt','',material.material_name),node('dd','',material.recovered_mass_kg == null ? REUI.ref('audit.unknown') : REUI.ref('format.kg',{value:material.recovered_mass_kg})));list.append(row);
    });
    card.append(list);
    const independent=stages.find(stage => typeof stage.verification_status === 'string');
    if (independent) card.append(auditFacts([['demo.independent',independent.verification_status]]));
    if (certificate.certificate_id) {
      const verify=node('button','technical-button',REUI.ref('demo.verifyAgain')); verify.type='button';
      verify.dataset.demoControl=''; verify.disabled=busy;
      verify.addEventListener('click',() => { if (!busy) cvVerifyCertificateLive(certificate.certificate_id); });
      card.append(verify);
    }
    host.append(card);
  }
  function render(data) {
    const stages=data.stages;
    el('scenario-summary').append(node('p','workflow-muted',REUI.ref('common.apiText')));
    REUI.set(el('demo-outcome-label'),'demo.actual');
    REUI.raw(el('scenario-title'),data.title);
    REUI.raw(el('scenario-verdict'),data.verdict);
    el('scenario-verdict').dataset.outcome = data.verdict === 'VERIFIED' ? 'verified' : ['CLAIM FLAGGED','EVIDENCE_INTEGRITY_FAILURE'].includes(data.verdict) ? 'blocked' : 'other';
    const summary=el('scenario-summary');
    const reason=stages.find(stage => stage.explanation)?.explanation;
    if (reason) summary.append(node('h4','',REUI.ref('demo.why')),node('p','demo-explanation',reason));
    if (data.scenario === 'A') summary.append(node('p','demo-fixture',REUI.ref('demo.fixture')),node('p','workflow-muted',REUI.ref('review.disclaimer')));
    renderComparison(summary,stages);
    const state=stages.findLast(stage => stage.lifecycle_state != null || stage.new_state != null);
    const decision=stages.find(stage => stage.decision != null);
    const consequence=stages.find(stage => stage.certificate_issuance != null);
    const intake=stages.find(stage => stage.intake_gross_mass_kg != null);
    const facts=[];
    if (decision) facts.push(['demo.decision',decision.decision]);
    if (intake) facts.push(['demo.intake',intake.intake_gross_mass_kg]);
    if (state) facts.push(['demo.state',state.lifecycle_state ?? state.new_state]);
    if (consequence) facts.push(['audit.certificateConsequence',consequence.certificate_issuance]);
    if (facts.length) summary.append(auditFacts(facts));
    if (data.scenario === 'C') {
      const original=stages.find(stage => stage.original_file_sha256), modified=stages.find(stage => stage.tampered_sha256);
      if (original && modified) {
        if (original.original_file_sha256 !== modified.tampered_sha256) summary.append(node('p','demo-explanation',REUI.ref('demo.cWhy')));
        summary.append(auditHash('audit.originalHash',original.original_file_sha256),auditHash('audit.changedHash',modified.tampered_sha256));
      }
      summary.append(node('p','workflow-muted',REUI.ref('demo.temporary')));
    }
    if (data.certificate) renderCertificate(summary,data.certificate,stages);
    if (data.mathematical_proof) {
      el('scenario-math').classList.remove('hidden');
      el('scenario-math').append(auditDetails(data.mathematical_proof,'demo.proof'));
    }
    el('scenario-sequence-heading').classList.remove('hidden');
    stages.forEach(stage => {
      const card=node('li','demo-stage');
      const heading=node('div','technical-panel-heading');
      const number=node('span','demo-stage-number',REUI.ref('demo.stage',{stage:stage.stage}));
      const status=node('span','workflow-state',stage.status);
      if (['FRAUD_DETECTED','TAMPERING_DETECTED','FAILED'].includes(stage.status)) status.classList.add('is-blocked');
      heading.append(number,status);card.append(heading,node('h4','',stage.name));
      if (typeof stage.details === 'string') card.append(node('p','demo-explanation',stage.details));
      if (stage.message) card.append(node('p','demo-explanation',stage.message));
      if (stage.detected_units != null) card.append(node('p','demo-fixture',REUI.ref('demo.fixture')));
      addFacts(card,stage,[['current_state','demo.state'],['new_state','demo.state'],['lifecycle_state','demo.state'],['decision','demo.decision'],['is_valid','demo.valid'],['conservation_valid','demo.conservation'],['provenance','demo.provenance'],['detected_units','audit.units'],['confidence','audit.confidence'],['anomaly_flags','demo.anomalies'],['certificate_issuance','audit.certificateConsequence'],['verification_status','demo.independent'],['resolution_rule','demo.notes'],['quarantine_resolution_rule','demo.notes']]);
      addHashes(card,stage);card.append(auditDetails(stage));el('scenario-stages').append(card);
    });
    el('scenario-technical').append(auditDetails(data,'demo.response'));
  }
  function showError(error) {
    clearOutput();
    REUI.set(el('scenario-title'),'demo.error');
    REUI.set(el('scenario-verdict'),'demo.error');
    el('scenario-verdict').classList.add('is-blocked');
    const alert=node('div','demo-error');alert.setAttribute('role','alert');
    alert.append(node('p','',error.uiMessage ?? error.message),node('p','workflow-muted',REUI.ref('demo.errorHelp')));
    if (error.response) alert.append(auditDetails(error.response));
    el('scenario-summary').append(alert);
  }
  async function run(scenario) {
    if (busy || !['A','B','C'].includes(scenario)) return;
    const trigger=el(`btn-scenario-${scenario.toLowerCase()}`);
    const unlock=lock(); clearOutput();el('scenario-output').setAttribute('aria-busy','true');
    REUI.set(el('scenario-title'),'demo.running',{scenario});
    REUI.set(el('scenario-verdict'),'demo.processing');
    announce('demo.running','pending',{scenario});
    try {
      const data=await post('/api/v1/demo/run-scenario',{scenario});
      if (data.scenario !== scenario || !Array.isArray(data.stages) || !data.stages.length || typeof data.title !== 'string' || typeof data.verdict !== 'string') throw uiError('demo.invalidResponse');
      render(data);
      announce('demo.completed','success',{scenario,verdict:data.verdict});
      // Preserve integration with evidence, certificate, ledger and investigation views.
      // A refresh problem must not replace the actual completed scenario with a request error.
      try { await auditCaptureScenario(data); await cvLoadPassports(); }
      catch { el('scenario-summary').append(node('p','workflow-muted',REUI.ref('demo.refreshFailed'))); }
    } catch (error) { showError(error); announce('demo.errorStatus','failed'); }
    finally {
      el('scenario-output').setAttribute('aria-busy','false');unlock();
      el('scenario-output').querySelectorAll('[data-demo-control]').forEach(button => {button.disabled=false;});
      if (!el('view-demo').classList.contains('hidden') && [document.body,trigger].includes(document.activeElement)) el('scenario-title').focus();
    }
  }
  async function reset() {
    if (busy) return;
    const trigger=document.activeElement;
    const unlock=lock(); announce('demo.resetting','pending');
    try { await post('/api/v1/passports/seed?force=true'); await cvLoadPassports(); announce('demo.resetDone','success'); }
    catch (error) { announce('demo.resetFailed','failed',{reason:error.uiMessage ?? error.message}); }
    finally {
      unlock();
      if (trigger === el('demo-reset') && document.activeElement === document.body && !el('view-demo').classList.contains('hidden')) trigger.focus();
    }
  }
  return {run,reset,get busy() {return busy;}};
})();
