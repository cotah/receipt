# SmartDocket — Pre-Launch QA Checklist
## App Store & Google Play Submission Readiness

**Date:** 01 April 2026
**Version:** 1.0.0
**Tester:** Henrique (Manual) + Claude (Automated)

---

## PART 1: AUTOMATED ANALYSIS RESULTS

### ✅ Backend Tests: 94/94 PASSED
### ✅ TypeScript: 0 errors
### ✅ Security: No exposed secrets in code

### ⚠️ Issues Found (Non-blocking)

| # | Severity | Issue | Location | Status |
|---|----------|-------|----------|--------|
| 1 | Minor | 5 orphan component files (unused) | `PriceCompare.tsx`, `PriceHistory.tsx`, `Toast.tsx`, `useAlerts.ts`, `useTabSwipe.ts` | Can remove later |
| 2 | Minor | Hardcoded Railway URL for Pro upgrade | `profile.tsx:438` | Should use env var |
| 3 | Minor | Some unused imports in frontend files | Various | Cosmetic only |
| 4 | Info | Login/Register async calls lack explicit try-catch | `login.tsx`, `register.tsx` | Parent catches errors |

---

## PART 2: MANUAL TEST CHECKLIST

### Instructions
- Test on **iPhone** (Expo Go) — Apple is the strictest reviewer
- For each test: **PASS** ✅ or **FAIL** ❌ + screenshot
- Test with **Wi-Fi ON** and **Wi-Fi OFF** (airplane mode)
- Every screen must render without crash
- Every button must do something (no dead buttons)

---

### 🔐 A. AUTHENTICATION (7 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| A1 | Fresh install onboarding | Delete app → reinstall → open | 5 onboarding slides appear, can swipe through, "Get Started" button works | |
| A2 | Register with email | Onboarding → Register → fill name, email, password | Account created, redirects to Home | |
| A3 | Login with email | Logout → Login → enter email + password | Login success, Home screen loads with data | |
| A4 | Login with Google | Login screen → "Continue with Google" button | Google OAuth opens, returns to app, Home loads | |
| A5 | Forgot password | Login → "Forgot password" → enter email | "Check your email" message appears | |
| A6 | Logout | Profile → Scroll down → "Sign Out" | Returns to Login screen, data cleared | |
| A7 | Session persistence | Login → close app completely → reopen | Still logged in, Home loads normally | |

---

### 🏠 B. HOME SCREEN (10 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| B1 | Home loads | Open app (logged in) | "Good morning/afternoon" + name + stats cards | |
| B2 | Spent this month | Check main green card | Shows total spent THIS MONTH (resets on 1st) | |
| B3 | Stats row | Check Shops/Discounts/Saved cards | Numbers match reality (not negative, not zero if have receipts) | |
| B4 | My Usual Shop | Tap "My Usual Shop" card | Opens usual-shop screen, shows items bought 2+ times | |
| B5 | Running Low | Check "Running Low" section | Shows items not bought recently (or empty state) | |
| B6 | Price Memory | Check "Price Memory" section | Shows price changes (or empty state) | |
| B7 | Best Saving | Check "Best saving" card | Shows biggest saving from receipts (or empty) | |
| B8 | Shopping List | Tap shopping list section | Opens shopping list (or shows empty state) | |
| B9 | This Month receipts | Scroll down to receipts | Shows receipts from current month only | |
| B10 | Bell icon (alerts) | Tap bell icon in header | Opens alerts screen, shows notifications | |

---

### 📸 C. RECEIPT SCANNING (8 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| C1 | Camera opens | Tap Scan button (center tab bar) → "Scan receipt" | Camera opens, viewfinder visible | |
| C2 | Take photo | Point at receipt → tap capture button | Photo captured, "Processing..." appears | |
| C3 | Receipt processed | Wait for AI processing | Receipt appears with store name, items, total | |
| C4 | Items correct | Check extracted items | Product names and prices match the receipt | |
| C5 | Save receipt | Confirm/save the receipt | Receipt saved, appears in History tab | |
| C6 | Delete receipt | History → tap receipt → "Delete" button | Confirmation dialog → receipt removed | |
| C7 | Photo from gallery | Scan → gallery icon (if exists) | Can pick photo from gallery and process | |
| C8 | Bad photo handling | Take blurry/dark photo | Shows error message, doesn't crash | |

