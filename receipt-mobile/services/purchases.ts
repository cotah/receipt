/**
 * RevenueCat In-App Purchase service.
 *
 * Handles Pro subscription via Apple/Google native payments.
 * RevenueCat abstracts both platforms into one API.
 *
 * Setup required (one-time):
 * 1. Create account at revenuecat.com
 * 2. Create products in App Store Connect + Google Play Console
 * 3. Connect stores to RevenueCat
 * 4. Set API keys in .env
 */

import { Platform } from 'react-native';
import Purchases, {
  PurchasesOffering,
  CustomerInfo,
  PurchasesPackage,
} from 'react-native-purchases';

const API_KEYS = {
  apple: process.env.EXPO_PUBLIC_RC_APPLE_KEY || '',
  google: process.env.EXPO_PUBLIC_RC_GOOGLE_KEY || '',
};

let isConfigured = false;

/**
 * Initialize RevenueCat. Call once at app startup.
 */
export async function configurePurchases(userId?: string): Promise<void> {
  const apiKey = Platform.OS === 'ios' ? API_KEYS.apple : API_KEYS.google;

  console.log('[Purchases] Configure called, platform:', Platform.OS, 'key:', apiKey ? apiKey.substring(0, 10) + '...' : 'MISSING');

  if (!apiKey) {
    console.warn('[Purchases] No RevenueCat API key configured');
    return;
  }

  if (isConfigured) {
    console.log('[Purchases] Already configured');
    return;
  }

  try {
    Purchases.configure({ apiKey, appUserID: userId || undefined });
    isConfigured = true;
    console.log('[Purchases] Configured successfully for user:', userId || 'anonymous');
  } catch (e) {
    console.error('[Purchases] Configure failed:', e);
  }

  if (__DEV__) {
    Purchases.setLogLevel(Purchases.LOG_LEVEL.DEBUG);
  }
}

/**
 * Link RevenueCat to the current Supabase user.
 */
export async function loginPurchases(userId: string): Promise<void> {
  if (!isConfigured) return;
  try {
    await Purchases.logIn(userId);
  } catch (e) {
    console.warn('[Purchases] Login failed:', e);
  }
}

/**
 * Unlink user on logout.
 */
export async function logoutPurchases(): Promise<void> {
  if (!isConfigured) return;
  try {
    await Purchases.logOut();
  } catch (e) {
    console.warn('[Purchases] Logout failed:', e);
  }
}

/**
 * Check if user has active Pro entitlement.
 */
export async function checkProStatus(): Promise<boolean> {
  if (!isConfigured) return false;
  try {
    const customerInfo = await Purchases.getCustomerInfo();
    return customerInfo.entitlements.active['pro'] !== undefined;
  } catch (e) {
    console.warn('[Purchases] Status check failed:', e);
    return false;
  }
}

/**
 * Get available subscription packages.
 */
export async function getOfferings(): Promise<PurchasesOffering | null> {
  if (!isConfigured) {
    console.warn('[Purchases] Not configured — cannot get offerings');
    return null;
  }
  try {
    const offerings = await Purchases.getOfferings();
    console.log('[Purchases] Offerings loaded:', {
      current: offerings.current?.identifier,
      packages: offerings.current?.availablePackages?.map(p => p.identifier),
    });
    return offerings.current;
  } catch (e) {
    console.warn('[Purchases] Offerings fetch failed:', e);
    return null;
  }
}

/**
 * Purchase a subscription package.
 * Returns true if successful, false if cancelled/failed.
 */
export async function purchasePackage(
  pkg: PurchasesPackage,
): Promise<{ success: boolean; customerInfo?: CustomerInfo; error?: string }> {
  if (!isConfigured) {
    return { success: false, error: 'Purchases not configured' };
  }

  try {
    const { customerInfo } = await Purchases.purchasePackage(pkg);
    const isPro = customerInfo.entitlements.active['pro'] !== undefined;
    return { success: isPro, customerInfo };
  } catch (e: any) {
    if (e.userCancelled) {
      return { success: false, error: 'cancelled' };
    }
    console.error('[Purchases] Purchase failed:', e);
    return { success: false, error: e.message || 'Purchase failed' };
  }
}

/**
 * Restore previous purchases (e.g., after reinstall).
 */
export async function restorePurchases(): Promise<boolean> {
  if (!isConfigured) return false;
  try {
    const customerInfo = await Purchases.restorePurchases();
    return customerInfo.entitlements.active['pro'] !== undefined;
  } catch (e) {
    console.warn('[Purchases] Restore failed:', e);
    return false;
  }
}
