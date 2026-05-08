/* ═══════════════════════════════════════════════
   Pragyaa.AI — App Logic (Client-Side Excel Processing)
   Uses SheetJS (xlsx) for browser-based Excel parsing
   ═══════════════════════════════════════════════ */

// Load SheetJS from CDN
const script = document.createElement('script');
script.src = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js';
document.head.appendChild(script);

// ─── State ────────────────────────────────────
let state = {
  file: null,
  rawData: null,
  analysis: null,
  deltas: null,
  optimizedPrompt: '',
  history: [],
  engineMode: 'gemini',
};

// ─── DOM References ───────────────────────────
const $ = id => document.getElementById(id);
const dropzone = $('dropzone');
const fileInput = $('fileInput');
const fileInfo = $('fileInfo');
const fileName = $('fileName');
const removeFile = $('removeFile');
const analyzeBtn = $('analyzeBtn');
const resultsSection = $('resultsSection');
const promptSection = $('promptSection');
const historySection = $('historySection');
const loadingOverlay = $('loadingOverlay');
const toast = $('toast');
const engineModeSelect = $('engineMode');

// ─── Event Listeners ──────────────────────────
engineModeSelect.addEventListener('change', (e) => {
  state.engineMode = e.target.value;
  if (state.engineMode === 'vertex') {
    showToast('🚀 Backend Engine selected (Requires Vertex AI setup)');
  }
});

// ... (Rest of upload handlers) ...

// ─── Analysis Pipeline ────────────────────────
analyzeBtn.addEventListener('click', async () => {
  if (!state.file) return;
  showLoading('Processing...');
  
  try {
    if (state.engineMode === 'vertex') {
      updateLoader('Calling Backend API (Vertex AI)...');
      await runBackendAnalysis();
    } else {
      updateLoader('Analyzing locally...');
      await runLocalAnalysis();
    }
  } catch (err) {
    hideLoading();
    showToast('❌ Error: ' + err.message);
    console.error(err);
  }
});

async function runBackendAnalysis() {
  const reader = new FileReader();
  const fileBase64 = await new Promise((resolve) => {
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.readAsDataURL(state.file);
  });

  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_content: fileBase64,
      current_prompt: $('currentPrompt').value,
    })
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || 'Backend analysis failed');
  }

  const result = await response.json();
  state.analysis = result.analysis;
  state.deltas = result.deltas;
  
  const apiKey = $('apiKey').value.trim();
  if (apiKey) {
    updateLoader('🤖 Calling Gemini 1.5 Flash for final optimization...');
    state.optimizedPrompt = await generatePromptWithGemini(apiKey, state.analysis, state.deltas, $('currentPrompt').value);
    state.promptSource = 'ai';
  } else {
    updateLoader('Building template-based prompt...');
    state.optimizedPrompt = buildTemplatePrompt(state.analysis, state.deltas, $('currentPrompt').value);
    state.promptSource = 'template';
  }

  finalizeAnalysis();
}

async function runLocalAnalysis() {
    const data = await readExcel(state.file);
    state.rawData = data;
    updateLoader('Analyzing discrepancies...');
    
    state.analysis = analyzeRootCauses(data);
    updateLoader('Generating prompt deltas...');
    state.deltas = generateDeltas(state.analysis);
    
    const currentPrompt = $('currentPrompt').value;
    const apiKey = $('apiKey').value.trim();
    
    if (apiKey) {
      try {
        updateLoader('🤖 Calling Gemini 1.5 Flash...');
        state.optimizedPrompt = await generatePromptWithGemini(apiKey, state.analysis, state.deltas, currentPrompt, 3);
        state.promptSource = 'ai';
      } catch (apiError) {
        state.optimizedPrompt = buildTemplatePrompt(state.analysis, state.deltas, currentPrompt);
        state.promptSource = 'template';
      }
    } else {
      state.optimizedPrompt = buildTemplatePrompt(state.analysis, state.deltas, currentPrompt);
      state.promptSource = 'template';
    }
    
    finalizeAnalysis();
}

