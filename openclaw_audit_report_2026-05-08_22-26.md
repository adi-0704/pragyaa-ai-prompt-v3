# OpenClaw Audit Automation Report
**Generated:** 2026-05-08 22:26 | **Product:** ICICI DC Upgrade

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Total Cases | 751 |
| Agreement Rate | 48.9% |
| AI Approval Rate | 30.1% |
| Verifier Approval Rate | 75.4% |
| **Approval Gap** | **45.3%** |
| False Reworks (AI too strict) | 358 |
| False Approves (AI too lenient) | 17 |

> **Root Cause:** AI rejects 45.3% more calls than human verifiers.
> Primary drivers: Consent strictness (95.3%), Charges rushing detection (83.0%), Pitch pace (55.9%)

---

## 2. Parameter-Level Failure Analysis (False Reworks)

| Parameter | Failures | Rate | Severity |
|---|---|---|---|
| Consent Taken Met | 341 | 95.3% | CRITICAL |
| Charges Explained Met | 297 | 83.0% | CRITICAL |
| Pitch Pace | 200 | 55.9% | CRITICAL |
| Benefits Explained Met | 93 | 26.0% | HIGH |
| Card Variant Met | 47 | 13.1% | MEDIUM |
| Pitch Modulation | 26 | 7.3% | MEDIUM |

---

## 3. Root Cause → Fix Mapping

### 3.1 Consent Taken Met (CRITICAL)
- **Root Cause:** AI treats passive Hindi agreement as invalid consent
- **Fix:** EXPAND Tier 2 consent: Accept 'Okay', 'Theek hai', 'Haan ji', 'Ji' as valid consent IF agent completed full pitch (benefits + charges) before customer response. Pattern breakdown: passive_agreement=310, no_explicit_ask=80, backchannel=96
- **Status:** ✅ Already in prompt

### 3.2 Charges Explained Met (CRITICAL)
- **Root Cause:** AI penalizes speed/style of delivery, not factual accuracy
- **Fix:** SWITCH from speed-based to content-based charges evaluation. Pass charges if ₹699+GST joining AND annual fees stated correctly, regardless of delivery speed. Only fail for wrong amounts or total omission. Pattern breakdown: rushed=227, confusing=241, missing_gst=283
- **Status:** ✅ Already in prompt

### 3.3 Pitch Pace (CRITICAL)
- **Root Cause:** AI pace threshold is stricter than human tolerance
- **Fix:** Only fail Pitch Pace if customer EXPLICITLY asks to repeat or slow down. Normal conversational Hindi speed is acceptable.
- **Status:** ✅ Already in prompt

### 3.4 Benefits Explained Met (HIGH)
- **Root Cause:** AI requires too many benefits to be mentioned
- **Fix:** Pass benefits if agent mentions ≥2 core benefits accurately.
- **Status:** ✅ Already in prompt

### 3.5 Card Variant Met (MEDIUM)
- **Root Cause:** AI fails on card name variations
- **Fix:** Add fuzzy matching: 'Coral card'/'Updated Coral'/'Coral Visa' → Coral Debit Card
- **Status:** 🔴 NEEDS ADDITION

### 3.6 Pitch Modulation (MEDIUM)
- **Root Cause:** AI too strict on Pitch Modulation
- **Fix:** Align Pitch Modulation threshold with human verifier standards
- **Status:** 🔴 NEEDS ADDITION

### 3.7 False Approves (HIGH)
- **Root Cause:** AI approved 17 calls that verifiers rejected
- **Fix:** Add guardrails for: RPC not confirmed; Charges Not proper; Wrong Information; Need to do fresh call; Drop Off Script Not Followed; Charges & Consent Issue
- **Status:** 🔴 NEEDS ADDITION

---

## 4. False Approve Cases (AI missed these)

Verifier rejected but AI approved — these need NEW guardrails:

- RPC not confirmed
- Consent not proper
- Charges Not proper
- Wrong Information
- Need to do fresh call
- Drop Off Script Not Followed
- Charges & Consent Issue

---

## 5. OpenClaw/Hermes Prompt Evolution Instructions

### Skill: `dc_audit_prompt_evolver`

```json
{
  "skill_name": "dc_audit_prompt_evolver",
  "trigger": "new_excel_feedback_received",
  "input": "AI vs Verifier audit Excel file",
  "steps": [
    "1. Ingest Excel → extract Raw Data sheet",
    "2. Compute: false_rework_rate, false_approve_rate, param_failures",
    "3. Compare param_failures against current prompt rules",
    "4. Generate delta patches for parameters with >10% failure rate",
    "5. Apply patches to prompt file (versioned)",
    "6. Log changes to evolution_history.json"
  ],
  "output": "Updated prompt file + change report",
  "feedback_loop": {
    "metric": "agreement_rate",
    "target": ">85%",
    "current": "48.9%",
    "rerun_if_below": true
  }
}
```

### Current Calibration Targets:

| Parameter | Current AI Pass% | Target Pass% | Delta |
|---|---|---|---|
| Consent | ~5% | >90% | Expand Tier 2 |
| Charges | ~17% | >85% | Content-based eval |
| Pitch Pace | ~44% | >90% | Customer-signal only |
| Benefits | ~74% | >90% | ≥2 benefits rule |