---

### 🔍 D. BARCODE SCANNER (7 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| D1 | Scanner opens | Scan tab → "Scan barcode" | Camera opens with barcode viewfinder | |
| D2 | Known barcode | Scan a product you've scanned before | "We already have this barcode!" + product info | |
| D3 | New barcode (API found) | Scan a product NOT in DB | Product found via Open Food Facts/UPCitemdb, auto-saved | |
| D4 | New barcode (not found) | Scan obscure product barcode | "Link this barcode" screen with search + photo options | |
| D5 | Photo ID | On "Link barcode" → "Take photo" | Camera opens, AI identifies product name | |
| D6 | Manual add | On "Link barcode" → type name → "Add" button | Product saved, "+10 points" message | |
| D7 | Tap to compare | Scan barcode → product found with prices → tap product card | Opens Prices tab with bar chart comparison | |

---

### 💰 E. PRICES — COMPARE TAB (9 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| E1 | Search works | Prices tab → Compare → type "chicken" | Products appear in list (not empty) | |
| E2 | X clear button | Type in search → tap X button | Text clears, results reset | |
| E3 | Product detail (bars) | Tap a product from results | Bar chart comparison opens with colored bars per store | |
| E4 | Cheapest highlighted | Check bar chart | Cheapest store has green price + checkmark ✓ | |
| E5 | Save pill | Check detail view | "Save €X.XX" pill shows correct saving | |
| E6 | Also Available | Scroll to "Also available" section | Similar products listed with dot + name + store + price | |
| E7 | Also Available → detail | Tap a product in "Also available" | Opens THAT product's detail (not search results) | |
| E8 | Add to shopping list | Tap "Add to shopping list" button (white text) | Item added, button text changes to "✓ Added" | |
| E9 | No results | Search for nonsense "xyzqwerty" | "No products found" message, no crash | |

---

### 🏷️ F. PRICES — OFFERS TAB (4 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| F1 | Offers load | Prices tab → "Offers This Week" | Weekly deals appear grouped by store | |
| F2 | Deal cards | Check deal cards | Product name, price, store tag, offer badge visible | |
| F3 | Smart timing | Check timing suggestion | "Best time to shop" or similar suggestion | |
| F4 | Empty state | If no offers available | Friendly empty state message, no crash | |

---

### 🛒 G. SHOPPING LIST (6 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| G1 | View list | Home → Shopping List (or nav) | Shows all added items | |
| G2 | Check item | Tap checkbox on an item | Item marked as done (strikethrough or check) | |
| G3 | Remove item | Swipe or tap delete on item | Item removed from list | |
| G4 | Add from Prices | Prices → product detail → "Add to shopping list" | Item appears in shopping list | |
| G5 | Share list | Share button (if exists) | Share sheet opens with list content | |
| G6 | Empty state | Remove all items | "Shopping list is empty" message | |

---

### 💬 H. AI CHAT (5 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| H1 | Chat opens | Tap Chat tab | "SmartDocket AI" header, suggestion chips visible | |
| H2 | Send message | Type "What's the cheapest milk?" → send | AI responds with real prices from database | |
| H3 | Suggestion chips | Tap a suggestion chip | Message sends, AI responds | |
| H4 | Multiple messages | Send 3-4 messages in a row | Conversation flows, no crashes, scroll works | |
| H5 | Long response | Ask complex question | Response renders fully, no cut-off | |

---

### 👤 I. PROFILE (8 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| I1 | Profile loads | Tap Profile tab | Avatar, name, email, plan status visible | |
| I2 | Edit name | Tap name field → change → save | Name updated | |
| I3 | Points display | Check points section | Points number visible (from barcode contributions) | |
| I4 | Level/rewards | Check level/gamification section | Current level and progress visible | |
| I5 | Settings toggles | Toggle notifications/dark mode switches | Toggles work, thumb visible (green on dark bg) | |
| I6 | Report Issue | Tap "Report Issue" | Feedback form opens, can submit | |
| I7 | Pro upgrade | Tap upgrade button (if free plan) | Opens upgrade flow or info page | |
| I8 | Sign Out | Tap "Sign Out" (red button) | Confirmation → returns to login | |

---

