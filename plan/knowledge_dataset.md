# Enterprise Knowledge Dataset Plan

This document defines the airline enterprise knowledge base that Pawan will create.
All documents are stored in `src/data/` and ingested into IBM Db2 via the Haystack pipeline.

---

## Why This Dataset Exists

Agents must never hallucinate airline policies.
Whenever a policy, SOP, regulation, or procedure is needed, agents call the `db2_search_tool`
which performs semantic search over this dataset.

---

## Folder Structure

```
src/data/
├── sops/
│   ├── flight_delay_sop.md
│   ├── diversion_sop.md
│   ├── cancellation_sop.md
│   ├── ground_stop_sop.md
│   └── weather_operations_sop.md
│
├── policies/
│   ├── passenger_rights_policy.md
│   ├── compensation_policy.md
│   ├── rebooking_policy.md
│   ├── refund_policy.md
│   └── special_assistance_policy.md
│
├── manuals/
│   ├── crew_operations_manual.md
│   ├── ground_operations_manual.md
│   ├── aircraft_maintenance_manual.md
│   └── airport_operations_manual.md
│
├── regulations/
│   ├── eu261_2004_regulation.md
│   ├── dgca_passenger_charter.md
│   └── iata_delay_codes.md
│
└── faqs/
    ├── passenger_faq.md
    ├── crew_faq.md
    └── operations_faq.md
```

**Total minimum:** 20 documents

---

## Document Specifications

### sops/flight_delay_sop.md
**Purpose:** Step-by-step procedures for handling a flight delay
**Must cover:**
- Delay notification timeline (gate agents, passengers, crew)
- Decision thresholds (delay vs. cancel vs. divert)
- Coordination checklist (ops, crew, catering, fuel, ground)
- Passenger communication script templates
- Escalation matrix

---

### sops/diversion_sop.md
**Purpose:** Procedures for mid-flight or pre-departure diversion
**Must cover:**
- Captain's authority and responsibilities
- Ground coordination at alternate airport
- Passenger handling at alternate airport
- Crew duty time considerations
- Recovery procedures

---

### sops/cancellation_sop.md
**Purpose:** Full flight cancellation handling procedures
**Must cover:**
- Cancellation decision authority
- Passenger re-accommodation priority
- Refund vs. rebooking procedures
- Station manager responsibilities
- Documentation requirements

---

### sops/ground_stop_sop.md
**Purpose:** Handling ATC-issued ground stops
**Must cover:**
- What triggers a ground stop
- Passenger communication during ground stop
- Crew rest management
- Aircraft fueling decisions
- Estimated clearance handling

---

### sops/weather_operations_sop.md
**Purpose:** Operating in adverse weather conditions
**Must cover:**
- Visibility and crosswind limits by aircraft type
- De-icing procedures and holdover times
- Low-visibility approach procedures
- Thunderstorm avoidance rules
- Contaminated runway operations

---

### policies/passenger_rights_policy.md
**Purpose:** Summary of passenger rights enforced by the airline
**Must cover:**
- Rights during delay (meals, accommodation, communication)
- Rights during cancellation
- Rights during denied boarding
- Compensation thresholds by delay duration
- Distinction between extraordinary circumstances and controllable delays

---

### policies/compensation_policy.md
**Purpose:** Precise compensation rules
**Must cover:**
- Compensation matrix:
  - Delay < 2 hours: No compensation
  - Delay 2–3 hours: Meal voucher
  - Delay 3–5 hours: Meal + hotel (if overnight)
  - Delay > 5 hours: Full refund option + above
- EU261/2004 cash amounts by distance band
- Applicability (domestic vs. international)
- Extraordinary circumstances exclusions (weather, ATC, security)

---

### policies/rebooking_policy.md
**Purpose:** Rules for rebooking passengers during disruption
**Must cover:**
- Priority order (medical, UM, premium, economy)
- Rebooking on partner airlines
- Endorsement rules
- Voluntary vs. involuntary rebooking
- No-show protection during disruption

---

### policies/refund_policy.md
**Purpose:** Refund entitlements and processing rules
**Must cover:**
- Full refund triggers
- Partial refund rules
- Refund timeline commitments
- Original form of payment rule
- Ancillary refund rules (seats, bags, meals)

---

### policies/special_assistance_policy.md
**Purpose:** Handling passengers with special needs during disruption
**Must cover:**
- WCHR / WCHS / WCHC handling at alternate airports
- UM protocols during rebooking
- MEDA case escalation
- Service animal handling
- Priority boarding during recovery

