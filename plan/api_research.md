# External API Research

Based on the architecture diagram, the following external API categories are required.
This document compares options and records the selected API for each category.

---

## 1. Weather API

**Used by:** Weather Agent via `weather_tool`

| API                   | Free Tier                      | Rate Limit (free)     | Auth         | Aviation-Specific | Notes |
|-----------------------|--------------------------------|-----------------------|--------------|:-----------------:|-------|
| **OpenWeatherMap**    | Yes — Current + 5-day forecast | 1,000 calls/day       | API Key      | Partial           | METAR not native but widely used |
| Tomorrow.io           | Yes — limited calls            | 500 calls/day         | API Key      | Yes               | Good aviation fields (wind shear, visibility) |
| CheckWX (Aviation WX) | Yes                            | 100 calls/month       | API Key      | ✓ Full METAR/TAF  | Purpose-built aviation weather |
| aviationweather.gov   | Completely free                | Unlimited             | None         | ✓ Full METAR/TAF  | US Gov service, no auth required |

**Selected:** `OpenWeatherMap` (primary) + `aviationweather.gov` (METAR/TAF supplement)

- OpenWeatherMap for current conditions and forecasts
- aviationweather.gov for raw METAR and TAF strings (free, no auth, REST)
- Combined gives full weather picture needed by aviation ops

**Endpoints used:**
```
GET https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}
GET https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={key}
GET https://aviationweather.gov/api/data/metar?ids={ICAO}&format=json
GET https://aviationweather.gov/api/data/taf?ids={ICAO}&format=json
```

---

## 2. Flight Status API

**Used by:** Flight Agent via `flight_tool`

| API              | Free Tier                      | Rate Limit (free) | Auth    | Real-time | Historical | Notes |
|------------------|--------------------------------|-------------------|---------|:---------:|:----------:|-------|
| **AviationStack**| Yes — 100 calls/month          | 100/month         | API Key | ✓         | Limited    | Simple REST, easy to integrate |
| FlightAware AeroAPI | No free tier (trial only)   | —                 | API Key | ✓         | ✓          | Industry standard, expensive |
| OAG              | No free tier                   | —                 | API Key | ✓         | ✓          | Enterprise only |
| OpenSky Network  | Free                           | 400 req/day       | Optional| ✓         | ✓          | Community data, less structured |

**Selected:** `AviationStack` for free-tier integration + `OpenSky Network` as fallback

- AviationStack provides clean structured JSON for flight status, delay reason, and route
- OpenSky as secondary for real-time position data if needed

**Endpoints used:**
```
GET http://api.aviationstack.com/v1/flights?flight_iata={FLIGHT}&access_key={key}
GET http://api.aviationstack.com/v1/airports?iata_code={IATA}&access_key={key}
```

---

## 3. Airport Operations API

**Used by:** Runway Agent via `airport_tool`

| API                   | Free Tier | Rate Limit | Auth    | NOTAM | Runway Data | Notes |
|-----------------------|-----------|------------|---------|:-----:|:-----------:|-------|
| **aviationweather.gov** | Free    | Unlimited  | None    | ✓     | Partial     | NOTAMs available via NOTAM API |
| FAA NOTAM API         | Free      | Unlimited  | None    | ✓     | No          | US-only NOTAMs |
| AIP / EUROCONTROL     | Free (public) | Limited | None  | ✓     | Yes         | Europe focused |
| AviationStack Airports| Yes       | 100/month  | API Key | No    | Partial     | Basic airport info only |

**Selected:** `aviationweather.gov` for NOTAMs + `AviationStack` for airport metadata

- Real runway-level operational data is not available publicly — supplement with mock data
- NOTAMs from aviationweather.gov cover flight restrictions and runway closures

**Endpoints used:**
```
GET https://aviationweather.gov/api/data/notam?icaos={ICAO}&format=json
GET http://api.aviationstack.com/v1/airports?iata_code={IATA}&access_key={key}
```

---

## 4. Booking / Seat Inventory API

**Used by:** Rebooking Agent via `booking_tool`

> No public free-tier booking inventory API exists (Amadeus/Sabre/Travelport are enterprise and paid).

**Decision:** Implement a realistic mock booking service in `src/mock_services/booking_service.py`

Mock should simulate:
- Seat inventory per flight
- Fare class availability
- Rebooking eligibility check
- Seat assignment

---

## 5. Fleet / Aircraft Management API

**Used by:** Aircraft Agent via `fleet_tool`

> No public free-tier fleet management API exists. Internal airline systems (AMOS, SITA) are proprietary.

**Decision:** Implement a realistic mock fleet service in `src/mock_services/fleet_service.py`

Mock should simulate:
- Aircraft registration and model
- Airworthiness status
- Last maintenance date and next due
- Fuel state
- Current rotation schedule

---

## 6. Passenger Service System (PSS) API

**Used by:** Passenger Agent via `passenger_service`

> Real PSS APIs (Amadeus Altéa, Sabre, Travelport) are enterprise-only.

**Decision:** Implement a realistic mock PSS in `src/mock_services/passenger_service.py`

Mock should simulate:
- Full passenger manifest for a flight
- Cabin class breakdown
- VIP / FFP tier flags
- Special assistance codes (WCHR, UM, BLND, DEAF, MEDA)
- Onward connection details

---

## 7. Notification API

**Used by:** (Optional) Post-decision notifications to passengers

| API           | Free Tier                 | Channels       | Auth    |
|---------------|---------------------------|----------------|---------|
| **SendGrid**  | 100 emails/day free       | Email          | API Key |
| Twilio        | Trial credits ($15)       | SMS, WhatsApp  | API Key |
| Firebase FCM  | Free                      | Push           | API Key |

**Selected:** `SendGrid` for email notifications (demo only, not critical path)

---

## Summary — API Selection

| Agent           | Tool             | API / Service                          | Type     |
|-----------------|------------------|----------------------------------------|----------|
| Weather Agent   | weather_tool     | OpenWeatherMap + aviationweather.gov   | Real API |
| Flight Agent    | flight_tool      | AviationStack + OpenSky                | Real API |
| Runway Agent    | airport_tool     | aviationweather.gov NOTAMs + AviationStack | Real API |
| Aircraft Agent  | fleet_tool       | Mock Fleet Service                     | Mock     |
| Passenger Agent | passenger_svc    | Mock PSS Service                       | Mock     |
| Rebooking Agent | booking_tool     | Mock Booking Service                   | Mock     |
| All Agents      | db2_search_tool  | Haystack + IBM Db2                     | Internal |

---

## Environment Variables Required

```env
OPENWEATHER_API_KEY=
AVIATIONSTACK_API_KEY=
SENDGRID_API_KEY=
```

No keys required for: aviationweather.gov, OpenSky Network
