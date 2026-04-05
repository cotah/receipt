# SmartDocket — App Store Submission Guide

## Status: READY TO SUBMIT ✅

---

## STEP 1: EAS Setup (5 minutes)

Run these commands no teu terminal:

```bash
cd receipt-mobile

# Install EAS CLI (if not installed)
npm install -g eas-cli

# Login to Expo account
eas login

# Initialize project (this generates the REAL projectId)
eas init

# This will update app.json with the correct projectId automatically
```

---

## STEP 2: Apple App Store Connect

### App Information

| Field | Value |
|-------|-------|
| App Name | SmartDocket |
| Subtitle | Compare Irish Grocery Prices |
| Category | Shopping |
| Secondary Category | Finance |
| Content Rating | 4+ |
| Privacy Policy URL | https://www.smartdocket.ie/privacy.html |
| Support URL | https://www.smartdocket.ie |
| Marketing URL | https://www.smartdocket.ie |

### Description (4000 chars max)

```
SmartDocket compares grocery prices across Ireland's 5 major supermarkets — so you always know where the deals are.

SCAN YOUR RECEIPT
Take a photo of any receipt from Tesco, Lidl, Aldi, SuperValu, or Dunnes. Our AI reads it instantly — even crumpled or faded receipts.

SEE WHERE YOU OVERPAID
SmartDocket shows you where every item is cheaper across all 5 stores. Real prices, updated every 2 days.

SAVE €40+ PER MONTH
Track your spending, get personalised deal alerts, and optimise your next shop with smart store recommendations.

FEATURES:
• Price comparison across Tesco, Lidl, Aldi, SuperValu & Dunnes
• AI-powered receipt scanning (works with crumpled receipts!)
• Smart Search — find the cheapest price for any product
• Weekly deals from all 5 stores in one place
• Shopping list with price-optimised store suggestions
• AI chat assistant — ask about prices, deals, and spending
• Monthly spending report delivered to your email
• Barcode scanner to contribute and compare prices
• Reward points for every receipt scanned

PRO PLAN (€4.99/month):
• Unlimited receipt scans
• Golden Deals — products 25%+ below average price
• Price drop alerts for your regular items
• AI chat assistant with full spending insights
• Monthly email report with personalised tips
• 2.5× reward points

SmartDocket tracks 4,200+ products with prices updated every 2 days from official store data. Made in Dublin, for Irish shoppers.
```

### Keywords (100 chars max, comma separated)

```
grocery,prices,compare,supermarket,receipt,scanner,tesco,lidl,aldi,savings,deals,Ireland,shopping
```

### Promotional Text (170 chars max)

```
Compare grocery prices across Tesco, Lidl, Aldi, SuperValu & Dunnes. Scan any receipt and see where you can save. 4,200+ products tracked live.
```

### What's New (for updates)

```
Welcome to SmartDocket 1.0! 🎉
• Compare prices across 5 Irish supermarkets
• AI-powered receipt scanning
• Smart Search & weekly deals
• Barcode scanner with community pricing
• AI chat assistant for spending insights
```

---

## STEP 3: Screenshots (iPhone 15 = 6.1" display)

Apple requires screenshots for these sizes:
- **6.7" (iPhone 15 Pro Max)** — REQUIRED
- **5.5" (iPhone 8 Plus)** — REQUIRED for older devices

### How to take screenshots on iPhone 15:

1. Open SmartDocket on the phone
2. Navigate to each screen below
3. Press **Side button + Volume Up** simultaneously
4. Screenshots go to Photos → Screenshots album

### Recommended 5 screenshots (in order):

| # | Screen | What to show |
|---|--------|-------------|
| 1 | Home | "Spent this month" card + stats + greeting |
| 2 | Prices → Compare | Search results with bar chart comparison |
| 3 | Prices → Offers | Weekly deals from multiple stores |
| 4 | Receipt scan result | A processed receipt with items + savings |
| 5 | AI Chat | A conversation asking about cheapest prices |

**Tips:**
- Use REAL data (not empty screens)
- Make sure dark theme looks clean
- iPhone 15 resolution is fine (2556×1179) — Apple scales automatically

---

## STEP 4: Build & Submit

```bash
# Build for iOS
eas build --platform ios --profile production

# After build completes, submit to App Store
eas submit --platform ios

# Build for Android
eas build --platform android --profile production

# Submit to Google Play
eas submit --platform android
```

---

## STEP 5: Google Play Console

### Store Listing

| Field | Value |
|-------|-------|
| App name | SmartDocket - Grocery Price Compare |
| Short description (80 chars) | Compare grocery prices across Ireland's 5 major supermarkets and save. |
| Full description | (same as Apple description above) |
| Category | Shopping |
| Content rating | Everyone |
| Privacy policy URL | https://www.smartdocket.ie/privacy.html |

### Screenshots
- Same as Apple but minimum 2, recommended 4-8
- Google Play also needs a **Feature Graphic** (1024×500 banner)

---

## STEP 6: Before First Build

Things to configure in `eas.json`:
1. Replace `YOUR_APPLE_ID` with your Apple ID email
2. Replace `YOUR_ASC_APP_ID` with App Store Connect app ID
3. Replace `YOUR_TEAM_ID` with Apple Developer Team ID
4. For Android: add `google-services.json` from Play Console

---

## App Review Notes (for Apple)

```
SmartDocket is a grocery price comparison app for Irish consumers. 
It compares prices across Tesco, Lidl, Aldi, SuperValu, and Dunnes.

To test the app:
1. Create an account with any email
2. Take a photo of any Irish supermarket receipt
3. View price comparisons in the Prices tab
4. Try the AI Chat to ask about prices

The app requires camera access to scan receipts.
No special credentials needed — regular account creation works.

Demo account (optional):
Email: review@smartdocket.ie
Password: AppReview2026!
```

Note: Create the demo account above in your app before submitting!
