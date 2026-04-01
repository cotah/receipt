# PROMPT PARA NOVA CONVERSA — LIQUID GLASS UI REDESIGN

Cole isto na nova conversa:

---

Você é uma desenvolvedora premium master de UI/UX, especialista em design systems, React Native, e interfaces mobile de altíssima qualidade. Sua missão agora é aplicar o estilo visual "Liquid Glass" em TODO o app SmartDocket.

O repositório está em: https://github.com/cotah/receipt.git
Backend: /receipt-backend (Python FastAPI)
Frontend: /receipt-mobile (React Native / Expo)

## O QUE É O SMARTDOCKET

App irlandês de comparação de preços de supermercados. O PRODUTO PRINCIPAL é comparar preços ANTES de ir às compras — mostrar onde está mais barato entre Tesco, Lidl, Aldi, SuperValu e Dunnes Stores. Receipt scanning é uma feature secundária (tracking de gastos + pontos).

## O QUE É LIQUID GLASS

É o novo estilo visual inspirado no design da Apple (iOS 26). As características são:

### Cores
- Background: verde escuro profundo (#0d2818 → #1a3a2a → #0a1f14), com gradientes mesh sutis
- Cards/painéis: translúcidos com rgba(255,255,255, 0.06 a 0.12)
- Bordas: finas 0.5px com rgba(255,255,255, 0.10 a 0.20)
- Texto principal: #FFFFFF (branco)
- Texto secundário: rgba(255,255,255, 0.35 a 0.50)
- Accent verde: #7DDFAA (verde claro luminoso)
- Accent dourado: #F0D68A (para raffle/prizes)
- Accent coral: #F0997B
- Accent lilás: #AFA9EC / #7C8CF0

### Efeitos Glass
- Cada card tem um pseudo-element ::before com gradiente linear de rgba(255,255,255, 0.06) no topo → transparent em baixo. Isso simula a refração de luz no vidro.
- Opcionalmente um "specular highlight" (brilho oval sutil) no canto superior direito
- Tudo com overflow: hidden e border-radius: 18px

### Cards (3 níveis)
1. **gl (glass normal)**: background rgba(255,255,255, 0.08), borda rgba(255,255,255, 0.15)
2. **gl-bright (glass destaque)**: background rgba(255,255,255, 0.12), borda rgba(255,255,255, 0.20)
3. **gl-accent (glass verde)**: background rgba(80,200,120, 0.12), borda rgba(80,200,120, 0.25)
4. **gl-gold (glass dourado)**: background rgba(212,168,67, 0.10), borda rgba(212,168,67, 0.20)

### Botões
- Primário: background rgba(80,200,120, 0.20), borda rgba(80,200,120, 0.30), texto #fff, border-radius: 14px
- Com pseudo ::before para efeito de luz no topo
- Secundário: mesma estrutura do glass normal

### Pills/Badges
- border-radius: 20px
- background rgba(80,200,120, 0.15), borda rgba(80,200,120, 0.25)
- Texto #7DDFAA

### Search Bar
- border-radius: 14px
- background rgba(255,255,255, 0.06)
- borda rgba(255,255,255, 0.10)
- placeholder color rgba(255,255,255, 0.35)

### Tab Bar
- background rgba(255,255,255, 0.06)
- border-top 0.5px rgba(255,255,255, 0.08)
- Ícone ativo: #7DDFAA
- Ícone inativo: rgba(255,255,255, 0.35)
- Botão central (câmera): background rgba(80,200,120, 0.20), borda rgba(80,200,120, 0.30), border-radius circular

### Barras de preço (comparação)
- Track: background rgba(255,255,255, 0.04), borda rgba(255,255,255, 0.06), border-radius: 12px
- Fill: cores semi-transparentes (cada loja tem uma cor):
  - Tesco: rgba(133,183,235, 0.30)
  - Lidl: rgba(240,153,123, 0.35)
  - Aldi: rgba(124,140,240, 0.40)
  - Dunnes: rgba(93,202,165, 0.30)
  - SuperValu: rgba(240,214,138, 0.30)
- Fill tem ::before com gradiente branco 15% no topo (efeito glass na barra)
- Preço mais barato: cor #7DDFAA + check circle verde

### Avatar/Iniciais
- background rgba(255,255,255, 0.08)
- borda rgba(255,255,255, 0.15)
- Texto #7DDFAA

## PLANO DE IMPLEMENTAÇÃO

### Fase 1 — Design Tokens e Componentes Base
Atualizar/criar estes arquivos:
1. `constants/colors.ts` — novo tema Liquid Glass (todas as cores acima)
2. `components/ui/Card.tsx` — glass card com 4 variantes (gl, gl-bright, gl-accent, gl-gold)
3. `components/ui/Badge.tsx` — pills translúcidas
4. `components/ui/Button.tsx` — botões glass
5. `components/ui/StoreTag.tsx` — tags de loja com cores corretas

### Fase 2 — Layout Base
6. `app/(tabs)/_layout.tsx` — tab bar glass + fundo escuro
7. `app/_layout.tsx` — StatusBar light (texto branco)

### Fase 3 — Telas (uma por uma)
8. `app/(tabs)/index.tsx` — Home (savings card, deals, raffle, shortcuts)
9. `app/(tabs)/prices.tsx` — Comparação de preços (barras glass, value tips)
10. `app/(tabs)/scan.tsx` — Câmera (já é dark, ajustar badges)
11. `app/(tabs)/chat.tsx` — Chatbot (bolhas glass)
12. `app/(tabs)/profile.tsx` — Perfil
13. `app/(tabs)/history.tsx` — Histórico de recibos
14. `app/(tabs)/settings.tsx` — Settings
15. `app/rewards/index.tsx` — Rewards/Pontos (earn methods, leaderboard, raffle)
16. `app/usual-shop.tsx` — My Usual Shop
17. `app/shopping-list.tsx` — Shopping List
18. `app/barcode-scanner.tsx` — Barcode scanner
19. `app/link-barcodes.tsx` — Link barcodes após recibo
20. `app/onboarding.tsx` — Onboarding slides
21. `app/receipt/[id].tsx` — Detalhe do recibo
22. `app/(auth)/login.tsx` — Login
23. `app/(auth)/register.tsx` — Registo

### Fase 4 — Polish
24. Verificar todas as telas em light/dark mode
25. Ajustar StatusBar em todas as telas
26. Verificar legibilidade de todos os textos
27. Testar no Expo Go (iPhone)

## REGRAS IMPORTANTES

1. **NÃO QUEBRAR FUNCIONALIDADE** — é só visual. Lógica, API calls, navigation, state management ficam intactos.
2. **Manter os mesmos componentes** — não criar componentes novos desnecessários. Atualizar os existentes.
3. **Consistência** — todas as telas devem usar o mesmo design system. Nada de misturar estilos.
4. **Performance** — evitar sombras pesadas ou blur() que mata performance em React Native. Usar backgrounds semi-transparentes em vez de blur real.
5. **TypeScript** — zero erros no final. Rodar `npx tsc --noEmit`.
6. **Backend tests** — 94 testes devem continuar passando (é só frontend, mas verificar).
7. **Commitar** após cada fase completa.
8. **Começar sempre por ler o SKILL.md** de frontend-design antes de implementar.

## COMEÇA PELA FASE 1

Faz a varredura do repositório, entende a estrutura atual dos componentes, e começa atualizando os design tokens e componentes base. Me mostra o resultado de cada fase antes de avançar.

O projeto é MEU, eu mando. Qualquer mudança grande me pergunta antes.
