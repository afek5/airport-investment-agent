export const meta = {
  name: 'build-airport-agent',
  description: 'Build the Airport Investment Intelligence Agent per docs/HANDOFF.md: build, verify and fix each package phase by phase',
  whenToUse: 'Run from ~/Documents/HA after the human has done setup-wizard stages 1 and 3. args: {from: "P0".."P4", to: "P0".."P4"}',
  phases: [
    { title: 'Preflight', detail: 'tools, secrets, git, raw data present' },
    { title: 'P0', detail: 'scaffold + Anchorage tracer bullet' },
    { title: 'P1', detail: 'ingest, analytics, agent/API, frontend in parallel' },
    { title: 'P2', detail: 'integration + golden/live/e2e verification' },
    { title: 'P3', detail: 'docs + deploy prepared (local prod container)' },
    { title: 'LIVE', detail: 'deploy verified live (after human wizard stages 4-5)' },
    { title: 'P4', detail: 'deferred: charts, query_public_api, voice, deck' },
  ],
}

const ORDER = ['P0', 'P1', 'P2', 'P3', 'LIVE', 'P4']
const from = ORDER.indexOf((args && args.from) || 'P0')
const to = ORDER.indexOf((args && args.to) || 'P3')
const want = p => ORDER.indexOf(p) >= from && ORDER.indexOf(p) <= to

const REPORT = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'blocked', 'failed'] },
    summary: { type: 'string' },
    done_when_evidence: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'array', items: { type: 'string' } },
    contract_changes: { type: 'array', items: { type: 'string' } },
    files_owned_touched: { type: 'array', items: { type: 'string' } },
    shared_files_touched: { type: 'array', items: { type: 'string' } },
    open_issues: { type: 'array', items: { type: 'string' } },
    human_action_needed: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'summary', 'done_when_evidence', 'open_issues', 'human_action_needed'],
}

const VERDICT = {
  type: 'object',
  properties: {
    pass: { type: 'boolean' },
    failures: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'array', items: { type: 'string' } },
  },
  required: ['pass', 'failures', 'evidence'],
}

const PREFLIGHT = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    missing: { type: 'array', items: { type: 'string' } },
    notes: { type: 'array', items: { type: 'string' } },
  },
  required: ['ok', 'missing'],
}

const buildPrompt = (pkg, extra) => `You are the builder for package ${pkg} of the Airport Investment Intelligence Agent.

Read docs/HANDOFF.md (§0, the ground rules, §2 contracts and the "${pkg}" section) and the docs/SPEC.md sections that package cites. Use GLOSSARY.md terms. Work only within that package's owned paths, following the shared-working-tree rule for shared files.

Build until the package's "Done when" criterion is observably true, proven by commands you actually ran. Commit your work (explicit path list, afek5 identity, attribution trailer) and push with GH_TOKEN=$(gh auth token -u afek5) once the repo exists.
${extra || ''}
If a stop-and-report condition from HANDOFF §0 applies, stop and return status "blocked" with the reason in human_action_needed.
Return the report (the HANDOFF §0 agent report format).`

const verifyPrompt = (pkg, report) => `You are an independent verifier for package ${pkg} of the Airport Investment Intelligence Agent. You did not build it, so be skeptical.

Read the "${pkg}" section of docs/HANDOFF.md and the SPEC sections it cites. Then check EVERY clause of its "Done when" criterion yourself by running the commands, tests, builds and requests (do not trust the builder's claims). Also check that:
- GLOSSARY terms are used (Data Confidence, Provisional Score, Spill Scenario…);
- no secrets are committed;
- no employer names or branding appear;
- commits are only under the afek5 identity.

Builder's report, to check rather than believe:
${JSON.stringify(report, null, 2)}

pass = true only if every clause holds. List each failing clause concretely in failures, with what you observed.`

const fixPrompt = (pkg, failures) => `You are the builder for package ${pkg} (see the "${pkg}" section of docs/HANDOFF.md). An independent verifier found these failures against its "Done when" criterion:
${failures.map(f => '- ' + f).join('\n')}

Fix each one at the root cause, re-run the checks that prove it, commit and push (afek5 only), and return the report (the HANDOFF §0 format).`

// Build → verify → up to 2 fix rounds for one package. Returns {pkg, report, verdict}.
async function runPackage(pkg, phaseName, extra) {
  let report = await agent(buildPrompt(pkg, extra), { label: `${pkg}:build`, phase: phaseName, schema: REPORT })
  if (!report) return { pkg, report: null, verdict: { pass: false, failures: ['builder agent died'], evidence: [] } }
  if (report.status === 'blocked') return { pkg, report, verdict: { pass: false, failures: ['blocked'], evidence: [] } }
  let verdict = await agent(verifyPrompt(pkg, report), { label: `${pkg}:verify`, phase: phaseName, schema: VERDICT })
  for (let round = 1; round <= 2 && verdict && !verdict.pass; round++) {
    log(`${pkg}: verify failed (${verdict.failures.length} issue(s)), fix round ${round}`)
    report = await agent(fixPrompt(pkg, verdict.failures), { label: `${pkg}:fix${round}`, phase: phaseName, schema: REPORT })
    if (!report || report.status === 'blocked') break
    verdict = await agent(verifyPrompt(pkg, report), { label: `${pkg}:verify${round + 1}`, phase: phaseName, schema: VERDICT })
  }
  return { pkg, report, verdict: verdict || { pass: false, failures: ['verifier died'], evidence: [] } }
}

