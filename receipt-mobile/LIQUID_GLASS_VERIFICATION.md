# SmartDocket — Liquid Glass Visual Verification Guide

## Como testar
```bash
cd receipt-mobile
npx expo start --tunnel
# Scan QR code with Expo Go on iPhone
```

## Checklist visual por tela

### 1. Onboarding (primeira vez)
- [ ] Fundo verde escuro profundo
- [ ] Slides com ilustrações em cards glass translúcidos
- [ ] Dots de paginação: inativo = branco 20%, ativo = verde #7DDFAA
- [ ] Botão "Next" / "Get Started" em verde glass
- [ ] Texto branco e semi-transparente legível

### 2. Login / Register
- [ ] Fundo verde escuro
- [ ] Input fields com bg glass (rgba 0.06), borda sutil
- [ ] Botão Google com bg preto
- [ ] Botão email com bg glass
- [ ] Links em verde accent #7DDFAA
- [ ] Texto placeholder cinza claro (35% opacity)

### 3. Home (Tab principal)
- [ ] Fundo verde escuro #0d2818
- [ ] "Hi, [Nome]" em branco
- [ ] Card "Spent this month" = glass bright (12% opacity), valor em amber #F0D68A
- [ ] 3 stat cards = glass default (8% opacity)
- [ ] "My usual shop" = glass card com ícone verde
- [ ] "Shopping List" = glass card com ícone verde
- [ ] Recent Receipts = glass cards com borda colorida por loja
- [ ] Bell icon com bg glass, badge vermelho

### 4. Prices (Compare tab)
- [ ] Tabs "Compare" / "Offers" = pills glass, ativa = verde glass
- [ ] Search bar = glass (bg 0.06, borda 0.10)
- [ ] Result cards = glass com nome branco, preço amber
- [ ] Store tags = pills coloridas por loja (Tesco=azul, Lidl=coral, etc.)
- [ ] "CHEAPEST" badge = verde glass pill
- [ ] Value tips = verde glass com borda esquerda verde
- [ ] Golden Offers = glass gold com borda dourada

### 5. Scan
- [ ] Câmera com overlay escuro (já era dark)
- [ ] Botões e hints adaptados ao glass
- [ ] Processing modal = glass escuro com progress bar verde

### 6. Chat
- [ ] Fundo verde escuro
- [ ] Header "SmartDocket AI" em branco
- [ ] User bubble = verde glass com borda verde
- [ ] Assistant bubble = glass neutro com borda branca sutil
- [ ] Input = glass (bg 0.06)
- [ ] Send button = verde glass circular
- [ ] Suggestion chips = glass com texto verde

### 7. History
- [ ] Receipt cards com border-left colorida por loja
- [ ] Store name em branco, branch em 50% opacity
- [ ] Preço em amber, badges glass

### 8. Profile
- [ ] Avatar glass com iniciais verde
- [ ] Sections com glass cards
- [ ] Sign out em vermelho coral #F07B7B

### 9. Settings
- [ ] Lista de opções em glass cards
- [ ] Toggles/switches legíveis

### 10. Tab Bar (Global)
- [ ] Background glass (rgba 0.06)
- [ ] Borda top 0.5px subtle
- [ ] Ícone ativo = #7DDFAA
- [ ] Ícone inativo = branco 35%
- [ ] Botão câmera central = verde glass com glow

### 11. Status Bar (Global)
- [ ] Texto branco (hora, bateria, signal) — `style="light"`

## Cores de referência rápida

| Elemento | Cor |
|---|---|
| Background | #0d2818 |
| Card glass | rgba(255,255,255, 0.08) |
| Card bright | rgba(255,255,255, 0.12) |
| Card accent | rgba(80,200,120, 0.12) |
| Card gold | rgba(212,168,67, 0.10) |
| Border default | rgba(255,255,255, 0.15) |
| Text primary | #FFFFFF |
| Text secondary | rgba(255,255,255, 0.50) |
| Text tertiary | rgba(255,255,255, 0.35) |
| Accent green | #7DDFAA |
| Accent amber | #F0D68A |
| Accent coral | #F0997B |
| Accent red | #F07B7B |
| Accent blue | #85B7EB |
| Accent lilac | #AFA9EC |

## Se algo estiver ilegível
Aumentar a opacity do texto afetado:
- 0.35 → 0.50 (tertiary mais visível)
- 0.50 → 0.65 (secondary mais visível)
- 0.08 → 0.12 (card mais opaco)
