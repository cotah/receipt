import React, { useState, useEffect, useCallback, useRef } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator, Alert, Vibration } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { Feather } from '@expo/vector-icons';

import Card from '../components/ui/Card';
import { Colors } from '../constants/colors';
import { Spacing, Fonts } from '../constants/typography';
import api from '../services/api';

interface BarcodeItem {
  id: string;
  name: string;
  category: string;
  price: number;
}

type Phase = 'loading' | 'scanning' | 'done';

export default function LinkBarcodesScreen() {
  const router = useRouter();
  const { receiptId } = useLocalSearchParams<{ receiptId: string }>();
  const [permission, requestPermission] = useCameraPermissions();

  const [phase, setPhase] = useState<Phase>('loading');
  const [items, setItems] = useState<BarcodeItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [linked, setLinked] = useState<string[]>([]);
  const [totalPoints, setTotalPoints] = useState(0);
  const [storeName, setStoreName] = useState('');

  const cooldown = useRef(false);

  // Load items
  useEffect(() => {
    if (!receiptId) return;
    (async () => {
      try {
        const { data } = await api.get(`/receipts/${receiptId}/barcode-items`);
        setItems(data.items || []);
        setStoreName(data.store_name || '');
        setPhase(data.items?.length > 0 ? 'scanning' : 'done');
      } catch {
        setPhase('done');
      }
    })();
  }, [receiptId]);

  const currentItem = items[currentIndex];

  // Handle barcode scan
  const handleScan = useCallback(async (result: BarcodeScanningResult) => {
    if (cooldown.current || !currentItem) return;
    cooldown.current = true;
    Vibration.vibrate(100);

    try {
      const { data } = await api.post('/receipts/link-barcode', null, {
        params: { item_id: currentItem.id, barcode: result.data },
      });
      setLinked(prev => [...prev, currentItem.name]);
      setTotalPoints(prev => prev + (data.points_earned || 30));
    } catch {
      // Silently continue — might be duplicate barcode
    }

    // Move to next or finish
    if (currentIndex + 1 < items.length) {
      setCurrentIndex(prev => prev + 1);
    } else {
      setPhase('done');
    }

    setTimeout(() => { cooldown.current = false; }, 1500);
  }, [currentItem, currentIndex, items.length]);

  // Skip current product
  const skipProduct = useCallback(() => {
    if (currentIndex + 1 < items.length) {
      setCurrentIndex(prev => prev + 1);
    } else {
      setPhase('done');
    }
  }, [currentIndex, items.length]);

  // Finish early
  const finishEarly = useCallback(() => {
    setPhase('done');
  }, []);

  // Permission
  if (!permission) return <View style={styles.container} />;
  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.safeLight} edges={['top']}>
        <View style={styles.permBox}>
          <Text style={styles.permText}>Camera access needed to scan barcodes</Text>
          <Pressable onPress={requestPermission} style={styles.permBtn}>
            <Text style={styles.permBtnText}>Allow camera</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // Loading
  if (phase === 'loading') {
    return (
      <SafeAreaView style={styles.safeLight} edges={['top']}>
        <View style={styles.permBox}>
          <ActivityIndicator size="large" color={Colors.accent.green} />
          <Text style={styles.loadingText}>Loading products...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Done
  if (phase === 'done') {
    return (
      <SafeAreaView style={styles.safeLight} edges={['top']}>
        <View style={styles.doneContainer}>
          <Text style={styles.doneEmoji}>{linked.length > 0 ? '🏆' : '👋'}</Text>
          <Text style={styles.doneTitle}>
            {linked.length > 0 ? 'Nice work!' : 'No products to scan'}
          </Text>
          {linked.length > 0 && (
            <>
              <Text style={styles.doneSub}>
                You linked {linked.length} of {items.length} barcodes
              </Text>
              <View style={styles.pointsBox}>
                <Text style={styles.pointsValue}>+{totalPoints} pts</Text>
                <Text style={styles.pointsSub}>
                  {linked.length}×30 double points
                </Text>
              </View>
              <View style={styles.linkedList}>
                {linked.slice(0, 5).map((name, i) => (
                  <View key={i} style={styles.linkedRow}>
                    <Text style={styles.linkedName} numberOfLines={1}>{name}</Text>
                    <Text style={styles.linkedCheck}>✓</Text>
                  </View>
                ))}
                {linked.length > 5 && (
                  <Text style={styles.linkedMore}>+{linked.length - 5} more</Text>
                )}
              </View>
            </>
          )}
          <Pressable
            onPress={() => receiptId ? router.replace(`/receipt/${receiptId}`) : router.back()}
            style={styles.doneBtn}
          >
            <Text style={styles.doneBtnText}>View receipt →</Text>
          </Pressable>
          {linked.length === 0 && (
            <Pressable onPress={() => router.back()} style={styles.skipLink}>
              <Text style={styles.skipLinkText}>Go back</Text>
            </Pressable>
          )}
        </View>
      </SafeAreaView>
    );
  }

  // Scanning
  return (
    <View style={styles.container}>
      {/* Header */}
      <SafeAreaView edges={['top']} style={styles.scanHeader}>
        <View style={styles.scanHeaderRow}>
          <Pressable onPress={finishEarly} style={styles.scanHeaderBtn}>
            <Feather name="x" size={20} color="#FFF" />
          </Pressable>
          <Text style={styles.scanHeaderTitle}>Scan barcodes</Text>
          <Text style={styles.scanHeaderCount}>
            {currentIndex + 1} / {items.length}
          </Text>
        </View>
      </SafeAreaView>

      {/* Current product card */}
      <View style={styles.productCard}>
        <Text style={styles.productLabel}>NOW SCANNING</Text>
        <Text style={styles.productName} numberOfLines={2}>
          {currentItem?.name || ''}
        </Text>
        <Text style={styles.productPoints}>+30 pts (double!)</Text>
      </View>

      {/* Camera */}
      <CameraView
        style={styles.camera}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] }}
        onBarcodeScanned={handleScan}
      >
        {/* Viewfinder */}
        <View style={styles.overlay}>
          <View style={styles.overlayTop} />
          <View style={styles.overlayMiddle}>
            <View style={styles.overlaySide} />
            <View style={styles.viewfinder}>
              <View style={[styles.corner, styles.cTL]} />
              <View style={[styles.corner, styles.cTR]} />
              <View style={[styles.corner, styles.cBL]} />
              <View style={[styles.corner, styles.cBR]} />
              <View style={styles.scanLine} />
            </View>
            <View style={styles.overlaySide} />
          </View>
          <View style={styles.overlayBottom}>
            <Text style={styles.hint}>
              Point at the barcode on the {currentItem?.name || 'product'}
            </Text>
          </View>
        </View>
      </CameraView>

      {/* Bottom actions */}
      <View style={styles.bottomBar}>
        <Pressable onPress={skipProduct} style={styles.bottomBtn}>
          <Text style={styles.bottomBtnText}>Skip this product</Text>
        </Pressable>
        <Pressable onPress={finishEarly} style={styles.bottomBtn}>
          <Text style={styles.bottomBtnText}>Done scanning</Text>
        </Pressable>
      </View>
    </View>
  );
}