function finalizeAnalysis() {
    state.history.push({
      timestamp: new Date().toISOString(),
      file: state.file.name,
      cases: state.analysis.summary.total,
      agreement: state.analysis.summary.agreementRate,
      falseReworks: state.analysis.summary.falseReworkCount,
      source: state.promptSource,
    });

    renderResults();
    renderPrompt();
    renderHistory();
    hideLoading();
    
    showToast(`✅ Analysis complete — ${state.promptSource === 'ai' ? '🤖 AI-generated' : '📝 Template-based'} prompt ready`);
    
    resultsSection.style.display = 'block';
    promptSection.style.display = 'block';
    historySection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── Excel Reader ─────────────────────────────
async function readExcel(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const wb = XLSX.read(e.target.result, { type: 'array' });
        const sheetName = wb.SheetNames.includes('Raw Data') ? 'Raw Data' : wb.SheetNames[0];
        const ws = wb.Sheets[sheetName];
        const json = XLSX.utils.sheet_to_json(ws, { defval: '' });
        resolve(json);
      } catch (err) { reject(err); }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsArrayBuffer(file);
  });
}

// ─── Root Cause Analyzer ──────────────────────
function analyzeRootCauses(data) {
  const norm = v => String(v || '').trim().toLowerCase();
  const total = data.length;
  
  const aiCol = Object.keys(data[0]).find(k => k.includes('Call Status AI')) || 'Call Status AI';
  const verCol = Object.keys(data[0]).find(k => k.includes('Call Status Verifier')) || 'Call Status Verifier';
  
  let agree = 0, falseRework = [], falseApprove = [];
  data.forEach(row => {
    const ai = norm(row[aiCol]);
    const ver = norm(row[verCol]);
    if (ai === ver) agree++;
    else if (ai === 'rework' && ver === 'approved') falseRework.push(row);
    else if (ai === 'approved' && (ver === 'rework')) falseApprove.push(row);
  });
  
  // Parameter failures in false reworks
  const params = [
    'Greeting Met', 'Benefits Explained Met', 'Charges Explained Met',
    'Pitch Modulation', 'Pitch Pace', 'Tone Appropriate Met',
    'Consent Taken Met', 'Card Variant Met'
  ];
  
  const paramFailures = {};
  params.forEach(p => {
    const col = Object.keys(data[0]).find(k => k.includes(p));
    if (!col) return;
    const fails = falseRework.filter(r => norm(r[col]) === 'no').length;
    paramFailures[p] = { count: fails, pct: Math.round(fails / falseRework.length * 1000) / 10 };
  });
  
  // Consent patterns
  const consentReasonCol = Object.keys(data[0]).find(k => k.includes('Consent Taken Reasons')) || '';
  const consentFails = falseRework.filter(r => norm(r['Consent Taken Met']) === 'no');
  const consentPatterns = {
    'Passive Okay/Haan': 0, 'No Explicit Ask': 0,
    'Ji/Hmm Backchannel': 0, 'Premature/Rushed': 0
  };
  consentFails.forEach(r => {
    const reason = norm(r[consentReasonCol] || '');
    if (['passive', 'okay', "'ok'", 'haan', 'acknowledgm'].some(k => reason.includes(k))) consentPatterns['Passive Okay/Haan']++;
    if (['not explicitly', 'did not', 'without'].some(k => reason.includes(k))) consentPatterns['No Explicit Ask']++;
    if (["'ji'", 'hmm', 'backchannel'].some(k => reason.includes(k))) consentPatterns['Ji/Hmm Backchannel']++;
    if (['rushed', 'before'].some(k => reason.includes(k))) consentPatterns['Premature/Rushed']++;
  });
  
  // Charges patterns
  const chargesReasonCol = Object.keys(data[0]).find(k => k.includes('Charges Explained Reasons')) || '';
  const chargesFails = falseRework.filter(r => norm(r['Charges Explained Met']) === 'no');
  const chargesPatterns = {
    'Rushed Delivery': 0, 'Confusing/Unclear': 0,
    'Missing GST': 0, 'Wrong Amounts': 0
  };
  chargesFails.forEach(r => {
    const reason = norm(r[chargesReasonCol] || '');
    if (['rushed', 'fast', 'quickly'].some(k => reason.includes(k))) chargesPatterns['Rushed Delivery']++;
    if (['confus', 'unclear', 'not clear'].some(k => reason.includes(k))) chargesPatterns['Confusing/Unclear']++;
    if (reason.includes('gst')) chargesPatterns['Missing GST']++;
    if (['incorrect', 'wrong'].some(k => reason.includes(k))) chargesPatterns['Wrong Amounts']++;
  });
  
  // False approve reasons
  const reworkReasonCol = Object.keys(data[0]).find(k => k.includes('Reason for Rework'));
  const faReasons = falseApprove.map(r => r[reworkReasonCol]).filter(Boolean);
  
  return {
    summary: {
      total, agree, agreementRate: Math.round(agree / total * 1000) / 10,
      aiApprovalRate: Math.round(data.filter(r => norm(r[aiCol]) === 'approved').length / total * 1000) / 10,
      verApprovalRate: Math.round(data.filter(r => norm(r[verCol]) === 'approved').length / total * 1000) / 10,
      falseReworkCount: falseRework.length,
      falseApproveCount: falseApprove.length,
    },
    paramFailures, consentPatterns, chargesPatterns, faReasons,
  };
}