### 📋 J. HISTORY (4 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| J1 | History loads | Tap History tab | List of past receipts (most recent first) | |
| J2 | Receipt detail | Tap a receipt | Receipt detail opens with items, store, total | |
| J3 | Scroll/pagination | Scroll through many receipts | Loads more receipts, no crash | |
| J4 | Empty state | New user with no receipts | "No receipts yet" message | |

---

### 🏪 K. MY USUAL SHOP (4 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| K1 | Loads correctly | Home → My Usual Shop | Shows items bought 2+ times only | |
| K2 | No store name in header | Check header text | Says "Your X usual items" (NO store name) | |
| K3 | Store comparison bars | Check bar chart | Multiple stores compared with totals | |
| K4 | Delete list | Tap "Delete List" (red button) | Confirmation → list cleared | |

---

### 📱 L. UI / VISUAL (8 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| L1 | Dark theme consistent | Browse ALL screens | Dark green background everywhere, no white screens | |
| L2 | Glass cards | Check card components | Translucent glass effect, visible borders | |
| L3 | Font consistency | Check titles on all 5 tabs | DMSerifDisplay 28px on all tab titles | |
| L4 | Icons visible | Check all icons on Profile, tabs, etc | Green (#7DDFAA) icons visible on dark bg | |
| L5 | Tab bar | Check bottom tab bar | 5 tabs (Home, History, Scan, Prices, Chat) + glass scan button center | |
| L6 | StatusBar | Check top status bar | Light text on dark background (not black on dark) | |
| L7 | Safe areas | Check top/bottom margins on iPhone | No content hidden under notch or home indicator | |
| L8 | Loading states | Navigate between screens | Loading spinners appear, no blank white screens | |

---

### 🌐 M. NETWORK / OFFLINE (4 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| M1 | Slow network | Enable 3G mode (or slow Wi-Fi) | App works, just slower. Loading indicators visible | |
| M2 | No network | Turn on airplane mode → open app | Cached data shows OR friendly "No connection" message | |
| M3 | Network recovery | Go offline → go online | App recovers, data loads | |
| M4 | API timeout | (Hard to test) | No infinite loading, timeout message after ~10s | |

---

### 🔒 N. SECURITY / EDGE CASES (5 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| N1 | Deep link | Open app from a shared link | Correct screen opens | |
| N2 | Background/foreground | Send app to background → return after 5 min | App resumes, no crash, data intact | |
| N3 | Memory pressure | Open many other apps → return to SmartDocket | App reloads gracefully if needed | |
| N4 | Rapid taps | Tap buttons very fast multiple times | No duplicate actions, no crash | |
| N5 | Special characters | Search for "O'Brien's" or "Müller" | No crash, search works | |

---

### 🍎 O. APP STORE SPECIFIC (6 tests)

| # | Test | Steps | Expected | Pass? |
|---|------|-------|----------|-------|
| O1 | App icon | Check home screen | SmartDocket icon renders correctly | |
| O2 | Splash screen | Open app cold start | Splash screen appears briefly, then app loads | |
| O3 | Camera permission | First time scan | iOS permission dialog appears, works after "Allow" | |
| O4 | No crashes on launch | Open app 5 times in a row | Never crashes on startup | |
| O5 | Minimum content | All screens have content | No empty screens without explanation (Apple rejects this) | |
| O6 | No placeholder content | Check all text | No "Lorem ipsum", no "TODO", no "[placeholder]" | |

---

## PART 3: KNOWN ITEMS TO ADDRESS BEFORE SUBMISSION

| Priority | Item | Effort |
|----------|------|--------|
| 🔴 High | Privacy Policy URL must be live (Apple requires it) | 1 hour |
| 🔴 High | App Store screenshots (6.7" + 5.5" iPhone) | 2 hours |
| 🔴 High | App Store description + keywords | 1 hour |
| 🟡 Medium | Terms of Service page | 1 hour |
| 🟡 Medium | Support URL/email (Apple requires it) | 30 min |
| 🟡 Medium | GDPR opt-in for marketing emails | 1 hour |
| 🟢 Low | Remove 5 orphan component files | 10 min |
| 🟢 Low | Move hardcoded Railway URL to env var | 5 min |

---

## SCORING

- **Total tests: 95**
- **Must pass for App Store: 90+ (95%)**
- **Any CRASH = immediate blocker**
- **Any empty screen without explanation = Apple rejection**

---

*Generated by SmartDocket QA — 01 April 2026*
