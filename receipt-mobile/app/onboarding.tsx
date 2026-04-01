import React, { useState, useRef, useCallback } from 'react';
import {
  View, Text, Pressable, StyleSheet, Dimensions, FlatList,
  Animated, ViewToken,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Feather } from '@expo/vector-icons';

import { Colors } from '../constants/colors';
import { Fonts } from '../constants/typography';

const { width: SCREEN_W } = Dimensions.get('window');
const ONBOARDING_KEY = 'smartdocket_onboarding_seen';

// ─── Slide data ───
const slides = [
  {
    id: '0',
    tag: 'WELCOME TO',
    title: 'SmartDocket',
    desc: 'Find the cheapest prices across all Irish supermarkets. Know exactly where to save before you shop.',
    animType: 'priceList',
  },
  {
    id: '1',
    tag: 'STEP 1',
    title: 'Compare before you buy',
    desc: 'Search any product and instantly see prices across Tesco, Lidl, Aldi, SuperValu and Dunnes. The cheapest is always highlighted.',
    animType: 'barChart',
  },
  {
    id: '2',
    tag: 'STEP 2',
    title: 'Track your spending',
    desc: 'Scan receipts to track spending, build price history, and earn points. The more you scan, the smarter your recommendations.',
    animType: 'receiptScan',
  },
  {
    id: '3',
    tag: 'STEP 3',
    title: 'Earn points every day',
    desc: 'Scan receipts, link barcodes, refer friends, confirm savings. Every action earns points towards monthly prizes!',
    animType: 'points',
  },
  {
    id: '4',
    tag: 'MONTHLY PRIZES',
    title: 'Win signed jerseys',
    desc: 'Every 200 points = 1 raffle ticket. Monthly draw for signed Premier League jerseys. More tickets, more chances!',
    animType: 'raffle',
  },
];

// ─── Mini animated illustrations ───

function PriceListAnim() {
  const items = [
    { name: 'Chicken Breast 1kg', store: 'Aldi', price: '€5.99' },
    { name: 'Avonmore Milk 2L', store: 'Lidl', price: '€2.19' },
    { name: 'Brennans Bread', store: 'Dunnes', price: '€1.69' },
  ];
  return (
    <View style={a.box}>
      <Text style={a.boxLabel}>Before you shop, check:</Text>
      {items.map((item, i) => (
        <View key={i} style={a.priceRow}>
          <Text style={a.priceItem} numberOfLines={1}>{item.name}</Text>
          <View style={a.priceBadge}>
            <Text style={a.priceBadgeText}>{item.store} {item.price}</Text>
          </View>
        </View>
      ))}
      <View style={a.saveBanner}>
        <Text style={a.saveBannerText}>Save up to €12.40/week</Text>
      </View>
    </View>
  );
}

function BarChartAnim() {
  const bars = [
    { store: 'Tesco', w: '75%', price: '€7.49', color: '#0C447C' },
    { store: 'Dunnes', w: '68%', price: '€6.99', color: '#1D9E75' },
    { store: 'Lidl', w: '62%', price: '€6.49', color: '#D85A30' },
    { store: 'Aldi', w: '55%', price: '€5.99', color: '#534AB7', best: true },
  ];
  return (
    <View style={a.box}>
      <Text style={a.boxLabel}>Chicken Breast 1kg</Text>
      {bars.map((b, i) => (
        <View key={i} style={a.barRow}>
          <Text style={a.barStore}>{b.store}</Text>
          <View style={a.barTrack}>
            <View style={[a.bar, { width: b.w as any, backgroundColor: b.color }]} />
          </View>
          <Text style={a.barPrice}>{b.price}</Text>
          {b.best && (
            <View style={a.checkCircle}>
              <Feather name="check" size={10} color="#FFF" />
            </View>
          )}
        </View>
      ))}
      <View style={a.tipBanner}>
        <Feather name="trending-down" size={12} color="#085041" />
        <Text style={a.tipText}>Aldi is cheapest — save €1.50</Text>
      </View>
    </View>
  );
}

function ReceiptScanAnim() {
  return (
    <View style={[a.box, { backgroundColor: 'rgba(255,255,255,0.08)' }]}>
      {/* Camera circle */}
      <View style={a.camCircle} />
      {/* Viewfinder */}
      <View style={a.viewfinder}>
        <View style={a.receiptLines}>
          {[70, 90, 50, 80, 60].map((w, i) => (
            <View key={i} style={[a.rLine, { width: `${w}%` }]} />
          ))}
        </View>
      </View>
      {/* Result badge */}
      <View style={a.scanResult}>
        <Text style={a.scanResultText}>12 items found  +15 pts</Text>
      </View>
      {/* Shutter */}
      <View style={a.shutter} />
    </View>
  );
}