// ─── Delta Generator ──────────────────────────
function generateDeltas(analysis) {
  const deltas = [];
  const pf = analysis.paramFailures;
  
  const sorted = Object.entries(pf).sort((a, b) => b[1].pct - a[1].pct);
  sorted.forEach(([param, info]) => {
    if (info.pct < 5) return;
    const severity = info.pct > 50 ? 'CRITICAL' : info.pct > 20 ? 'HIGH' : 'MEDIUM';
    let rootCause = '', fix = '';
    
    if (param === 'Consent Taken Met') {
      rootCause = 'AI rejects passive Hindi consent ("Okay", "Haan ji", "Theek hai")';
      fix = 'Implement 3-Tier consent: Tier 1 (explicit), Tier 2 (contextual — valid after full pitch), Tier 3 (refusal only)';
    } else if (param === 'Charges Explained Met') {
      rootCause = 'AI penalizes delivery speed instead of factual accuracy';
      fix = 'Switch to content-based evaluation — pass if ₹699+GST stated correctly regardless of pace';
    } else if (param === 'Pitch Pace') {
      rootCause = 'AI pace threshold stricter than human verifier tolerance';
      fix = 'Only fail if customer explicitly asks to repeat or slow down';
    } else if (param === 'Benefits Explained Met') {
      rootCause = 'AI requires too many benefits to be mentioned';
      fix = 'Pass if agent mentions ≥2 core benefits accurately';
    } else if (param === 'Card Variant Met') {
      rootCause = 'AI fails on informal card name variations';
      fix = 'Add fuzzy mapping: "Coral card"/"Updated Coral"/"Coral Visa" → Coral Debit Card';
    } else {
      rootCause = `AI too strict on ${param}`;
      fix = `Align ${param} threshold with human verifier standards`;
    }
    
    deltas.push({ param, ...info, severity, rootCause, fix });
  });
  
  return deltas;
}