---

### manuals/crew_operations_manual.md
**Purpose:** Crew duties and responsibilities during disruption
**Must cover:**
- FDP (Flight Duty Period) limits
- Rest requirements triggering crew swap
- Cabin crew briefing procedures during delay
- IFE and catering during extended ground delay
- Crew communication hierarchy

---

### manuals/ground_operations_manual.md
**Purpose:** Ground staff procedures during disruption
**Must cover:**
- Gate management during delay
- Checked baggage handling during cancellation
- Ground transportation for passengers
- Liaison with catering, fuel, and cleaning vendors
- Departure control system (DCS) procedures

---

### manuals/aircraft_maintenance_manual.md
**Purpose:** Maintenance decision-making during operations
**Must cover:**
- MEL (Minimum Equipment List) dispatch decisions
- AOG (Aircraft on Ground) procedures
- Ferry flight authorization
- Substitute aircraft acceptance checklist
- Fuel contamination procedures

---

### manuals/airport_operations_manual.md
**Purpose:** Airport-specific operational guidelines
**Must cover:**
- NOTAM interpretation guide
- Runway condition codes (RCAM)
- Slot coordination during disruption
- Remote parking and bussing procedures
- Airport emergency plan interface

---

### regulations/eu261_2004_regulation.md
**Purpose:** Full text summary of EU passenger rights regulation
**Must cover:**
- Article 5 — Cancellation
- Article 6 — Delay
- Article 7 — Right to compensation (€250/€400/€600)
- Article 8 — Right to reimbursement or re-routing
- Article 9 — Right to care (meals, hotel, communication)
- Extraordinary circumstances definition

---

### regulations/dgca_passenger_charter.md
**Purpose:** DGCA (India) passenger rights guidelines
**Must cover:**
- Compensation for domestic Indian flights
- Denied boarding rules
- Tarmac delay rules
- Refund timelines mandated by DGCA
- Applicability to international departures from India

---

### regulations/iata_delay_codes.md
**Purpose:** IATA standard delay and cancellation codes (AHM730)
**Must cover:**
- Code range 11–19: Passenger and Baggage
- Code range 21–29: Cargo and Mail
- Code range 31–39: Aircraft and Ramp
- Code range 41–49: Technical and Aircraft Equipment
- Code range 51–59: Damage to Aircraft
- Code range 61–69: Flight Operations / Crew
- Code range 71–79: Weather
- Code range 81–89: ATC
- Code range 91–99: Reactionary / Miscellaneous

---

### faqs/passenger_faq.md
**Purpose:** Common passenger questions and official answers during disruption
**Must cover:**
- What are my rights if my flight is delayed?
- Can I get a refund if I choose not to travel?
- What meals am I entitled to?
- Will the airline pay for my hotel?
- How do I claim compensation?
- What counts as extraordinary circumstances?

---

### faqs/crew_faq.md
**Purpose:** FAQ for cabin and flight crew during disruption
**Must cover:**
- What happens to my duty time if the flight is delayed?
- Who do I contact for a crew swap?
- What do I tell passengers during a long delay?
- What are my responsibilities during a diversion?

---

### faqs/operations_faq.md
**Purpose:** FAQ for ground operations and station managers
**Must cover:**
- Who authorizes a cancellation?
- How do I handle a ground stop?
- What is the escalation path for a 3-hour delay?
- How do I coordinate with catering for an extended delay?

---

## Content Guidelines for Pawan

1. Write each document in plain English markdown
2. Aim for 400–800 words per document (suitable for chunking)
3. Use realistic airline terminology (IATA codes, ICAO, MEL, FDP, etc.)
4. Base content on publicly available IATA, EU, and DGCA guidelines
5. Do not copy-paste official documents — paraphrase into internal policy style
6. Each document should have a clear header, section titles, and bullet lists where appropriate
7. Include realistic thresholds, timelines, and numeric values (e.g., "2-hour meal voucher threshold")

---

## Haystack Ingestion Parameters

| Parameter           | Value                        |
|---------------------|------------------------------|
| Chunk size          | 512 tokens                   |
| Chunk overlap       | 50 tokens                    |
| Embedding model     | `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) |
| Retrieval top-k     | 5                            |
| Reranker            | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Storage             | IBM Db2 Vector Store + Document Store |
