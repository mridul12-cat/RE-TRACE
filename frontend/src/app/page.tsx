'use client'

import React, { useState } from 'react'

export default function DashboardPage() {
  const [running, setRunning] = useState<string | null>(null)
  const [scenarioData, setScenarioData] = useState<any | null>(null)
  const [verifyStatus, setVerifyStatus] = useState<string | null>(null)

  const runScenario = async (scenario: string) => {
    setRunning(scenario)
    setScenarioData(null)
    setVerifyStatus(null)

    try {
      const res = await fetch('/api/v1/demo/run-scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
      })
      const data = await res.json()
      setScenarioData(data)
    } catch (err: any) {
      setScenarioData({
        title: `Scenario ${scenario} Execution Error`,
        verdict: 'ERROR',
        stages: [{ stage: 0, name: 'Network Error', status: 'FAILED', details: err.message }]
      })
    } finally {
      setRunning(null)
    }
  }

  const verifyCertificate = async (certId: string) => {
    setVerifyStatus('Verifying commitment against circular ledger...')
    try {
      const res = await fetch(`/api/v1/certificates/verify/${certId}`)
      if (res.ok) {
        const data = await res.json()
        setVerifyStatus(`AUTHENTICATED on LOCAL TESTNET (Commit: ${data.evidence_commitment.substring(0, 16)}...)`)
      } else {
        setVerifyStatus('Certificate not anchored or hash mismatch.')
      }
    } catch (e: any) {
      setVerifyStatus(`Verification error: ${e.message}`)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            RE:TRACE Circular Economy Platform
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono">IEEE Hackathon v1.0</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">Verifiable Digital Product Passports, Dual-Mode AI, Closed-Form Mass-Balance & Local EVM Ledger</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 text-xs font-mono flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            LOCAL TESTNET (Chain 31337)
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-purple-950/60 border border-purple-500/30 text-purple-300 text-xs font-mono">
            Dual-Mode AI Observer
          </div>
        </div>
      </div>

      {/* 1-Click Scenario Runner Bar */}
      <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h2 className="font-semibold text-white">Demonstrable Hackathon Scenarios (Pillar R4 & R5)</h2>
            <p className="text-xs text-slate-400">Trigger multi-stage automated verification tests with deterministic closed-form mathematics.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => runScenario('A')}
              disabled={running !== null}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold disabled:opacity-50 transition"
            >
              {running === 'A' ? 'Running...' : 'Run Scenario A (Legitimate)'}
            </button>
            <button
              onClick={() => runScenario('B')}
              disabled={running !== null}
              className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold disabled:opacity-50 transition"
            >
              {running === 'B' ? 'Running...' : 'Run Scenario B (Fraud Claim)'}
            </button>
            <button
              onClick={() => runScenario('C')}
              disabled={running !== null}
              className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold disabled:opacity-50 transition"
            >
              {running === 'C' ? 'Running...' : 'Run Scenario C (Tampering)'}
            </button>
          </div>
        </div>

        {scenarioData && (
          <div className="mt-4 pt-4 border-t border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-slate-200">{scenarioData.title}</span>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                scenarioData.verdict === 'VERIFIED' ? 'bg-emerald-500/20 text-emerald-300' :
                scenarioData.verdict === 'CLAIM FLAGGED' ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300'
              }`}>
                {scenarioData.verdict}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {scenarioData.stages?.map((st: any) => (
                <div key={st.stage} className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-1">
                  <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                    <span>Stage {st.stage}</span>
                    <span className="text-emerald-400">{st.status}</span>
                  </div>
                  <div className="font-medium text-slate-200">{st.name}</div>
                  <div className="text-[11px] text-slate-400 truncate">{st.details || st.decision || st.tx_hash}</div>
                </div>
              ))}
            </div>

            {scenarioData.mathematical_proof && (
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-rose-300 whitespace-pre-wrap">
                {scenarioData.mathematical_proof}
              </div>
            )}

            {scenarioData.verdict === 'EVIDENCE_INTEGRITY_FAILURE' && (
              <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/30 font-mono text-xs text-amber-300">
                ⚠️ EVIDENCE_INTEGRITY_FAILURE DETECTED: Physical evidence hashes do not match the on-chain cryptographic commitment! The passport has been transitioned to FLAGGED quarantine state on LOCAL TESTNET (requires authorized AUDITOR resolution).
              </div>
            )}

            {scenarioData.certificate && (
              <div className="p-4 rounded-xl bg-slate-950 border border-emerald-500/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-xs font-mono">
                <div>
                  <span className="text-emerald-400 font-bold block">Proof-of-Recycling Issued: {scenarioData.certificate.certificate_id}</span>
                  <span className="text-slate-400">Anchor: {scenarioData.certificate.evidence_commitment.substring(0, 32)}...</span>
                </div>
                <button
                  onClick={() => verifyCertificate(scenarioData.certificate.certificate_id)}
                  className="px-3 py-1.5 rounded-lg bg-teal-600/30 hover:bg-teal-600/50 border border-teal-500/30 text-teal-300 text-xs transition"
                >
                  Verify On-Chain
                </button>
              </div>
            )}

            {verifyStatus && (
              <div className="p-2.5 rounded-lg bg-teal-950/40 border border-teal-500/30 text-teal-300 text-xs font-mono">
                {verifyStatus}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Grid of DPP & Mass-Balance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <h3 className="font-bold text-white flex items-center justify-between">
            <span>Digital Product Passport (DPP-EV-NMC622-2026-M04)</span>
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-xs font-mono">EU Reg 2023/1542</span>
          </h3>
          <div className="space-y-2 text-xs text-slate-300">
            <div className="flex justify-between border-b border-slate-800 pb-1">
              <span className="text-slate-400">Model:</span>
              <span>24V EV Traction Battery Module (6S2P)</span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-1">
              <span className="text-slate-400">Manufacturer:</span>
              <span>Nordic Battery Systems AB</span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-1">
              <span className="text-slate-400">Intake Batch Size:</span>
              <span className="font-mono">40 Modules × 25 kg = 1,000.0 kg</span>
            </div>
          </div>
          <div className="text-xs text-slate-400">
            <span className="font-semibold text-slate-300 block mb-1">Elemental Prior:</span>
            Nickel: 18.0% | Cobalt: 6.0% | Manganese: 6.0% | Lithium: 2.8% | Copper: 11.2%
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <h3 className="font-bold text-white">Deterministic Mass-Balance Laws</h3>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 space-y-1">
            <div className="text-emerald-400 font-semibold">// First Law of Thermodynamics:</div>
            <div>∑ M_recovered ≤ M_intake × (1 + τ_scale)</div>
            <div>M_max_allowed = 1,000.00 × 1.005 = 1,005.00 kg</div>
            <div className="text-purple-400 mt-2">// Closed-form Recovery Range:</div>
            <div>M_exp_nom = M_intake × w_nominal × η_nominal</div>
            <div>M_abs_ceiling = M_intake × w_max × (1 + τ_scale)</div>
          </div>
          <div className="text-xs text-slate-400">
            AI is strictly an observation layer (<span className="text-purple-400 font-mono">AI_ESTIMATED</span>).
            Deterministic verification is pure closed-form algebra.
          </div>
        </div>
      </div>
    </div>
  )
}
