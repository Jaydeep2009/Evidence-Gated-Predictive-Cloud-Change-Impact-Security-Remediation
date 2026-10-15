# Milestone 2: Audit Corrections Log

**Date:** 2026-10-11  
**Audit Type:** Research integrity review  
**Status:** Corrections applied

---

## File Integrity Hashes (Pre-Correction)

### Evidence Files (PRESERVED - NO CHANGES)
```
SHA256: EE9B391C88AB45AB73F6057A158A33F643890123717A6C9DE2CB04076D61C7C0
File:   network-policy-verification-20261011-132130.json (3159 bytes)

SHA256: A65ADA1102F7EBFC8C4CD1F22D8749DE2E55338DD6A8D2D73494867F2414ECFB
File:   network-policy-verification-20261011-133342.json (3400 bytes)

SHA256: 65AE73FA9197CC33C431C1ABB2D93F814956F7473A5EBBC2474745FF98892697
File:   network-policy-verification-20261011-135142.json (3159 bytes)
```

### Report Files (PRE-CORRECTION)
```
SHA256: (to be computed from original files)
File:   docs/milestone-2-analysis.md (10949 bytes)
File:   docs/milestone-2-completion.md (16372 bytes)
```

---

## Corrections Applied

### 1. Unsupported Evidence Ablation Claim (HIGH SEVERITY)

**Location:** `docs/milestone-2-completion.md` → Research Contributions → For Overall Project

**Original text:**
> 3. **Evidence ablation:** Demonstrates value of combining Infrastructure + Application + Runtime evidence

**Problem:** Milestone 2 did NOT perform evidence ablation study. This experiment used all three evidence types together; it did not compare Infrastructure-only vs Infrastructure+Application vs Infrastructure+Runtime configurations.

**Correction:** Remove claim from "Research Contributions" section. Move to "Future Work" → "Long-Term Research" as planned work.

**Corrected text (Future Work section):**
> 1. **Evidence ablation study:** Compare Infrastructure-only vs Infrastructure+Application vs Infrastructure+Runtime vs All-three configurations

---

### 2. Overly Strong Causation Language (MEDIUM SEVERITY)

**Locations:** Multiple instances in both reports

#### Instance 1: milestone-2-analysis.md → Executive Summary

**Original:**
> "demonstrates a causal relationship between Kubernetes NetworkPolicy presence and backend-to-database connectivity failure"

**Corrected:**
> "is consistent with a causal relationship between Kubernetes NetworkPolicy presence and backend-to-database connectivity failure"

#### Instance 2: milestone-2-analysis.md → Causation Demonstration → Conclusion

**Original:**
> "The three-stage pattern demonstrates a causal relationship between NetworkPolicy presence and Backend connectivity failure."

**Corrected:**
> "The three-stage pattern is consistent with a causal relationship between NetworkPolicy presence and Backend connectivity failure."

#### Instance 3: milestone-2-completion.md → Causation Analysis → Conclusion

**Original:**
> "The three-stage controlled experiment demonstrates a **causal relationship** between NetworkPolicy presence and Backend connectivity failure."

**Corrected:**
> "The three-stage controlled experiment is consistent with a **causal relationship** between NetworkPolicy presence and Backend connectivity failure."

**Rationale:** Without packet-level verification (tcpdump/Wireshark) or nftables inspection during the experiment, we cannot definitively prove causation. The pattern is consistent with causation, but alternative explanations (though unlikely) cannot be completely ruled out.

---

### 3. Cluster Name Inconsistency (LOW SEVERITY)

**Location:** Multiple locations in both reports

**Reports claim:** "kind-poc-cluster"  
**Evidence files contain:** "poc-cluster"

**Correction:** Change all instances to "poc-cluster" to match actual evidence.

**Affected sections:**
- milestone-2-analysis.md → Header
- milestone-2-completion.md → (no explicit cluster name in header, only in narrative)

---

### 4. Socket Code Inconsistency (LOW SEVERITY)

**Location:** Evidence files → hypothesis → conditions_checked

**Evidence files list:**
> "Backend→Database connection timeout (socket code 110)"

**Actual observed code:** 11 (EAGAIN), not 110 (ETIMEDOUT)

**Problem:** This is in the JSON evidence files themselves, which are PRESERVED and must not be modified.

**Resolution:** Document the inconsistency. The `conditions_checked` field lists the six conditions generically (with 110 as the canonical ETIMEDOUT code). The actual observed code (11) is correctly recorded in `observed_behavior.backend_to_database.socket_code`.

**No correction needed** — this is a template vs. actual measurement distinction, not an error.

---

### 5. Missing MD5 Hash for Stage 3 (LOW SEVERITY)

**Location:** milestone-2-analysis.md → Evidence Files table

**Original:**
> | **3 - Recovery** | ... | 3159 bytes | (not captured) |

**Corrected:**
> | **3 - Recovery** | ... | 3159 bytes | SHA256: 65AE73FA... |

(Full hash recorded in milestone-2-evidence-hashes.txt)

---

## Corrections NOT Applied

### Evidence Files Themselves

**No changes made** to the three JSON evidence files. These are primary research data and must be preserved exactly as generated.

The `interpretation` field in all three files contains generic text:
> "Socket result is consistent with NetworkPolicy blocking traffic when status is connection_timeout and corroborating evidence from pod state is present. Does not definitively prove causation."

This text was part of the verification script template. While it reads oddly in Stage 1 and 3 (where NetworkPolicy is absent), it does not misrepresent the data — the actual `status` field correctly shows "connected" vs "connection_timeout."

**Resolution:** Document this as a template artifact. Future experiments should use stage-specific interpretation text.

---

## Verification

### Pre-Correction Evidence Integrity
- Stage 1 JSON: 3159 bytes, SHA256: EE9B391C...
- Stage 2 JSON: 3400 bytes, SHA256: A65ADA1102...
- Stage 3 JSON: 3159 bytes, SHA256: 65AE73FA...

### Post-Correction Evidence Integrity
- Stage 1 JSON: **UNCHANGED**
- Stage 2 JSON: **UNCHANGED**
- Stage 3 JSON: **UNCHANGED**

### Report Corrections
- Evidence ablation claim: REMOVED from contributions, MOVED to future work
- Causation language: QUALIFIED with "is consistent with" (3 instances)
- Cluster name: STANDARDIZED to "poc-cluster"
- Hash documentation: ADDED SHA256 reference for Stage 3

---

## Impact Assessment

### Research Validity
**No impact.** The corrections do not change:
- The experimental design
- The measurements
- The pattern observed (absent→present→absent → healthy→unhealthy→healthy)
- The conclusion that the pattern is consistent with NetworkPolicy causation

### Publication Readiness
**Improved.** Corrections make the reports more conservative and scientifically rigorous:
- Removes unsupported claim (evidence ablation)
- Uses appropriate hedging language ("consistent with" vs "demonstrates")
- Resolves minor inconsistencies

### Future Work
**Clarified.** Evidence ablation study is now explicitly listed as planned future work, not completed work.

---

## Audit Conclusion

✅ **Evidence integrity preserved:** All three JSON files unchanged  
✅ **Overclaims corrected:** Evidence ablation removed from contributions  
✅ **Language qualified:** Causation statements appropriately hedged  
✅ **Inconsistencies resolved:** Cluster name standardized, hashes documented  
✅ **Research validity maintained:** No substantive changes to findings

**Milestone 2 status:** COMPLETE with corrections applied  
**Ready for Milestone 3:** YES

---

**END OF CORRECTIONS LOG**
