import React, { useState, useCallback, useRef } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator, Alert, Vibration } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { Feather } from '@expo/vector-icons';

import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import StoreTag from '../components/prices/StoreTag';
import Button from '../components/ui/Button';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../constants/typography';
import { formatCurrency } from '../utils/formatCurrency';
import api from '../services/api';

interface StoreResult {
  store_name: string;
  product_name: string;
  unit_price: number;
  is_on_offer: boolean;
  promotion_text: string | null;
  image_url: string | null;
  is_cheapest: boolean;
}

interface BarcodeResult {
  found: boolean;
  barcode: string;
  product: {
    name: string;
    brand: string;
    category: string;
    package_size: string;
    image_url: string;
  } | null;
  stores: StoreResult[];
  cheapest_store: string | null;
  cheapest_price: number | null;
  saving: number;
}

export default function BarcodeScannerScreen() {
  const router = useRouter();
  const [permission, requestPermission] = useCameraPermissions();
  const [scannedBarcode, setScannedBarcode] = useState<string | null>(null);
  const [result, setResult] = useState<BarcodeResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [flashOn, setFlashOn] = useState(false);
  const lastScanned = useRef<string>('');
  const cooldown = useRef(false);

  const handleBarcode = useCallback(async (scanResult: BarcodeScanningResult) => {
    const barcode = scanResult.data;

    // Prevent duplicate scans
    if (cooldown.current || barcode === lastScanned.current) return;
    cooldown.current = true;
    lastScanned.current = barcode;

    Vibration.vibrate(100);
    setScannedBarcode(barcode);
    setIsLoading(true);
    setResult(null);

    try {
      const { data } = await api.get<BarcodeResult>('/prices/barcode-lookup', {
        params: { barcode },
      });
      setResult(data);
    } catch (e: any) {
      Alert.alert('Error', 'Could not look up this barcode');
    } finally {
      setIsLoading(false);
      // Allow rescan after 3 seconds
      setTimeout(() => { cooldown.current = false; }, 3000);
    }
  }, []);

  const resetScan = useCallback(() => {
    setScannedBarcode(null);
    setResult(null);
    lastScanned.current = '';
    cooldown.current = false;
  }, []);

  const addToList = useCallback(async (storeName: string, productName: string, price: number) => {
    try {
      await api.post('/shopping-list/add', {
        product_name: productName,
        store_name: storeName,
        unit_price: price,
        category: result?.product?.category || 'Other',
        source: 'barcode',
      });
      Alert.alert('Added', `${productName} added to your shopping list`);
    } catch {
      Alert.alert('Error', 'Could not add to list');
    }
  }, [result]);

  // Permission handling
  if (!permission) {
    return <View style={styles.container} />;
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.permissionBox}>
          <Feather name="camera-off" size={48} color={Colors.text.tertiary} />
          <Text style={styles.permissionTitle}>Camera access needed</Text>
          <Text style={styles.permissionText}>
            To scan barcodes, SmartDocket needs access to your camera.
          </Text>
          <Button title="Allow Camera" onPress={requestPermission} />
          <Pressable onPress={() => router.back()} style={styles.backLink}>
            <Text style={styles.backLinkText}>Go back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.headerBtn}>
          <Feather name="arrow-left" size={20} color="#FFF" />
        </Pressable>
        <Text style={styles.headerTitle}>Scan barcode</Text>
        <Pressable onPress={() => setFlashOn(!flashOn)} style={styles.headerBtn}>
          <Feather name={flashOn ? 'zap' : 'zap-off'} size={20} color="#FFF" />
        </Pressable>
      </View>

      {/* Camera / Results */}
      {!scannedBarcode ? (
        <View style={styles.cameraWrap}>
          <CameraView
            style={styles.camera}
            facing="back"
            enableTorch={flashOn}
            barcodeScannerSettings={{
              barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'],
            }}
            onBarcodeScanned={handleBarcode}
          />
          {/* Viewfinder overlay */}
          <View style={styles.overlay}>
            <View style={styles.overlayTop} />
            <View style={styles.overlayMiddle}>
              <View style={styles.overlaySide} />
              <View style={styles.viewfinder}>
                <View style={[styles.corner, styles.cornerTL]} />
                <View style={[styles.corner, styles.cornerTR]} />
                <View style={[styles.corner, styles.cornerBL]} />
                <View style={[styles.corner, styles.cornerBR]} />
              </View>
              <View style={styles.overlaySide} />
            </View>
            <View style={styles.overlayBottom}>
              <Text style={styles.scanHint}>Point at a product barcode</Text>
            </View>
          </View>
        </View>
      ) : (
        <ScrollView style={styles.resultScroll} contentContainerStyle={styles.resultContent}>
          {/* Loading */}
          {isLoading && (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color={Colors.primary.default} />
              <Text style={styles.loadingText}>Looking up barcode...</Text>
            </View>
          )}

          {/* Result: Not found */}
          {result && !result.found && (
            <Card style={styles.notFoundCard}>
              <Feather name="search" size={40} color={Colors.text.tertiary} />
              <Text style={styles.notFoundTitle}>Product not found</Text>
              <Text style={styles.notFoundText}>
                Barcode {result.barcode} is not in our database yet.
              </Text>
              <Button title="Scan another" onPress={resetScan} />
            </Card>
          )}

          {/* Result: Found */}
          {result && result.found && result.product && (
            <>
              {/* Product info */}
              <Card style={styles.productCard}>
                <View style={styles.productHeader}>
                  <Feather name="check-circle" size={18} color="#3CB371" />
                  <Text style={styles.foundLabel}>Product found</Text>
                </View>
                <Text style={styles.productName}>{result.product.name}</Text>
                {result.product.brand ? (
                  <Text style={styles.productBrand}>{result.product.brand}</Text>
                ) : null}
                <Text style={styles.barcodeText}>EAN: {result.barcode}</Text>
              </Card>

              {/* Price comparison */}
              {result.stores.length > 0 ? (
                <View style={styles.storesSection}>
                  {result.stores.map((store, i) => (
                    <Card
                      key={store.store_name}
                      style={[styles.storeCard, store.is_cheapest && styles.storeCardCheapest]}
                    >
                      <View style={styles.storeRow}>
                        <View style={styles.storeLeft}>
                          <View style={styles.storeNameRow}>
                            <View style={[styles.dot, { backgroundColor: store.is_cheapest ? '#3CB371' : Colors.surface.border }]} />
                            <StoreTag storeName={store.store_name} />
                            {store.is_cheapest && <Badge text="cheapest" variant="success" size="sm" />}
                            {store.is_on_offer && <Badge text="offer" variant="warning" size="sm" />}
                          </View>
                          {store.promotion_text && (
                            <Text style={styles.storePromo} numberOfLines={1}>{store.promotion_text}</Text>
                          )}
                        </View>
                        <View style={styles.storeRight}>
                          <Text style={[styles.storePrice, store.is_cheapest && styles.storePriceCheapest]}>
                            {formatCurrency(store.unit_price)}
                          </Text>
                          <Pressable
                            onPress={() => addToList(store.store_name, store.product_name, store.unit_price)}
                            style={styles.addBtn}
                          >
                            <Feather name="plus" size={16} color={Colors.primary.default} />
                          </Pressable>
                        </View>
                      </View>
                    </Card>
                  ))}

                  {/* Saving summary */}
                  {result.saving > 0 && (
                    <Text style={styles.savingSummary}>
                      You save {formatCurrency(result.saving)} buying at {result.cheapest_store} instead of {result.stores[result.stores.length - 1]?.store_name}
                    </Text>
                  )}
                </View>
              ) : (
                <Card style={styles.noPricesCard}>
                  <Text style={styles.noPricesText}>No current prices available for this product.</Text>
                </Card>
              )}

              {/* Action buttons */}
              <View style={styles.actions}>
                <Button title="Scan another" onPress={resetScan} variant="secondary" />
              </View>
            </>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const OVERLAY_COLOR = 'rgba(0,0,0,0.55)';
const VIEWFINDER_W = 300;
const VIEWFINDER_H = 160;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    backgroundColor: 'rgba(0,0,0,0.3)', zIndex: 10,
  },
  headerBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 16, color: '#FFF',
  },
  cameraWrap: { flex: 1, position: 'relative' },
  camera: { flex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject },
  overlayTop: { flex: 1, backgroundColor: OVERLAY_COLOR },
  overlayMiddle: { flexDirection: 'row', height: VIEWFINDER_H },
  overlaySide: { flex: 1, backgroundColor: OVERLAY_COLOR },
  viewfinder: {
    width: VIEWFINDER_W, height: VIEWFINDER_H,
    borderRadius: 12, position: 'relative',
  },
  overlayBottom: {
    flex: 1, backgroundColor: OVERLAY_COLOR,
    alignItems: 'center', paddingTop: 24,
  },
  scanHint: {
    fontFamily: Fonts.body, fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
  },
  corner: {
    position: 'absolute', width: 24, height: 24,
    borderColor: '#3CB371', borderWidth: 3,
  },
  cornerTL: { top: 0, left: 0, borderRightWidth: 0, borderBottomWidth: 0, borderTopLeftRadius: 8 },
  cornerTR: { top: 0, right: 0, borderLeftWidth: 0, borderBottomWidth: 0, borderTopRightRadius: 8 },
  cornerBL: { bottom: 0, left: 0, borderRightWidth: 0, borderTopWidth: 0, borderBottomLeftRadius: 8 },
  cornerBR: { bottom: 0, right: 0, borderLeftWidth: 0, borderTopWidth: 0, borderBottomRightRadius: 8 },
  resultScroll: { flex: 1, backgroundColor: Colors.surface.background },
  resultContent: { padding: Spacing.lg },
  loadingBox: {
    alignItems: 'center', paddingVertical: Spacing.xl * 2, gap: Spacing.md,
  },
  loadingText: {
    fontFamily: Fonts.body, fontSize: 15, color: Colors.text.secondary,
  },
  notFoundCard: {
    alignItems: 'center', padding: Spacing.xl, gap: Spacing.sm,
  },
  notFoundTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 18, color: Colors.text.primary,
  },
  notFoundText: {
    fontFamily: Fonts.body, fontSize: 14, color: Colors.text.secondary,
    textAlign: 'center', marginBottom: Spacing.sm,
  },
  productCard: { marginBottom: Spacing.md },
  productHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8,
  },
  foundLabel: {
    fontFamily: Fonts.bodyBold, fontSize: 13, color: '#3CB371',
  },
  productName: {
    fontFamily: Fonts.bodyBold, fontSize: 17, color: Colors.text.primary,
  },
  productBrand: {
    fontFamily: Fonts.body, fontSize: 13, color: Colors.text.secondary, marginTop: 2,
  },
  barcodeText: {
    fontFamily: Fonts.body, fontSize: 12, color: Colors.text.tertiary, marginTop: 4,
  },
  storesSection: { gap: Spacing.xs },
  storeCard: { marginBottom: 0 },
  storeCardCheapest: {
    borderWidth: 1.5, borderColor: 'rgba(60,179,113,0.4)',
  },
  storeRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  storeLeft: { flex: 1 },
  storeNameRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap',
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  storePromo: {
    fontFamily: Fonts.body, fontSize: 11, color: Colors.text.secondary,
    marginTop: 2, marginLeft: 14,
  },
  storeRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  storePrice: {
    fontFamily: 'CourierPrime_700Bold', fontSize: 18, color: Colors.text.primary,
  },
  storePriceCheapest: { color: '#3CB371' },
  addBtn: {
    width: 32, height: 32, borderRadius: 16,
    borderWidth: 1.5, borderColor: Colors.primary.default,
    alignItems: 'center', justifyContent: 'center',
  },
  savingSummary: {
    fontFamily: Fonts.body, fontSize: 13, color: Colors.text.secondary,
    textAlign: 'center', marginTop: Spacing.sm,
  },
  noPricesCard: { padding: Spacing.lg, alignItems: 'center' },
  noPricesText: {
    fontFamily: Fonts.body, fontSize: 14, color: Colors.text.secondary,
  },
  actions: {
    marginTop: Spacing.lg, gap: Spacing.sm,
  },
  permissionBox: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    padding: Spacing.xl, gap: Spacing.md,
    backgroundColor: Colors.surface.background,
  },
  permissionTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 18, color: Colors.text.primary,
  },
  permissionText: {
    fontFamily: Fonts.body, fontSize: 14, color: Colors.text.secondary,
    textAlign: 'center',
  },
  backLink: { marginTop: Spacing.sm },
  backLinkText: {
    fontFamily: Fonts.body, fontSize: 14, color: Colors.primary.default,
  },
});