function PointsAnim() {
  const coins = [
    { pts: '+15', color: Colors.accent.green, top: 16, left: 24 },
    { pts: '+30', color: '#534AB7', top: 16, left: 148 },
    { pts: '+50', color: '#D4A843', top: 70, left: 84 },
  ];
  return (
    <View style={[a.box, { backgroundColor: 'rgba(240,214,138,0.15)' }]}>
      {coins.map((c, i) => (
        <View key={i} style={[a.coin, { backgroundColor: c.color, top: c.top, left: c.left }]}>
          <Text style={a.coinText}>{c.pts}</Text>
        </View>
      ))}
      <View style={a.pointsBottom}>
        <View style={a.pointsLabels}>
          <Text style={a.pointsLabel}>Receipts</Text>
          <Text style={a.pointsLabel}>Barcodes</Text>
          <Text style={a.pointsLabel}>Referrals</Text>
        </View>
        <View style={a.progressTrack}>
          <View style={a.progressFill} />
        </View>
        <Text style={a.pointsTotal}>460 pts this month</Text>
      </View>
    </View>
  );
}

function RaffleAnim() {
  const tickets = [
    { label: 'TICKET #1', bg: 'rgba(255,255,255,0.15)', top: 20, left: 16 },
    { label: 'TICKET #2', bg: '#D4A843', top: 20, left: 124 },
    { label: 'TICKET #3', bg: '#534AB7', top: 76, left: 70 },
  ];
  return (
    <View style={[a.box, { backgroundColor: 'rgba(80,200,120,0.20)' }]}>
      {tickets.map((t, i) => (
        <View key={i} style={[a.ticket, { backgroundColor: t.bg, top: t.top, left: t.left }]}>
          <Text style={a.ticketText}>{t.label}</Text>
        </View>
      ))}
      <View style={a.raffleBottom}>
        <Text style={a.raffleTitle}>Monthly raffle draw</Text>
        <Text style={a.raffleSub}>200 pts = 1 ticket</Text>
      </View>
    </View>
  );
}

const AnimComponents: Record<string, React.FC> = {
  priceList: PriceListAnim,
  barChart: BarChartAnim,
  receiptScan: ReceiptScanAnim,
  points: PointsAnim,
  raffle: RaffleAnim,
};

// ─── Main component ───

export default function OnboardingScreen() {
  const router = useRouter();
  const [currentIndex, setCurrentIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);

  const onViewableItemsChanged = useRef(({ viewableItems }: { viewableItems: ViewToken[] }) => {
    if (viewableItems.length > 0 && viewableItems[0].index != null) {
      setCurrentIndex(viewableItems[0].index);
    }
  }).current;

  const viewabilityConfig = useRef({ viewAreaCoveragePercentThreshold: 50 }).current;

  const handleNext = useCallback(() => {
    if (currentIndex < slides.length - 1) {
      flatListRef.current?.scrollToIndex({ index: currentIndex + 1, animated: true });
    } else {
      handleFinish();
    }
  }, [currentIndex]);

  const handleFinish = useCallback(async () => {
    await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
    router.replace('/(tabs)');
  }, [router]);

  const renderSlide = useCallback(({ item }: { item: typeof slides[0] }) => {
    const AnimComp = AnimComponents[item.animType];
    const isLast = item.id === '4';
    return (
      <View style={s.slide}>
        <Text style={s.tag}>{item.tag}</Text>
        <Text style={s.title}>{item.title}</Text>
        <View style={s.animWrap}>
          <AnimComp />
        </View>
        <Text style={s.desc}>{item.desc}</Text>
        <View style={s.spacer} />
        {/* Dots */}
        <View style={s.dots}>
          {slides.map((_, i) => (
            <View key={i} style={[s.dot, currentIndex === i && s.dotActive]} />
          ))}
        </View>
        <Pressable onPress={isLast ? handleFinish : handleNext} style={s.btn}>
          <Text style={s.btnText}>{isLast ? 'Start comparing prices!' : currentIndex === 0 ? 'Get started' : 'Next'}</Text>
        </Pressable>
        <Pressable onPress={handleFinish} style={s.skipBtn}>
          <Text style={s.skipText}>{isLast ? '' : 'Skip tour'}</Text>
        </Pressable>
      </View>
    );
  }, [currentIndex, handleNext, handleFinish]);

  return (
    <SafeAreaView style={s.safe} edges={['top', 'bottom']}>
      <FlatList
        ref={flatListRef}
        data={slides}
        renderItem={renderSlide}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={(item) => item.id}
        onViewableItemsChanged={onViewableItemsChanged}
        viewabilityConfig={viewabilityConfig}
        bounces={false}
      />
    </SafeAreaView>
  );
}

// ─── Styles ───