// ─── Gemini AI Prompt Generator ───────────────
async function generatePromptWithGemini(apiKey, analysis, deltas, currentPrompt, maxRetries = 3) {
  const s = analysis.summary;
  const cp = analysis.consentPatterns;
  const ch = analysis.chargesPatterns;
  
  // Build the meta-prompt that instructs Gemini to write the audit prompt
  const metaPrompt = `You are an expert prompt engineer specializing in compliance audit automation.

I have analyzed ${s.total} ICICI Bank Debit Card upgrade call audits comparing AI verdicts vs Human Verifier verdicts. Here is the data:

## KEY STATISTICS
- AI Approval Rate: ${s.aiApprovalRate}% | Human Verifier Approval Rate: ${s.verApprovalRate}%
- Agreement Rate: ${s.agreementRate}% (target: >85%)
- False Reworks (AI rejected, Verifier approved): ${s.falseReworkCount} cases
- False Approves (AI approved, Verifier rejected): ${s.falseApproveCount} cases

## PARAMETER-LEVEL FAILURES IN FALSE REWORK CASES
${deltas.map(d => `- ${d.param}: ${d.pct}% failure rate | Root Cause: ${d.rootCause} | Fix: ${d.fix}`).join('\n')}

## CONSENT FAILURE PATTERNS
- Passive Okay/Haan: ${cp['Passive Okay/Haan']} cases
- No Explicit Ask: ${cp['No Explicit Ask']} cases
- Ji/Hmm Backchannel: ${cp['Ji/Hmm Backchannel']} cases
- Premature/Rushed: ${cp['Premature/Rushed']} cases

## CHARGES FAILURE PATTERNS
- Rushed Delivery: ${ch['Rushed Delivery']} cases
- Confusing/Unclear: ${ch['Confusing/Unclear']} cases
- Missing GST mention: ${ch['Missing GST']} cases
- Wrong Amounts: ${ch['Wrong Amounts']} cases

## FALSE APPROVE REASONS (Verifier rejected but AI missed)
${analysis.faReasons.length > 0 ? analysis.faReasons.map(r => `- ${r}`).join('\n') : '- None found'}

${currentPrompt ? `## CURRENT PROMPT (to improve upon)\n${currentPrompt.substring(0, 3000)}` : ''}

## YOUR TASK
Write a complete, production-ready compliance audit prompt for evaluating ICICI Debit Card upgrade calls. The prompt must:

1. Be calibrated to match human verifier judgment (currently ${s.agreementRate}% agreement, need >85%)
2. Include a 3-tier consent system for Hindi sales calls (Tier 1: explicit, Tier 2: contextual OK/Haan/Theek hai, Tier 3: refusal)
3. Use content-based charges evaluation (not speed-based) for Coral Debit Card (₹699 + GST)
4. Include fuzzy card name matching
5. Have recalibrated pitch pace thresholds
6. Include scenario-based exceptions (drop-off calls, already applied, RPC confirmation)
7. Include Soft Fail vs Hard Fail distinction
8. End with a JSON output format

Write the prompt in a clear, structured format with numbered sections. Include the actual data from the analysis to calibrate the rules. Make it production-ready — this will be directly deployed.`;

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
  
  let lastError;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: metaPrompt }] }],
          generationConfig: {
            temperature: 0.7,
            maxOutputTokens: 8192,
          }
        })
      });
      
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Gemini API error (${response.status}): ${errText.substring(0, 200)}`);
      }
      
      const result = await response.json();
      const text = result.candidates?.[0]?.content?.parts?.[0]?.text;
      
      if (!text) throw new Error('Gemini returned empty response');
      
      return `# AI-GENERATED AUDIT PROMPT — Gemini 1.5 Flash\n# Based on: ${state.file.name} (${s.total} cases analysis)\n# Generated: ${new Date().toLocaleString()}\n# Agreement target: >85% (current: ${s.agreementRate}%)\n\n${text}`;
    } catch (err) {
      lastError = err;
      console.warn(`Attempt ${attempt} failed:`, err);
      if (attempt < maxRetries) {
        const wait = Math.pow(2, attempt) * 1000;
        updateLoader(`Attempt ${attempt} failed. Retrying in ${wait/1000}s...`);
        await sleep(wait);
      }
    }
  }
  
  throw lastError;
}

