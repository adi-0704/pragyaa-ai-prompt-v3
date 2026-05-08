# Audit Analysis & Optimization Report: pragyaa.ai

## 1. Overview
This report analyzes the discrepancy between the **Audio Input** (Agent Performance) and the **Model Output** (Automated Compliance Audit) within the ICICI Credit Card/Debit Card upgrade pipeline.

---

## 2. Input Analysis (The "Audio/Transcript")
The input side faces challenges related to human variance and technical transcription noise.

### A. Compliance vs. Sales Tension
Agents are primarily motivated to close the sale, which often leads to "Critical Fail" omissions:
*   **Omission of Waiver Criteria:** Agents mention the card is "First Year Free" but forget to state the specific spend required to waive the second-year fee (e.g., Rs. 3,500 + GST).
*   **GST Disclosures:** The mention of "18% GST" is frequently missed or glossed over.

### B. Transcription (STT) Hallucinations
*   **Phonetic Errors:** "ICICI" -> "EXICIA", "Sapphiro" -> "Sapphire".
*   **Logic Impact:** When the model sees "EXICIA" in the transcript, it searches the allowed card list and fails the lead because "EXICIA" is not a valid bank product.

---

## 3. Output Analysis (The "Auditor Logic")
The model acts as a "Strict Compliance Officer," which creates a high volume of "Rework" statuses.

### A. Rigid Keyword Matching
The model currently looks for exact matches. 
*   **Example:** If the prompt expects `SAPPHIRO VISA-RUPAY FULL FEE` and the agent says `Sapphiro Visa Card`, the model flags a mismatch.

### B. Consent Categorization
The model struggles with "Passive Agreement." 
*   **Current State:** If a customer says "Proceed" or "Theek hai" instead of a clear "Yes, I agree to the upgrade," the model often marks it as "Incomplete Consent."

---

## 4. Actionable Suggestions to "Bridge the Gap"

### Suggestion 1: Fuzzy Card Matching (Immediate Fix)
Update the audit prompt to map common synonyms to canonical card names.
*   *Implementation:* `IF transcript contains ('Sapphire' OR 'Sapphiro' OR 'Super Saver') AND benefits match Profile X -> APPROVE NAME.`

### Suggestion 2: "Soft Fail" vs "Hard Fail"
Differentiate between "Inaccurate Charges" (Hard Fail) and "Incomplete Phrasing" (Soft Fail).
*   **Hard Fail:** Agent says the card is Free when it has a 5k fee.
*   **Soft Fail:** Agent mentions the fee but forgets to mention "plus GST."

### Suggestion 3: Feature-Based Verification
Instead of checking for the Card Name *string*, check if the **Benefits and Charges** explained by the agent match the specific card profile. This makes the audit "STT-Resistant."

---

## 5. Next Steps for Implementation
1.  **Refine Prompt Logic:** Incorporate "Synonym Lists" for all 16 CC card variants.
2.  **Adjust Consent Threshold:** Allow affirmative conversational fillers as valid consent if no subsequent objections are raised.
3.  **Data Refresh:** Confirm the latest waiver spends (1L vs 6L) and update the ground truth in the prompt instructions.
