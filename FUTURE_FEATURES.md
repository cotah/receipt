# SmartDocket — Features to Add in the Future

> This document tracks features that are **designed and ready** but intentionally held back
> for strategic launch timing. Each one is a marketing moment: "Now you have even MORE ways to earn!"

---

## 🔒 HELD BACK — Ready to Implement

### 1. Verify a Price (+5 pts)
**What it does:** User is in the supermarket, sees a product in the app, confirms the price is correct (or reports the new price).

**Anti-abuse plan (MUST implement before launch):**
- Geolocation check — user must be near a supermarket (GPS within 200m of a known store)
- User types the price they SEE (not shown our price) — if it matches ±€0.10, confirmed
- Rate limit: max 10 verifications per day per user
- Cooldown: same product can't be verified twice in 24h by same user
- Hours: only works 7am–11pm (supermarket hours)

**Why it's valuable:** Keeps our prices fresh. Crowdsourced price verification at zero cost.

**Backend status:** Endpoint exists (`POST /users/me/verify-price`, +5 pts). No frontend UI.

**Marketing angle:** "Help keep prices accurate — earn 5 pts every time you verify!"

---

### 2. Report an Offer (+10 pts)
**What it does:** User photographs a promotional shelf label in a supermarket. AI reads it (using our Shelf Price prompt with 8 Extraction Laws). Saved to collective_prices as a verified offer.

**Anti-abuse plan:**
- Photo required (can't fake without being in store)
- AI validates it's a real shelf label (not a screenshot, not a random photo)
- Duplicate detection: same product+store+price within 24h = rejected
- Rate limit: max 5 reports per day

**Why it's valuable:** Community-sourced deals. Users become our "field agents".

**Backend status:** Shelf extraction works (admin endpoint exists: `POST /admin/shelf-scan`). Need to create public endpoint + frontend screen.

**Marketing angle:** "Spotted a deal? Snap it & share — earn 10 pts!"

---

### 3. Weekly Challenges (+100 bonus pts)
**What it does:** Rotating challenges that reset every Monday. Examples:
- "Price Hunter: Scan & verify 5 products this week" (+100 bonus)
- "Barcode Hero: Link 20 barcodes this week" (+100 bonus)
- "Deal Spotter: Report 3 offers this week" (+100 bonus)

**Status:** UI card exists in Rewards screen ("Weekly Challenge" section) but challenges are hardcoded. Need dynamic challenge system.

**Backend needed:** challenges table, progress tracking, rotation logic.

---

## 🎯 RAFFLE / PRIZE SYSTEM (To be designed)

### Concept
- Points convert to raffle tickets (not direct redemption — "vai me quebrar")
- Monthly draw for signed Premier League jerseys (Henrique's collection)
- X points = 1 ticket. More tickets = higher chance.
- Drawing happens on social media (live on Palmeiras Dublin channels for engagement)

### Open questions
- How many points per ticket?
- Monthly or bi-weekly draws?
- Cap on tickets per user per draw?
- Display: show total tickets in pool + your tickets for transparency

---

## 📋 OTHER FUTURE IDEAS

### 4. Price Alerts
User sets alert: "Tell me when Chicken Breast drops below €5 at any store"
Backend partially exists (alert_service.py). Needs push notification integration.

### 5. Store Loyalty Integration
Connect Tesco Clubcard / SuperValu Real Rewards to auto-import purchases.
Complex — requires OAuth with each retailer. Long-term.

### 6. Community Price Reports
Public leaderboard of top contributors per area.
Gamification: "Dublin's #1 Price Hunter" badges.

### 7. Recipe Cost Calculator
User selects a recipe → app calculates cheapest store to buy all ingredients.
Needs recipe database or AI recipe parsing.

### 8. Price History Charts
Show 30/60/90 day price trends per product.
Data exists in price_history table. Needs frontend chart component.

### 9. Basket Optimizer
User adds 10 items to shopping list → app suggests optimal store split.
"Buy 6 items at Lidl + 4 at Tesco = save €8.50 vs all at Tesco"

---

## 📅 LAUNCH STRATEGY

**Phase 1 (NOW):** 5 earn methods live. Build user base.

**Phase 2 (Month 2):** Launch "Verify a Price" + "Report an Offer" → marketing push: "3 NEW ways to earn points!"

**Phase 3 (Month 3):** Launch Raffle system with first jersey draw → PR moment.

**Phase 4 (Month 4+):** Weekly Challenges, Price Alerts, community features.

Each phase is a reason to send a push notification, post on social media, and get press coverage.

---

*Last updated: March 2026*
*Owner: Henrique (product decisions) — "O projeto é MEU, eu mando."*