const OV = 'rgba(0,0,0,0.55)';

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  safeLight: { flex: 1, backgroundColor: Colors.surface.background },
  permBox: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32 },
  permText: { fontFamily: Fonts.body, fontSize: 15, color: Colors.text.secondary, textAlign: 'center' },
  permBtn: { backgroundColor: 'rgba(80,200,120,0.20)', borderRadius: 12, paddingHorizontal: 24, paddingVertical: 12 },
  permBtnText: { fontFamily: Fonts.bodyBold, fontSize: 15, color: '#FFF' },
  loadingText: { fontFamily: Fonts.body, fontSize: 15, color: Colors.text.secondary },

  // Scan header
  scanHeader: { backgroundColor: 'rgba(0,0,0,0.4)', zIndex: 10 },
  scanHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8 },
  scanHeaderBtn: { width: 32, height: 32, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.15)', alignItems: 'center', justifyContent: 'center' },
  scanHeaderTitle: { fontFamily: Fonts.bodyBold, fontSize: 16, color: '#FFF' },
  scanHeaderCount: { fontFamily: Fonts.bodySemiBold, fontSize: 14, color: 'rgba(255,255,255,0.6)' },

  // Product card
  productCard: { backgroundColor: 'rgba(255,255,255,0.1)', marginHorizontal: 12, marginVertical: 8, borderRadius: 12, padding: 12 },
  productLabel: { fontFamily: Fonts.bodyBold, fontSize: 10, color: 'rgba(255,255,255,0.5)', letterSpacing: 0.5 },
  productName: { fontFamily: Fonts.bodyBold, fontSize: 17, color: '#FFF', marginTop: 2 },
  productPoints: { fontFamily: Fonts.bodySemiBold, fontSize: 12, color: '#5DCAA5', marginTop: 4 },

  // Camera
  camera: { flex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject },
  overlayTop: { flex: 1, backgroundColor: OV },
  overlayMiddle: { flexDirection: 'row', height: 140 },
  overlaySide: { flex: 1, backgroundColor: OV },
  viewfinder: { width: 280, height: 140, borderRadius: 10, position: 'relative', justifyContent: 'center', alignItems: 'center' },
  corner: { position: 'absolute', width: 22, height: 22, borderColor: '#5DCAA5', borderWidth: 3 },
  cTL: { top: 0, left: 0, borderRightWidth: 0, borderBottomWidth: 0, borderTopLeftRadius: 6 },
  cTR: { top: 0, right: 0, borderLeftWidth: 0, borderBottomWidth: 0, borderTopRightRadius: 6 },
  cBL: { bottom: 0, left: 0, borderRightWidth: 0, borderTopWidth: 0, borderBottomLeftRadius: 6 },
  cBR: { bottom: 0, right: 0, borderLeftWidth: 0, borderTopWidth: 0, borderBottomRightRadius: 6 },
  scanLine: { width: '75%', height: 2, backgroundColor: '#5DCAA5', opacity: 0.5 },
  overlayBottom: { flex: 1, backgroundColor: OV, alignItems: 'center', paddingTop: 24 },
  hint: { fontFamily: Fonts.body, fontSize: 13, color: 'rgba(255,255,255,0.6)', textAlign: 'center', paddingHorizontal: 20 },

  // Bottom bar
  bottomBar: { flexDirection: 'row', justifyContent: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 16, backgroundColor: 'rgba(0,0,0,0.5)' },
  bottomBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.12)' },
  bottomBtnText: { fontFamily: Fonts.bodySemiBold, fontSize: 13, color: 'rgba(255,255,255,0.7)' },

  // Done screen
  doneContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  doneEmoji: { fontSize: 48, marginBottom: 12 },
  doneTitle: { fontFamily: Fonts.bodyBold, fontSize: 22, color: Colors.text.primary, marginBottom: 4 },
  doneSub: { fontFamily: Fonts.body, fontSize: 14, color: Colors.text.secondary, marginBottom: 16 },
  pointsBox: { backgroundColor: 'rgba(60,179,113,0.08)', borderRadius: 16, paddingHorizontal: 24, paddingVertical: 14, alignItems: 'center', marginBottom: 16 },
  pointsValue: { fontFamily: Fonts.bodyBold, fontSize: 28, color: '#1D9E75' },
  pointsSub: { fontFamily: Fonts.body, fontSize: 12, color: Colors.accent.green, marginTop: 2 },
  linkedList: { width: '100%', marginBottom: 20 },
  linkedRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6, borderBottomWidth: 0.5, borderBottomColor: Colors.surface.border },
  linkedName: { fontFamily: Fonts.body, fontSize: 14, color: Colors.text.primary, flex: 1 },
  linkedCheck: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.accent.green },
  linkedMore: { fontFamily: Fonts.body, fontSize: 13, color: Colors.text.secondary, marginTop: 4, textAlign: 'center' },
  doneBtn: { backgroundColor: 'rgba(80,200,120,0.20)', borderRadius: 12, paddingHorizontal: 32, paddingVertical: 14 },
  doneBtnText: { fontFamily: Fonts.bodyBold, fontSize: 15, color: '#FFF' },
  skipLink: { marginTop: 12 },
  skipLinkText: { fontFamily: Fonts.body, fontSize: 14, color: Colors.text.secondary },
});
