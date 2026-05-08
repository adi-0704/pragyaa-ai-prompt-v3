# Detailed Audit Gap Analysis Report
## pragyaa.ai | ICICI Bank CC & DC Call Verification Pipeline
**Report Date:** May 5, 2026 | **Scope:** CC (1,370 calls) + DC (292 calls)

---

## EXECUTIVE SUMMARY

| Metric | CC (Credit Card) | DC (Debit Card) |
|---|---|---|
| **Total Calls Audited** | 1,370 | 292 |
| **Approved** | 960 (70.1%) | 96 (32.9%) |
| **Rework** | 409 (29.9%) | 196 (67.1%) |
| **Primary Failure** | Consent + Benefits | Consent + Charges |

> **Critical Finding:** DC has a 67.1% rework rate vs CC's 29.9%. The DC audit prompt is significantly more strict — requiring an explicit "Yes" as consent — which is causing mass failures for conversational agreement patterns.

---

## PART 1: INPUT ANALYSIS (Audio Files & Agent Performance)

### 1.1 Audio File Structure (from CC_DC_audios.zip)

```
CC_audios/
  Approved/ — 5 files
  Rework/   — 5 files
DC_audios/
  Approved/ — 5 files
  Rework/   — 5 files
```

**Audio filename format:** `[CallType]_[Product]_[FNM]_[AgentID]_[Phone]_[SessionID]_[Date]_[Time]_[CallID]_[Phone].mp3`

The audio files are hosted on an internal server: `http://192.168.8.170:8080/audios/` and are also stored locally in the ZIP. This dual-source architecture means any sync failure between the internal server and zip snapshot creates audit blind spots.

---

### 1.2 GAP 1 — Consent Language Mismatch (ROOT CAUSE #1)

**What agents say:**
- "Theek hai, le lijiye" → treated as PASSIVE by model
- "Haan ji" → treated as backchannel acknowledgment, NOT consent
- "Ok" → treated as ambiguous

**What the model requires:**
- An explicit "Yes, request le lijiye" or "Haan, upgrade kar dijiye"
- A substantive sentence that *ties the answer to the request*, not just a filler word

**Impact:**
- CC: **320 out of 409 Rework calls** (78.2%) include consent as a failure reason
- DC: **186 out of 196 Rework calls** (94.9%) have Consent = No

**Root Cause:** Agents are culturally trained to accept conversational agreement.
In Indian sales calls, "Theek hai" IS consent. The model treats it as passive unless the
full call is "proactive" (customer asked questions, discussed details, etc.).
The model is correct per compliance rules, but agents are NOT trained
to elicit the specific phrase patterns the model accepts.

**Fix:**
```
1. Create an Agent "Magic Phrase" cheat sheet:
   ✓ "Sir, kya main aapka card upgrade request le sakta hoon?" → 
   ✓ Customer must say "Haan, le lijiye" / "Yes, kar dijiye" — NOT just "Ok"
   
2. In model prompt: Define "Proactive Call" threshold explicitly:
   If customer asked ≥ 1 substantive question (benefit/charge/limit) 
   AND said "Theek hai" after summary → treat as VALID consent.
```

---

### 1.3 GAP 2 — Charges Rushing & Omission (ROOT CAUSE #2)