// ─── Template Prompt Builder (Fallback) ───────
function buildTemplatePrompt(analysis, deltas, currentPrompt) {
  const s = analysis.summary;
  const cp = analysis.consentPatterns;
  const ch = analysis.chargesPatterns;
  
  return `# REFINED DC AUDIT PROMPT V3 — OpenClaw/Hermes Optimized
# Based on: ${state.file.name} (${s.total} cases, ${s.falseReworkCount} false reworks)
# Generated: ${new Date().toLocaleString()} | Product: ICICI Debit Card Upgrade

You are an expert Compliance Auditor for ICICI Bank Debit Card upgrades.
Your goal is to evaluate the call for accuracy, compliance, and consent — while matching human verifier judgment patterns.

CRITICAL CALIBRATION NOTE:
The current AI model has a ${100 - s.aiApprovalRate}% rejection rate vs the human verifier's ${100 - s.verApprovalRate}%.
This means you are TOO STRICT. ${s.falseReworkCount} out of ${s.total - Math.round(s.total * s.aiApprovalRate / 100)} AI rejections were overturned by human verifiers.
The #1 cause is treating normal conversational Hindi agreement as "passive consent."
Adjust your strictness to match human-level judgment.

---

### 1. CARD IDENTIFICATION (DC Products)
Map these variations to canonical names:
- "Coral card", "Coral Visa", "Coral Debit", "Updated Coral" → Coral Debit Card
- "Expression Coral", "Expression card" → Expression Coral Debit Card
- "400 debit card" → Flag as UNCLEAR (do not auto-fail, ask for context)
- "New visa debit card" → Coral Debit Card (if benefits match)

### 2. CONSENT EVALUATION — 3-TIER SYSTEM (MOST CRITICAL FIX)

CONTEXT: ${analysis.paramFailures['Consent Taken Met']?.pct || 0}% of false reworks were caused by consent being marked "No".
Human verifiers approved calls where customers said "Okay", "Haan ji", "Theek hai"
after hearing the full pitch. You MUST align with this standard.
Pattern analysis: Passive agreement=${cp['Passive Okay/Haan']}, No explicit ask=${cp['No Explicit Ask']}, Backchannel=${cp['Ji/Hmm Backchannel']}

**TIER 1 — ALWAYS VALID (Auto-approve consent):**
- "Haan, request le lijiye" / "Yes, kar dijiye" / "Yes, proceed"
- "Haan, upgrade kar do" / "Ji, apply karo" / "Okay, le lo"
- Any sentence that explicitly ties agreement to the upgrade request

**TIER 2 — VALID IF CONTEXTUAL (Approve if pitch was complete):**
- "Okay" / "Theek hai" / "Haan ji" / "Ji" / "Hmm okay"
- "Accha theek hai" / "Chalo theek hai" / "Ok sir"
- RULE: If the agent explained benefits AND charges BEFORE getting this response,
  AND the customer did NOT raise objections afterward → Consent = YES
- RULE: If the customer asked at least 1 question about the card → Consent = YES

**TIER 3 — ALWAYS INVALID (Reject consent):**
- Customer explicitly refuses: "Nahi chahiye" / "Not interested" / "Cancel karo"
- Customer says they're busy: "Baad mein" / "Abhi nahi" / "Time nahi hai"
- Agent takes consent BEFORE explaining charges (premature consent)
- Customer repeatedly says only "Hmm" with zero engagement throughout entire call

**KEY PRINCIPLE:** In Indian sales calls, "Theek hai" and "Okay" after a full pitch
ARE consent. Do NOT apply Western-style explicit consent standards to Hindi calls.

### 3. CHARGES EVALUATION — CONTENT-BASED (NOT SPEED-BASED)

CONTEXT: ${analysis.paramFailures['Charges Explained Met']?.pct || 0}% of false reworks flagged charges issues.
Pattern analysis: Rushed=${ch['Rushed Delivery']}, Confusing=${ch['Confusing/Unclear']}, GST=${ch['Missing GST']}, Wrong=${ch['Wrong Amounts']}

**Coral Debit Card Standard Charges:**
- Joining Fee: ₹699 + GST (one-time, auto-debited in 7-10 days)
- Annual Fee: ₹699 + GST (from Year 2 onward)

**PASS Charges if ALL of these are met:**
□ Joining fee amount mentioned (₹699 or "699 plus GST")
□ Annual fee amount mentioned (₹699 or "699 plus GST")
□ Both fees stated as SEPARATE items

**SOFT FAIL (Observation only, NOT Rework):**
- Forgetting "plus GST" but stating ₹699 correctly
- Slightly rushed delivery if amounts are factually correct

**HARD FAIL (Rework):**
- Wrong amount: "999 plus GST" or "600 plus GST"
- Saying "No charges" or "Free card"
- Completely omitting charges discussion
- Contradictory statements about charges

**SPEED RULE:** Do NOT fail purely because charges were explained quickly.
Only flag if the customer explicitly asks to repeat and agent ignores.

### 4. BENEFITS EVALUATION
**Core DC Benefits (must mention at least 2):**
- Higher withdrawal limit (₹1 lakh/day)
- Higher transaction limit (₹5 lakh/day)
- Wallet/Card protection insurance
- Apollo Pharmacy discount (10-15%)
- Airport lounge access (if applicable)

**PASS if:** Agent mentions ≥2 benefits accurately
**HARD FAIL:** Agent invents benefits or gives completely wrong information

### 5. GREETING & TONE (Low dispute rate — keep current logic)
- Greeting: Agent must identify themselves and ICICI Bank
- Tone: Must not be aggressive or rude
- These parameters have <2% dispute rate — no changes needed

### 6. PITCH PACE EVALUATION (RECALIBRATED)
**Only mark Pitch Pace = No if:**
- Customer explicitly says "Dhire boliye" / "Please repeat" / "Samajh nahi aaya"
- Customer asks the SAME question twice because they couldn't follow
- Call duration is under 1.5 minutes AND all parameters were covered

### 7. DROP-OFF CALL SPECIAL RULES
If filename contains "Drop_off":
- Shortened pitch is acceptable
- Consent standard remains the same
- Drop-off script adherence should be checked

### 8. SCENARIO-BASED EXCEPTIONS
- Customer already applied via app → Cannot be approved
- Customer wants to visit branch → Not a valid lead
- Customer's family member answers → RPC must be confirmed

---

### STRICT OUTPUT FORMAT (JSON):
{
  "Call_Summary": "Start with 'Call explains...'",
  "Verdict": "Approved / Rework / Observation",
  "CardName_Canonical": "Coral Debit Card / Expression Coral Debit Card / NA",
  "Greeting_Met": "Yes/No",
  "Benefits_Met": "Yes/No",
  "Charges_Met": "Yes/No",
  "Consent_Met": "Yes/No",
  "Consent_Tier": "Tier1/Tier2/Tier3",
  "Pitch_Pace_Met": "Yes/No",
  "Tone_Met": "Yes/No",
  "Rework_Reason": "Explain HARD FAIL only — leave blank if Approved",
  "Soft_Fail_Notes": "Minor observations for agent coaching",
  "Confidence_Score": "0.0 to 1.0"
}

Call Transcript:
[INSERT TRANSCRIPT HERE]
`;
}

