# Ground Stop Handling Standard Operating Procedure

**Document ID:** SOP-OPS-005  
**Version:** 1.8  
**Effective Date:** 2024-01-15  
**Owner:** Director Network Control  

---

## 1. Purpose

This SOP defines procedures for handling ATC-issued Ground Stops (GS) and Ground Delay Programs (GDP). A ground stop prohibits departure of one or more flights to a specific destination due to capacity, weather, or security constraints at the destination or en-route.

---

## 2. What Triggers a Ground Stop

Ground stops are issued by:
- **ATC / ATFM (Air Traffic Flow Management)** — destination capacity exceeded
- **Weather** — severe weather at destination or en-route making acceptance impossible
- **Airport authority** — runway closure, security event, power failure
- **Government order** — security threat, VIP movement, airspace restriction

Upon receiving a ground stop EDCT (Estimated Departure Clearance Time):
- All affected flights are assigned a revised EDCT slot
- Departure is prohibited until the EDCT window (EDCT ± 5 minutes)

---

## 3. Immediate Response (T+0)

1. Operations Controller receives GS notification via ATFM system or ATC
2. NCC logs GS in OpsSystem with:
   - Affected airport(s)
   - EDCT times per flight
   - Estimated duration
3. All affected gate agents notified within 5 minutes
4. Passenger announcement issued at gate

---

## 4. Passenger Communication During Ground Stop

### 4.1 Initial Announcement (first 15 minutes)
> "Ladies and gentlemen, ATC has issued a ground stop for flights to [destination]. Your flight will depart as soon as clearance is received. Our current estimated departure time is [EDCT]. We appreciate your patience."

### 4.2 Repeat Announcements
- Every 20 minutes if GS continues
- Immediately if EDCT changes (earlier or later)

### 4.3 If Ground Stop Exceeds 90 Minutes
- Issue meal or refreshment vouchers (same thresholds as delay SOP)
- Offer passengers option to deplane if aircraft has not pushed back
- Rebooking desk activated if GS forecast > 3 hours

---

## 5. Crew Rest Management

Ground stops do not pause crew FDP (Flight Duty Period). The clock continues from original sign-on.

**Management actions:**
- At T+90 minutes of GS: NCC proactively calculates remaining FDP for all crew on affected flights
- If projected total FDP (including GS duration + flight time) will be breached: initiate crew swap immediately, do not wait for GS to lift
- Crew swap lead time is typically 2–3 hours; act early

**Crew rest facilities:**
- Crew rest room at airport if available
- Hotel transport authorised if GS exceeds 4 hours and no rest facility at airport

---

## 6. Aircraft Fueling Decisions

A ground stop creates a fuel management challenge: fuel loaded for departure may evaporate holding time value, and additional fuel burn from APU must be tracked.

| GS Duration | Fuel Action |
|-------------|-------------|
| < 60 minutes | No action, monitor fuel state |
| 60–90 minutes | Dispatch recalculates fuel requirement |
| > 90 minutes | Contact refuelling team for top-up assessment |
| > 3 hours | Full new fuel plan required before departure |

**Note:** Dispatch retains authority over fuel decision. Captain may request additional fuel above dispatch minimum.

---

## 7. Handling Estimated Clearance Changes

EDCT times are regularly revised by ATFM. When EDCT changes:

1. Operations Controller updates OpsSystem immediately
2. Gate agents notified
3. Passenger announcement made within 5 minutes of EDCT change
4. Crew duty time recalculated if EDCT moves forward by > 1 hour
5. Ground handler given revised push-back time (EDCT – 20 minutes)

---

## 8. Ground Stop Lifting — Departure Sequence

When ground stop is lifted or EDCT window is reached:

1. Dispatch confirms final fuel plan and clearance
2. Ground handler contacted for immediate push-back positioning
3. Boarding completed (if passengers deplaned, expedited re-boarding begins)
4. Crew confirms readiness and no FDP breach
5. ATC clearance requested
6. Push-back and departure executed within EDCT window (± 5 minutes)

---

## 9. Documentation

- GS event log: receipt time, EDCT series, lift time
- Passenger communication log
- Crew FDP records
- Fuel load history
- Final IATA delay code: Code 81–89 (ATC) with applicable sub-code