const GREEN = Colors.accent.green;

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.surface.background },
  slide: {
    width: SCREEN_W, flex: 1, alignItems: 'center',
    paddingHorizontal: 28, paddingTop: 20, paddingBottom: 16,
  },
  tag: { fontSize: 11, color: 'rgba(255,255,255,0.35)', letterSpacing: 0.5, marginBottom: 6 },
  title: { fontFamily: Fonts.bodyBold, fontSize: 26, color: GREEN, textAlign: 'center', marginBottom: 12 },
  animWrap: { width: 220, height: 220, marginBottom: 16 },
  desc: { fontFamily: Fonts.body, fontSize: 14, color: 'rgba(255,255,255,0.50)', textAlign: 'center', lineHeight: 21, paddingHorizontal: 8 },
  spacer: { flex: 1 },
  dots: { flexDirection: 'row', gap: 6, justifyContent: 'center', marginBottom: 16 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.20)' },
  dotActive: { backgroundColor: GREEN, width: 22 },
  btn: { backgroundColor: GREEN, borderRadius: 14, paddingVertical: 14, width: '100%', alignItems: 'center' },
  btnText: { fontFamily: Fonts.bodyBold, fontSize: 16, color: '#FFF' },
  skipBtn: { marginTop: 10, minHeight: 20 },
  skipText: { fontFamily: Fonts.body, fontSize: 13, color: 'rgba(255,255,255,0.35)' },
});

const a = StyleSheet.create({
  box: { width: 220, height: 220, borderRadius: 18, backgroundColor: 'rgba(80,200,120,0.15)', position: 'relative', overflow: 'hidden', padding: 14 },
  boxLabel: { fontFamily: Fonts.bodySemiBold, fontSize: 12, color: GREEN, marginBottom: 8 },
  // PriceList
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6, borderBottomWidth: 0.5, borderBottomColor: 'rgba(0,0,0,0.06)' },
  priceItem: { fontFamily: Fonts.body, fontSize: 11, color: 'rgba(255,255,255,0.70)', flex: 1, marginRight: 6 },
  priceBadge: { backgroundColor: 'rgba(80,200,120,0.12)', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  priceBadgeText: { fontFamily: Fonts.bodySemiBold, fontSize: 9, color: '#7DDFAA' },
  saveBanner: { position: 'absolute', bottom: 14, left: 14, right: 14, backgroundColor: GREEN, borderRadius: 10, paddingVertical: 8, alignItems: 'center' },
  saveBannerText: { fontFamily: Fonts.bodyBold, fontSize: 14, color: '#FFF' },
  // BarChart
  barRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  barStore: { fontFamily: Fonts.bodySemiBold, fontSize: 10, width: 44, color: 'rgba(255,255,255,0.70)' },
  barTrack: { flex: 1, height: 16, backgroundColor: 'rgba(0,0,0,0.04)', borderRadius: 4, overflow: 'hidden', marginHorizontal: 4 },
  bar: { height: '100%', borderRadius: 4 },
  barPrice: { fontFamily: Fonts.bodySemiBold, fontSize: 9, color: 'rgba(255,255,255,0.50)', width: 34 },
  checkCircle: { width: 16, height: 16, borderRadius: 8, backgroundColor: GREEN, alignItems: 'center', justifyContent: 'center' },
  tipBanner: { position: 'absolute', bottom: 12, left: 12, right: 12, backgroundColor: 'rgba(80,200,120,0.12)', borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10, flexDirection: 'row', alignItems: 'center', gap: 4 },
  tipText: { fontFamily: Fonts.bodySemiBold, fontSize: 10, color: '#7DDFAA' },
  // ReceiptScan
  camCircle: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', alignSelf: 'center', marginBottom: 8 },
  viewfinder: { width: 110, height: 100, borderWidth: 2, borderColor: '#5DCAA5', borderRadius: 6, alignSelf: 'center', padding: 8, justifyContent: 'center' },
  receiptLines: { gap: 5 },
  rLine: { height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.18)' },
  scanResult: { position: 'absolute', bottom: 50, alignSelf: 'center', backgroundColor: '#5DCAA5', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 5 },
  scanResultText: { fontFamily: Fonts.bodySemiBold, fontSize: 10, color: '#FFF' },
  shutter: { position: 'absolute', bottom: 12, alignSelf: 'center', width: 36, height: 36, borderRadius: 18, borderWidth: 3, borderColor: 'rgba(255,255,255,0.15)', backgroundColor: 'rgba(255,255,255,0.1)' },
  // Points
  coin: { position: 'absolute', width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  coinText: { fontFamily: Fonts.bodyBold, fontSize: 12, color: '#FFF' },
  pointsBottom: { position: 'absolute', bottom: 14, left: 14, right: 14 },
  pointsLabels: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  pointsLabel: { fontFamily: Fonts.body, fontSize: 9, color: 'rgba(255,255,255,0.35)' },
  progressTrack: { height: 4, backgroundColor: '#E8E8E0', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', width: '65%', backgroundColor: GREEN, borderRadius: 2 },
  pointsTotal: { fontFamily: Fonts.bodyBold, fontSize: 16, color: GREEN, textAlign: 'center', marginTop: 6 },
  // Raffle
  ticket: { position: 'absolute', width: 80, height: 44, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  ticketText: { fontFamily: Fonts.bodyBold, fontSize: 10, color: '#FFF' },
  raffleBottom: { position: 'absolute', bottom: 16, alignSelf: 'center', alignItems: 'center' },
  raffleTitle: { fontFamily: Fonts.bodyBold, fontSize: 14, color: '#D4A843' },
  raffleSub: { fontFamily: Fonts.body, fontSize: 11, color: 'rgba(255,255,255,0.6)', marginTop: 2 },
});

export { ONBOARDING_KEY };