// ─── Renderers ────────────────────────────────
function renderResults() {
  const s = state.analysis.summary;
  const gap = Math.round((s.verApprovalRate - s.aiApprovalRate) * 10) / 10;
  
  $('statsGrid').innerHTML = [
    { value: s.total, label: 'Total Cases', cls: '' },
    { value: s.agreementRate + '%', label: 'Agreement', cls: s.agreementRate > 70 ? 'success' : 'danger' },
    { value: s.aiApprovalRate + '%', label: 'AI Approval', cls: '' },
    { value: s.verApprovalRate + '%', label: 'Verifier Approval', cls: 'success' },
    { value: s.falseReworkCount, label: 'False Reworks', cls: 'danger' },
    { value: gap + '%', label: 'Approval Gap', cls: 'danger' },
  ].map(s => `
    <div class="stat-card">
      <div class="stat-value ${s.cls}">${s.value}</div>
      <div class="stat-label">${s.label}</div>
    </div>`).join('');
  
  // Failure bars
  const sorted = Object.entries(state.analysis.paramFailures).sort((a, b) => b[1].pct - a[1].pct);
  $('failureBars').innerHTML = sorted.map(([param, info]) => {
    const cls = info.pct > 50 ? 'critical' : info.pct > 20 ? 'high' : info.pct > 5 ? 'medium' : 'low';
    const shortName = param.replace(' Met', '').replace('Explained ', '');
    return `
      <div class="failure-row">
        <div class="failure-label">${shortName}</div>
        <div class="failure-bar-bg"><div class="failure-bar ${cls}" style="width: 0%" data-width="${info.pct}"></div></div>
        <div class="failure-pct">${info.pct}%</div>
      </div>`;
  }).join('');
  
  // Animate bars
  requestAnimationFrame(() => {
    setTimeout(() => {
      document.querySelectorAll('.failure-bar').forEach(bar => {
        bar.style.width = bar.dataset.width + '%';
      });
    }, 100);
  });
  
  // Patterns
  $('patternsGrid').innerHTML = `
    <div class="pattern-box">
      <h4>🔒 Consent Failure Patterns</h4>
      ${Object.entries(state.analysis.consentPatterns).map(([k, v]) => `
        <div class="pattern-item"><span class="pattern-name">${k}</span><span class="pattern-count">${v}</span></div>
      `).join('')}
    </div>
    <div class="pattern-box">
      <h4>💰 Charges Failure Patterns</h4>
      ${Object.entries(state.analysis.chargesPatterns).map(([k, v]) => `
        <div class="pattern-item"><span class="pattern-name">${k}</span><span class="pattern-count">${v}</span></div>
      `).join('')}
    </div>`;
}