const results = []
const halt = (why) => ({ halted: true, why, results })
const allPassed = rs => rs.every(r => r && r.verdict && r.verdict.pass)

// ── Preflight ──────────────────────────────────────────────────────────
phase('Preflight')
const pre = await agent(`Preflight check for the build in ~/Documents/HA. Report problems; change nothing.
Check, without printing any secret value:
- .env exists and has non-empty MODEL_ID, ACCESS_CODE, SESSION_SECRET (grep key names only). ANTHROPIC_API_KEY may still be missing because the human is adding it during P0; if so, put it in notes, not in missing;
- \`gh auth token -u afek5\` succeeds;
- docker is running (\`docker info\`);
- uv, node ≥ 20 and npm are installed;
- data/raw contains t100seg_2026_07.zip, ontime_2026_08.zip, airports.csv, taf2025.zip and faa_cy2025_commercial_enplanements.xlsx;
- the git repo exists locally on branch main.
If the requested start phase is after P0 (start = ${ORDER[from]}), also confirm the earlier phases' artifacts exist (backend/, frontend/, data/snapshot/manifest.json as relevant).
ok = true only if nothing required is missing. List each missing item with the human fix (e.g. "run ./scripts/setup-wizard.sh stage 1").`,
  { label: 'preflight', phase: 'Preflight', schema: PREFLIGHT })
if (!pre || !pre.ok) return halt({ phase: 'Preflight', missing: pre ? pre.missing : ['preflight agent died'] })

// ── P0 ─────────────────────────────────────────────────────────────────
if (want('P0')) {
  phase('P0')
  const r = await runPackage('P0', 'P0', 'If ANTHROPIC_API_KEY is not yet in .env when you reach the live G3 test, build and test everything else first, then poll .env (key name only, never print it) every 2 minutes for up to 30 minutes before reporting blocked.')
  results.push(r)
  if (!allPassed([r])) return halt({ phase: 'P0', package: r })
}

// ── P1: four packages in parallel, each verified independently (no barrier between build and verify) ──
if (want('P1')) {
  phase('P1')
  const pkgs = ['P1-A', 'P1-B', 'P1-C', 'P1-D']
  const extras = {
    'P1-A': 'The On-Time download was started detached by P0. Check data/raw/ontime/download.log; wait for it (poll every few minutes) instead of restarting it.',
    'P1-D': 'Use the ui-taste skill (.claude/skills/ui-taste) as instructed in your section.',
  }
  const rs = await pipeline(pkgs, pkg => runPackage(pkg, 'P1', extras[pkg]))
  results.push(...rs)
  if (!allPassed(rs)) return halt({ phase: 'P1', failed: rs.filter(r => !(r && r.verdict && r.verdict.pass)).map(r => r && r.pkg) })
}

// ── P2: needs every P1 package, so it runs after them ──
if (want('P2')) {
  phase('P2')
  const r = await runPackage('P2', 'P2')
  results.push(r)
  if (!allPassed([r])) return halt({ phase: 'P2', package: r })
}

// ── P3: docs and deploy prep in parallel ──
if (want('P3')) {
  phase('P3')
  const rs = await pipeline(['P3-E', 'P3-F'], pkg => runPackage(pkg, 'P3',
    pkg === 'P3-F' ? 'This package is outcome 1 ("prepared") only. Its Done-when is the "P3-F — Deploy, outcome 1" section; the live URL is NOT part of it (that is the separate LIVE package). You cannot create accounts.' : ''))
  results.push(...rs)
  if (!allPassed(rs)) return halt({ phase: 'P3', failed: rs.filter(r => !(r && r.verdict && r.verdict.pass)).map(r => r && r.pkg) })
}

// ── LIVE: only after the human finished setup-wizard stages 4-5 ──
if (want('LIVE')) {
  phase('LIVE')
  const r = await runPackage('LIVE', 'LIVE', 'Use the RENDER_URL and ACCESS_CODE from .env (never print secrets). Cold starts on the Render free tier can take ~60 s; retry the health check before concluding.')
  results.push(r)
  if (!allPassed([r])) return halt({ phase: 'LIVE', package: r })
}

// ── P4: deferred, sequential so each item ships independently ──
if (want('P4')) {
  phase('P4')
  for (const item of ['P4 item 1: bespoke Evidence charts', 'P4 item 2: query_public_api', 'P4 item 3: voice call (SPEC §10)', 'P4 item 4: 5-slide deck with the officecli skill']) {
    const r = await runPackage(item, 'P4', 'This is one item from the HANDOFF "P4" section. Ship only this item, keep everything else green (make test), and treat "Done when" as: the item works end to end in the running app (or the deck file exists with real screenshots) and all existing tests still pass.')
    results.push(r)
    if (!allPassed([r])) return halt({ phase: 'P4', package: r })
  }
}

const humanSteps = results.flatMap(r => (r && r.report && r.report.human_action_needed) || [])
const openIssues = results.flatMap(r => ((r && r.report && r.report.open_issues) || []).map(i => `${r.pkg}: ${i}`))
log(`Completed ${ORDER[from]}→${ORDER[to]}: ${results.length} package(s) verified`)
return { halted: false, results: results.map(r => ({ pkg: r.pkg, status: r.report && r.report.status, pass: r.verdict.pass, summary: r.report && r.report.summary })), humanSteps, openIssues }
