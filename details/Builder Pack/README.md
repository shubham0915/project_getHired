# Hack to the Future — Builder Pack v0.1

**Status:** Shipped May 7, 2026 · 48 hours before Demo Day · Imperfect-but-shipped

This pack is for hackathon teams building fintech projects on Indian retail-investor problems (FD, MF, SIP, SIF, AIF, KYC, payments, customer-experience). Use any subset that helps your build. Don't feel obliged to use all of it.

---

## What's inside

```
builder-pack/
├── README.md                              ← you are here
├── recommendations.md                     ← what's NOT in this pack and why; your next-best moves
├── 01_synthetic_data/
│   ├── users_master.csv                  1,000 fake-but-realistic Indian users with PII fields
│   ├── user_segments.csv                 Segmentation labels for churn / LTV analysis
│   └── support_tickets_unstructured.csv  300 free-text customer support tickets (synthetic PII)
├── 02_customer_journey/
│   ├── web_onboarding_events.csv         Funnel events with rate-check + VKYC drop-offs
│   ├── mobile_sdk_events.csv             Mobile-SDK journey, partial-funnel pattern
│   ├── cbs_api_logs.csv                  Core Banking System API call logs (latency, errors)
│   └── vkyc_dropoffs.csv                 VKYC stage data with reason codes
├── 03_transactions/
│   ├── upi_transactions.csv              ~17k UPI txns across MCCs, P2M/P2P, success/fail
│   ├── fd_bookings.csv                   ~700 FD bookings with all attributes
│   ├── fd_rate_check_dropoffs.csv        Rate-checked-but-didn't-book funnel
│   ├── payment_gateway_txns.csv          PG txns (Razorpay/Cashfree/etc.) with failure codes
│   └── tax_form26as_style.csv            Form 26AS-shaped TDS / income data
├── 04_regulatory_refs/
│   ├── RBI_FD_DICGC_summary.md           DICGC, FD master direction, TDS, partner-bank rules
│   ├── SEBI_MF_AIF_SIF_summary.md        MF categories, AIF/SIF, SIP rules, taxation
│   ├── KYC_VKYC_norms.md                 KYC tiers, VKYC requirements, CKYC, re-KYC
│   └── DPDPA_data_handling.md            DPDPA 2023 + PII handling patterns
├── 05_voc_research/
│   └── voc_research.md                   Voice-of-customer dialogue corpus across 8 languages
├── 06_eval_sets/
│   ├── vernacular_fd_eval.json           15 cases for FD-agent regression
│   ├── mf_advisor_eval.json              12 cases for MF-advisor regression
│   ├── tax_helper_eval.json              10 cases for tax-clarification agent
│   └── general_chatbot_eval.json         10 cross-cutting safety / compliance tests
└── 07_prompt_templates/
    └── prompt_templates.md               10 production-grade prompt templates
```

## Important: data is synthetic

Every PII value in this pack — names, PAN, IFSC, bank account, phone, address, transaction IDs — is **fake**. Generated with realistic patterns so it looks and feels like Indian fintech data, but no real person's information is here.

- Names are randomly drawn from common Indian first/last name pools.
- PAN follows the AAAAA9999A format but is not a real PAN registered with the IT department.
- Aadhaar is **only stored as last-4 digits** in this pack — never use full 12-digit Aadhaar even synthetically; it normalises bad practice.
- IFSC follows real bank prefixes but the branch portion is random.
- Account numbers are random 10-14 digit strings.

The Voice-of-Customer dialogues are **synthesised representative samples** modelled on patterns from public forums, not scraped content. Treat them as *plausible* user voice for prompt-engineering and tone calibration — not as ground-truth labels.

## How to use this pack

**For an FD / MF / vernacular conversational project:**
1. Read `04_regulatory_refs/` for compliance grounding.
2. Use `05_voc_research/voc_research.md` to seed your prompt's tone + intent classifier.
3. Use `07_prompt_templates/` for system prompts, JSON output, RAG, PII redaction, eval-as-judge.
4. Run `06_eval_sets/` against your agent before demo. Aim for >80% pass on `vernacular_fd_eval.json`.
5. Pull `01_synthetic_data/users_master.csv` if you need user-context grounding.

**For a churn / segmentation / analytics project:**
1. `01_synthetic_data/users_master.csv` joined with `user_segments.csv` + `02_customer_journey/web_onboarding_events.csv` is your starting analytic layer.
2. `03_transactions/fd_rate_check_dropoffs.csv` shows the classic rate-check-no-book pattern.
3. `02_customer_journey/vkyc_dropoffs.csv` has labelled drop-reasons — great for a classification demo.
4. Aggregate `cbs_api_logs.csv` by endpoint to demo upstream-bank reliability dashboards.

**For a payments / fraud / reconciliation project:**
1. `03_transactions/upi_transactions.csv` and `payment_gateway_txns.csv` have status + failure-reason fields.
2. Cross-join with `users_master.csv` and `support_tickets_unstructured.csv` for "transaction failed → ticket raised" causal demos.

**For a KYC / data-masking project:**
1. `01_synthetic_data/support_tickets_unstructured.csv` has 300 free-text tickets stuffed with synthetic PII — perfect for a PII-redaction demo.
2. Use the prompt templates in `07_prompt_templates/prompt_templates.md` (#3 PII redaction, #4 KYC document extraction).

**For a tax / advisor project:**
1. `03_transactions/tax_form26as_style.csv` mirrors the Form-26AS shape.
2. `06_eval_sets/tax_helper_eval.json` covers FY 25-26 rules including the Jul-2024 capital-gains changes.

## Disclosures every customer-facing demo should include

- "Mutual fund investments are subject to market risks. Read all scheme-related documents carefully."
- "Past performance is not indicative of future returns."
- "Deposits are insured by DICGC up to ₹5,00,000 per depositor per bank (principal + interest combined)."
- Partner-bank name visible on FD-related screens.
- For MF: "Mutual Fund Sahi Hai" / AMFI registration of the distributor / AMC.

## Calibration notes

Numbers in this pack are tuned to feel real, not to be exhaustive:
- Real partner-bank platforms see ~25-40% drop at rate-check, ~15-25% drop at VKYC. The synthetic data here matches.
- ~92% UPI success rate matches NPCI public data.
- Income brackets weighted toward middle (₹6L-12L) to reflect the typical retail-investor onboarding profile.

## Versioning

This is **v0.1**, shipped fast for the hackathon. Known limitations:

- VoC samples are synthesised, not from real user research — flag this in your demo.
- Regulatory references are summaries, not the full circulars.
- Eval sets cover the common cases, not every edge case.
- No images or scanned documents (e.g., PAN/Aadhaar mock images) included — generate with synthetic-document tools if your project needs them.
- No streaming / real-time data feeds; all batch CSVs.

If we have time post-hackathon, **v0.2** would add: real-rate APIs, image-OCR ground truth, multilingual TTS samples, and a cleaner schema for the journey events.

---

*Questions: ping the program team in your cohort WhatsApp group.*