function renderPrompt() {
  // Show source badge
  const badge = state.promptSource === 'ai'
    ? '<span class="ai-badge">🤖 Gemini 2.5 Flash</span>'
    : '<span class="ai-badge template">📝 Template</span>';
  $('promptSection').querySelector('h2').innerHTML = 'Optimized Prompt ' + badge;
  
  $('optimizedPrompt').textContent = state.optimizedPrompt;
  
  // Changes view
  $('changesView').innerHTML = state.deltas.map(d => `
    <div class="change-item ${d.severity.toLowerCase()}">
      <div class="change-title">${d.param} (${d.pct}% failure rate)</div>
      <div class="change-desc"><strong>Root Cause:</strong> ${d.rootCause}<br><strong>Fix:</strong> ${d.fix}</div>
      <span class="change-status added">APPLIED</span>
    </div>`).join('');
  
  // Report view
  const s = state.analysis.summary;
  $('reportView').innerHTML = `
    <h3>Executive Summary</h3>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Total Cases</td><td>${s.total}</td></tr>
      <tr><td>Agreement Rate</td><td>${s.agreementRate}%</td></tr>
      <tr><td>AI Approval Rate</td><td>${s.aiApprovalRate}%</td></tr>
      <tr><td>Verifier Approval Rate</td><td>${s.verApprovalRate}%</td></tr>
      <tr><td>False Reworks</td><td>${s.falseReworkCount}</td></tr>
      <tr><td>False Approves</td><td>${s.falseApproveCount}</td></tr>
    </table>
    <h3>Verifier Rework Reasons (AI Missed)</h3>
    ${state.analysis.faReasons.length ? '<ul>' + [...new Set(state.analysis.faReasons)].map(r => `<li>${r}</li>`).join('') + '</ul>' : '<p>None found</p>'}
  `;
  
  // Tab switching
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.dataset.view;
      $('optimizedPrompt').style.display = view === 'optimized' ? '' : 'none';
      $('changesView').style.display = view === 'changes' ? '' : 'none';
      $('reportView').style.display = view === 'report' ? '' : 'none';
    });
  });
  
  // Copy & Download
  $('copyPrompt').onclick = () => {
    navigator.clipboard.writeText(state.optimizedPrompt);
    showToast('📋 Prompt copied to clipboard');
  };
  $('downloadPrompt').onclick = () => {
    const blob = new Blob([state.optimizedPrompt], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `refined_audit_prompt_v3_dc_${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    showToast('⬇️ Prompt downloaded');
  };
}

function renderHistory() {
  $('timeline').innerHTML = state.history.map((h, i) => `
    <div class="timeline-item">
      <div class="timeline-date">${new Date(h.timestamp).toLocaleString()}</div>
      <div class="timeline-content">
        <strong>Run #${i + 1}:</strong> ${h.file}
        <div class="timeline-stat">
          <span>Cases: <strong>${h.cases}</strong></span>
          <span>Agreement: <strong>${h.agreement}%</strong></span>
          <span>False Reworks: <strong>${h.falseReworks}</strong></span>
        </div>
      </div>
    </div>`).join('');
}

// ─── Utilities ────────────────────────────────
function showLoading(text) { loadingOverlay.style.display = 'flex'; $('loaderSub').textContent = text; }
function updateLoader(text) { $('loaderSub').textContent = text; }
function hideLoading() { loadingOverlay.style.display = 'none'; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}