**What agents do:**
- Bundle charges within benefits explanation ("...and the joining fee is 6500+GST, annual fee 3500+GST, 
  and you also get 4 lounge accesses per quarter...")
- Rush through fees in 2–3 seconds to minimize customer objections
- Omit GST mention ("annual fee is 3500" instead of "3500 plus 18% GST")
- Explain joining fee but NOT annual fee waiver spend (₹6,00,000 for Sapphiro)

**Impact:**
- CC: **209 out of 409 Rework calls** (51.1%) include charges as a failure reason
- DC: **163 out of 196 Rework calls** (83.2%) have Charges Explained = No

**Specific Example from CSV (FNM2626):**
> "Agent initially stated 'zero joining fee' and 'annual fee waived off'. Later stated 'annual fee is 599 plus GST.' 
> This is contradictory. The waiver criteria for Rs. 3,500 were not explained."

**Fix:**
```
1. Add a "Charges Checklist" to agent desktop tool:
   □ Joining Fee: ₹[amount] + 18% GST (or FREE)
   □ Annual Fee from Year 2: ₹[amount] + 18% GST
   □ Annual Fee Waiver: "If you spend ₹[X] lakh in a year, the fee is waived"
   □ Pause between fee and benefits (don't bundle)

2. In model prompt: Clarify the "3–4 second rushing" rule more precisely.
   Current rule is vague. Suggest: "If charges + benefits explained within 
   same 10-second block with no customer pause/response, mark as RUSHED."
```

---

### 1.4 GAP 3 — Benefits Inaccuracy & STT Hallucinations (ROOT CAUSE #3)

**What agents say:**
- "EXICIA Super Saver Visa card" (STT misheard "HPCL" or "ICICI")
- "You can refuel up to ₹1,000 per month on Sapphire" (wrong — it's ₹200/month cap)
- "Medical expense for roadside" (wrong benefit, not in ICICI card knowledge base)
- Omitting spending conditions on lounge ("4 per quarter" without "after ₹75,000 spend")

**Impact:**
- CC: **260 out of 409 Rework calls** (63.6%) include benefits as a failure reason
- DC: **51 out of 196 Rework calls** (26%) have Benefits = No

**STT-Specific Issue: The "EXICIA" Problem**
The STT engine transcribes "ICICI" → "EXICIA" in multiple calls. When the model
then searches the allowed card name list for "EXICIA Super Saver", it finds NO match
and flags the call as having an unknown/invalid card pitched. The agent was CORRECT.
The model is WRONG because of a transcription error.

**Fix:**
```
1. STT Layer: Add ICICI-specific dictionary boost:
   Boost words: ICICI, Sapphiro, Rubyx, Coral, HPCL, BookMyShow, INOX
   
2. Model Prompt: Add STT error correction logic before card matching:
   "If the card name contains 'EXICIA' or similar phonetic variants, 
   map it to the nearest valid card (HPCL Super Saver or ICICI variant)."
   
3. Agent Training: Fix high-frequency wrong facts:
   - Sapphiro fuel waiver: ₹200/month cap (NOT ₹1,000)
   - Lounge access ALWAYS requires ₹75,000 previous quarter spend
   - No medical/roadside benefits on CC (DC only)
```

---

### 1.5 GAP 4 — Card Variant Identification Failures

**What agents say:**
- "Sapphire card" → model expects "SAPPHIRO VISA-RUPAY FIRST YEAR FREE"
- "Coral RuPay card" → correctly maps to CORAL RUPAY LIFE TIME FREE
- "MMT Travel card" → should map to MMT TRAVEL MASTER-RUPAY FIRST YEAR FREE

**Impact:**
- CC: **61 out of 409 Rework calls** (14.9%) have card variant as a failure reason

**Fix:**
```
In model verification_checklist.txt, add a Synonym Mapping Table:
  "Sapphire" / "Saphir" / "Sapphiro" → SAPPHIRO family
  "Ruby" / "Rubyx" → RUBYX family
  "Coral RuPay" / "Coral Pay" → CORAL RUPAY LIFE TIME FREE
  "HPCL" / "HP card" / "Fuel card" → HPCL SUPER SAVER family
  "MMT" / "Make My Trip" → MMT TRAVEL MASTER-RUPAY
```

---

## PART 2: OUTPUT ANALYSIS (Model Prompts & Audit Logic)

### 2.1 Overview of Prompt Files

| File | Size | Lines | Complexity |
|---|---|---|---|
| CC/verification_checklist.txt | 83.7 KB | 1,332 | Very High |
| CC/verification_checklist_drop-off.txt | 85.1 KB | ~1,350 | Very High |
| DC/verification_checklist.txt | 64.0 KB | 998 | High |
| DC/verification_checklist_drop-off.txt | 65.7 KB | ~1,020 | High |
| CC/disposition.txt | 5.1 KB | 98 | Low |
| DC/disposition.txt | 15.7 KB | 541 | Medium |
| CC/script_adherence.txt | 5.8 KB | 120 | Low |
| DC/script_adherence.txt | 2.5 KB | 41 | Low |

---

### 2.2 GAP 5 — Consent Rules Are Contradictory (Critical Bug)

**In CC/verification_checklist.txt (Line 421):**
> "'Theek hai' — only if proactive discussion and full summary criteria are met and the reply clearly authorizes the request"

**In CC/verification_checklist.txt (Line 700):**
> "Allowed responses (context-based): 'OK', 'Thik hai', 'Ok le lo'"

**In DC/verification_checklist.txt (Line 57):**
> "Consent is NOT valid if the customer's only positive signals are backchannel acknowledgments — 'Ok', 'Okay', 'Haan', 'Haan ji'"

**The contradiction:** CC allows "Theek hai" as valid consent in some context. DC 
explicitly bans "Okay" as consent. Since agents use the SAME phrases for both CC and DC
calls, the model produces inconsistent verdicts for the same conversation pattern.

**Fix:**
```
Unify consent rules across CC and DC checklists:

TIER 1 (Always Valid):
  "Haan, request le lijiye" / "Yes, kar dijiye" / "Yes, proceed"

TIER 2 (Valid IF proactive call — customer asked ≥1 question):
  "Theek hai, le lo" / "Ok, kar do" / "Ji, process karo"

TIER 3 (Always Invalid — backchannel only):
  Standalone "Haan" / "Ok" / "Ji" / "Hmm" with NO request linkage
```

---

### 2.3 GAP 6 — DC Disposition.txt Is Mismatched (Structural Bug)

**Finding:** `finmech_project/DC/disposition.txt` contains rules for an **Amazon/Insta 
Credit Card** program, NOT for the ICICI Debit Card upgrade pipeline.

**Evidence (from DC/disposition.txt, Lines 370–396):**
> "Amazon Pay cashback... Lifetime free / joining fee info... Amazon ICICI Credit Card"
> "NOT_ELIGIBLE Sub Dispositions: ALREADY HAVING AMAZON PAY CREDIT CARD"

The DC audit pipeline is using a disposition framework designed for a **completely 
different product**. This means every DC call disposition (LEAD, NOT_ELIGIBLE, 
NOT_INTERESTED) is being evaluated against Amazon credit card rules, not DC debit card rules.

**Fix:**
```
URGENT: Replace DC/disposition.txt with the correct DC Debit Card 
disposition framework. Key correct DC dispositions should be:
  - LEAD GENERATED (Debit card upgrade consent taken)
  - REWORK (Non-compliant consent/charges)
  - NOT INTERESTED (Customer refused)
  - CALLBACK (Customer requested later call)
  - NOT CONNECTED (Failed to reach customer)
```

---

### 2.4 GAP 7 — Prompt Size Causes LLM Context Drift

**Finding:** The CC verification_checklist.txt is 83.7 KB / 1,332 lines. This is 
extremely large for a single prompt. LLMs (especially when processing long audio 
transcripts on top) frequently experience "context drift" where early rules are 
forgotten or de-prioritized by the end of the prompt.

**Evidence:** Multiple Rework calls in the CSV show the model correctly identifying
a small consent issue, but missing an obvious charging error earlier in the call — 
a sign of recency bias in long-context processing.

**Fix:**
```
Refactor verification_checklist.txt into modular sections:
  1. verification_checklist_core.txt    (Critical fail pillars only, <5KB)
  2. verification_checklist_benefits.txt (Card knowledge base)
  3. verification_checklist_scenarios.txt (15 scenarios)
  4. verification_checklist_consent.txt  (Consent rules)

Call the core rules first, then supplement with specific modules as needed.
```

---

### 2.5 GAP 8 — LTF Exception Is Partially Ambiguous

**The LTF Exception (for Coral Rupay LTF & Sapphiro LTF):**
> "Two benefits = sufficient... no need to explain all the details"

**But then (CC/verification_checklist.txt Line 570):**
> "When customer asks: If the customer asks about a specific benefit, the agent must 
> explain correctly with applicable conditions."

**Problem:** The model sometimes applies the LTF relaxation to customer QUERY responses,
which is incorrect. The relaxation is only for the INITIAL pitch, NOT for follow-up 
questions. This creates false Approvals for cases where the agent gave a wrong answer
to a customer's specific benefit question on an LTF card.

**Fix:**
```
Add explicit boundary to LTF exception:
"The LTF relaxation applies ONLY to the unprompted initial pitch.
 Once a customer asks a specific benefit question, 
 the agent MUST answer correctly with full conditions.
 Wrong answers to customer queries = Benefits = NO, regardless of LTF status."
```

---

### 2.6 GAP 9 — Timestamp-Based Rushing Detection Is Unreliable

**Current rule (DC/verification_checklist.txt Lines 351-354):**
> "Check only charges statement and the charges related statement should take the time 
> as per the regular and normal conversation. If its complete within 3–4 sec, then the 
> agent might be rushed."

**Problem:** This rule requires the model to interpret call timestamps embedded in the 
transcript. This is unreliable because:
1. STT timestamps vary in accuracy
2. "3–4 seconds" is not a consistent metric across speakers (fast vs slow speakers)
3. The model cannot reliably parse inline timestamps in Hindi/mixed-language calls

**Fix:**
```
Replace timestamp-based rushing detection with CONTENT-BASED detection:
  
  RUSHED if ANY of:
  □ Joining fee mentioned but no GST mentioned
  □ Annual fee mentioned without waiver spend threshold
  □ Both fees mentioned in same sentence with no pause (no customer response between)
  □ Customer asks "charges kya hai?" and agent responds in <20 words
  
  NOT RUSHED if:
  □ Agent pauses, customer responds (even "haan"), then agent continues charges
  □ Agent repeats charges when customer asks again
```

---

### 2.7 GAP 10 — Spelling & Formatting Errors in Prompts

Multiple spelling errors in prompt files affect model interpretation quality:

| Error Found | Correct Spelling | File | Impact |
|---|---|---|---|
| "benifits" | benefits | CC checklist (×15) | Model may not match context correctly |
| "Ruapy" | RuPay | CC checklist (×3) | Card name mismatch |
| "Shappiro" | Sapphiro | CC checklist (×4) | Card name mismatch |
| "Summerised" | Summarized | CC checklist (×6) | Comprehension degradation |
| "intrested" | interested | CC checklist (×2) | Minor |
| DC script says "Transcript" | "Call" | DC/script_adherence.txt L40 | Violates own rule (WARNING: DON'T SAY TRANSCRIPT) |

---

## PART 3: PRIORITY FIX MATRIX

| Priority | Gap | Effort | Impact | Fix |
|---|---|---|---|---|
| 🔴 P0 | DC disposition.txt is wrong product | Low | Critical | Replace with correct DC disposition file |
| 🔴 P0 | Consent language mismatch (CC+DC) | Medium | Critical | Add Tier 1/2/3 consent framework |
| 🔴 P1 | Charges rushing detection unreliable | Medium | High | Switch to content-based rushing detection |
| 🟡 P1 | STT "EXICIA" hallucination | Low | High | Add phonetic synonym correction to prompt |
| 🟡 P1 | Card name fuzzy matching | Low | High | Add synonym table to checklist prompt |
| 🟡 P2 | Contradictory consent rules CC vs DC | Medium | High | Unify consent tier framework |
| 🟡 P2 | Prompt too large (83KB) causing drift | High | Medium | Modularize into 4 sub-prompts |
| 🟢 P2 | LTF exception boundary unclear | Low | Medium | Add explicit boundary clause |
| 🟢 P3 | Spelling errors in prompts | Low | Low | Spell-check & clean all prompt files |

---

## PART 4: AGENT COACHING RECOMMENDATIONS

Based on the real CSV data, these are the top coaching priorities ranked by frequency:

### For CC Agents (409 Rework calls):
1. **#1 Priority — Consent Elicitation (78.2% of reworks):**
   Train agents to end with: *"Sir, kya main aapka upgrade request le sakta hoon?"* 
   and WAIT for a sentence-level yes, not just "Ok".

2. **#2 Priority — Benefits Accuracy (63.6% of reworks):**
   - Always state lounge spending condition (₹75,000 previous quarter)
   - Never invent benefits not in the product sheet
   - Movie tickets: ₹100 off (Coral) or ₹150 off (Rubyx) — NOT interchangeable

3. **#3 Priority — Charges Completeness (51.1% of reworks):**
   - Must say GST ("plus 18% GST") every time
   - Must mention waiver spend for paid cards MINIMUM ONCE

### For DC Agents (196 Rework calls):
1. **#1 Priority — Explicit Consent (94.9% of reworks):**
   DC rules require a HIGHER standard than CC. "Haan ji" is NEVER valid in DC.
   Agents MUST get: "Yes, upgrade kar dijiye" or equivalent full sentence.

2. **#2 Priority — Charges Clarity (83.2% of reworks):**
   DC joining AND annual fees must be stated separately, never bundled, 
   never rushed, always with GST.

---

## PART 5: METRICS DASHBOARD (Current vs Target)

| KPI | CC Current | CC Target | DC Current | DC Target |
|---|---|---|---|---|
| Overall Approval Rate | 70.1% | 82% | 32.9% | 65% |
| Consent Pass Rate | ~58% | 85% | ~5.1% | 75% |
| Charges Pass Rate | ~65% | 90% | ~44% | 85% |
| Benefits Pass Rate | ~72% | 90% | ~83% | 92% |
| Rework Rate | 29.9% | <18% | 67.1% | <35% |

---

## PART 6: CONCLUSION

The pipeline has two distinct categories of problems:

**Category A — Model Problems (Output Side):**
These generate "False Reworks" — calls that were genuinely compliant but
flagged incorrectly due to prompt logic issues. Estimated false rework rate: ~15%.
Primary fixes: DC disposition replacement, STT synonym correction, consent tier unification.

**Category B — Agent Problems (Input Side):**
These are genuine compliance failures that the model is correctly catching.
Estimated genuine rework rate: ~50% of CC reworks, ~70% of DC reworks.
Primary fixes: Agent training on consent phrasing, charges script, and LTF benefit depth.

**Recommended First Action:**
Fix the DC disposition.txt file (P0, 30 minutes of work) — it is auditing debit card
calls against Amazon credit card rules, which is a structural error affecting all 292 DC calls.
