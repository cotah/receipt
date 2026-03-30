# RELATÓRIO 1 — PLANO DE TESTE
## SmartDocket — Auditoria Técnica Completa
### Data: 30 Março 2026

---

## 1. RESUMO DO PROJETO

**O que é:** SmartDocket é um app irlandês de comparação de preços de supermercados. O usuário escaneia recibos de compra, o app extrai os produtos via AI (GPT), compara preços entre 5 supermercados (Tesco, Lidl, Aldi, SuperValu, Dunnes) e mostra onde comprar mais barato.

**Stack identificada:**
- **Mobile:** React Native + Expo SDK 54, Expo Router v6, Zustand, TypeScript
- **Backend:** FastAPI (Python 3.12), hospedado no Railway
- **Banco:** Supabase PostgreSQL com RLS
- **Cache:** Upstash Redis (TTL 10 min)
- **AI:** OpenAI GPT-4.1-nano (chat + OCR + matching)
- **Email:** Resend
- **Scraping:** Apify (Tesco, Lidl, Aldi, SuperValu)
- **Monitoramento:** Sentry
- **Pagamentos:** Stripe

**Arquitetura percebida:** Monolito backend (FastAPI) com background workers (APScheduler) + app mobile React Native que se comunica via REST API. O backend usa Supabase como DB (via client library, sem ORM/migrations tradicionais). A autenticação é via Supabase Auth (JWT) validada no backend.

**Tamanho do código:** ~21.800 linhas de código (Python + TypeScript), 51 testes backend passando, 0 erros no Sentry.

---

## 2. MAPA TÉCNICO DO SISTEMA

### Backend — Rotas/Endpoints (13 routers)
| Router | Arquivo | Linhas | Funcionalidade |
|--------|---------|--------|----------------|
| receipts | receipts.py | 997 | Upload, OCR, processamento, CRUD |
| prices | prices.py | 1248 | Comparação, busca, basket, categorias |
| admin | admin.py | 739 | Dashboard admin, métricas, gestão |
| shopping_list | shopping_list.py | 346 | CRUD lista de compras, optimizer |
| deals | deals.py | 269 | Ofertas semanais personalizadas |
| products | products.py | 248 | Busca de produtos |
| users | users.py | 174 | Profile CRUD, stats, referral |
| payments | payments.py | 125 | Stripe checkout + webhook |
| chat | chat.py | 116 | AI chat streaming (SSE) |
| feedback | feedback.py | 89 | Bug reports + email |
| alerts | alerts.py | 86 | Alertas de preço |
| leaflets | leaflets.py | 35 | Controle de scrapers |
| reports | reports.py | 24 | Relatórios mensais |

### Backend — Services (12 serviços)
| Serviço | Linhas | Funcionalidade |
|---------|--------|----------------|
| search_service | 525 | Busca inteligente, grouping, AI alternatives |
| email_service | 479 | Templates HTML, envio via Resend |
| embedding_service | 362 | RAG context, embeddings OpenAI |
| attribution_service | 309 | Rastreamento de economias |
| ocr_service | 304 | Extração de texto (imagem→text) |
| leaflet_service | 235 | Processamento de folhetos |
| extraction_service | 226 | Extração de produtos do recibo |
| alert_service | 179 | Lógica de alertas de preço |
| price_service | 170 | Lógica de preços |
| push_service | 126 | Push notifications |
| chat_service | 123 | Prompt engineering + streaming GPT |
| cache_service | 61 | Upstash Redis wrapper |

### Backend — Workers (6 workers)
| Worker | Linhas | Funcionalidade |
|--------|--------|----------------|
| leaflet_worker | 2915 | Scrapers: Tesco, Lidl, Aldi, SuperValu, Dunnes |
| deals_worker | 726 | Geração de deals semanais |
| intelligence_worker | 338 | Product patterns + analytics |
| email_report_worker | 83 | Envio de relatórios mensais |
| alerts_worker | 44 | Check de alertas de preço |
| prices_worker | 39 | Limpeza de preços expirados |

### Mobile — Telas (21 screens)
| Tela | Linhas | Função |
|------|--------|--------|
| prices.tsx | 702 | Comparação de preços + deals |
| profile.tsx | 664 | Perfil do usuário |
| scan.tsx | 379 | Câmera para escanear recibos |
| receipt/[id].tsx | 359 | Detalhe do recibo + confirmação peso |
| basket.tsx | 350 | Basket optimizer |
| index.tsx (Home) | 339 | Dashboard principal |
| settings.tsx | 316 | Configurações |
| shopping-list.tsx | 254 | Lista de compras |
| login.tsx | 251 | Tela de login |
| register.tsx | 214 | Registro |
| refer/index.tsx | 182 | Sistema de referral |
| feedback/index.tsx | 176 | Report an issue |
| history.tsx | 175 | Histórico de recibos |
| alerts/index.tsx | 122 | Notificações |
| levels/index.tsx | 118 | Progressão de níveis |
| chat.tsx | 112 | Chat AI |
| _layout.tsx (tabs) | 107 | Tab bar layout |
| report/[month].tsx | 105 | Relatório mensal |
| rewards/index.tsx | 96 | Pontos e recompensas |
| _layout.tsx (root) | 94 | Root layout + auth guard |
| auth/callback.tsx | 48 | Deep link handler |

### Mobile — Stores (4 stores Zustand)
- authStore.ts — Autenticação, profile, tokens
- receiptStore.ts — CRUD recibos
- chatStore.ts — Estado do chat
- alertStore.ts — Alertas

### Mobile — Services
- api.ts — Axios + in-memory token
- supabase.ts — Supabase client com SecureStore adapter
- notifications.ts — Push notifications

---

## 3. DETECÇÃO DE AMBIENTE

| Item | Detectado |
|------|-----------|
| Gerenciador Python | pip + requirements.txt |
| Gerenciador Node | npm (package-lock.json) |
| Framework Backend | FastAPI 0.115.0 |
| Framework Mobile | React Native 0.81.5 + Expo SDK 54 |
| Python Version | 3.12 |
| Node Version | 20 |
| Banco | Supabase PostgreSQL |
| Cache | Upstash Redis |
| Docker | Dockerfile (backend only) |
| CI/CD | GitHub Actions (ci.yml) |
| Procfile | Sim (Railway) |
| Makefile | Não |
| .env file | Referenciado em config.py, não commitado |

---

## 4. MATRIZ DE COMPONENTES E ESTRATÉGIA DE TESTE

### 4.1 Backend — Testes Unitários/Integração

| Componente | O que testar | Risco | Prioridade | Dependências |
|-----------|-------------|-------|------------|--------------|
| auth_utils.py | Validação JWT, 401 em token inválido | ALTO | P0 | Supabase Auth |
| plan_utils.py | Limites free/pro, reset contadores | ALTO | P0 | DB profiles |
| search_service.py | Normalização, grouping, word-boundary | ALTO | P0 | Nenhuma |
| extraction_service.py | OCR→produtos, parse de preços | ALTO | P0 | OpenAI |
| prices.py (/compare) | Busca, dedup, ordering | ALTO | P0 | DB, RPC |
| receipts.py (/upload) | Validação, processamento, hash check | ALTO | P0 | Storage, OCR |
| shopping_list.py | CRUD, dedup, optimizer | MÉDIO | P1 | DB |
| chat.py | Streaming SSE, history, limites | MÉDIO | P1 | OpenAI |
| payments.py | Stripe webhook, upgrade/downgrade | ALTO | P0 | Stripe |
| users.py | Profile CRUD, referral | MÉDIO | P1 | DB |
| alerts.py | CRUD, confirm saving | BAIXO | P2 | DB |
| feedback.py | Validação, email | BAIXO | P2 | Resend |
| rate_limit.py | Limites por IP, scan-specific | MÉDIO | P1 | Nenhuma |
| cache_service.py | GET/SET, fallback sem Redis | BAIXO | P2 | Redis |

### 4.2 Frontend — Validações

| Componente | O que testar | Risco | Prioridade |
|-----------|-------------|-------|------------|
| authStore.ts | Fluxos auth (Google, email, magic link, logout→login) | ALTO | P0 |
| api.ts | In-memory token, fallback, interceptors | ALTO | P0 |
| receiptStore.ts | Upload, polling, CRUD | ALTO | P0 |
| receipt/[id].tsx | TypeScript errors (image_urls), weight confirm | ALTO | P0 |
| prices.tsx | Duplicate style property, search, add to cart | MÉDIO | P1 |
| feedback/index.tsx | Colors.bg reference error | BAIXO | P2 |
| _layout.tsx | Auth guard, deep links, splash screen | ALTO | P0 |

### 4.3 Integração Frontend↔Backend

| Fluxo | O que validar | Risco |
|-------|--------------|-------|
| Login→Profile | Token → /users/me → profile loaded | ALTO |
| Scan→Process→Detail | Upload → polling → items → weight confirm | ALTO |
| Search→Compare | Busca → grouping → preços por loja | ALTO |
| Chat | SSE streaming → mensagens salvas | MÉDIO |
| Shopping List | Add from compare → optimizer | MÉDIO |
| Feedback | Submit → DB save → email send | BAIXO |
| Stripe | Checkout → webhook → plan upgrade | ALTO |

---

## 5. ISSUES JÁ IDENTIFICADAS NA VARREDURA (Pré-teste)

### ISSUE-001: TypeScript — `image_urls` não existe em `ReceiptDetail` (receipt/[id].tsx)
- **Severidade:** Major
- **Detalhes:** 10 erros TS. O backend retorna `image_urls` no detail, mas o tipo `ReceiptDetail` no frontend não declara essa propriedade.
- **Impacto:** Funciona em runtime (JS ignora tipos), mas quebra o build de produção com `--noEmit`.

### ISSUE-002: TypeScript — `Colors.bg` não existe (feedback/index.tsx)
- **Severidade:** Minor
- **Detalhes:** Referência a `Colors.bg.primary` na linha 121, mas Colors não tem propriedade `bg`.
- **Impacto:** Quebra type check, pode causar crash em runtime se acessado.

### ISSUE-003: TypeScript — Propriedade duplicada `addBtn` (prices.tsx)
- **Severidade:** Minor
- **Detalhes:** `addBtn` definido na linha 607 E 659 do StyleSheet. O segundo sobrescreve o primeiro.
- **Impacto:** Estilo possivelmente incorreto em um dos usos.

### ISSUE-004: Segurança — ADMIN_KEY vazio = acesso aberto
- **Severidade:** Critical (se em produção sem key)
- **Detalhes:** `_verify_admin_key()` retorna silenciosamente se `ADMIN_KEY` não está configurado. Debug endpoints ficam abertos.
- **Impacto:** Qualquer pessoa pode rodar scrapers, categorização, etc.

### ISSUE-005: Segurança — Sentry traces_sample_rate=1.0
- **Severidade:** Minor
- **Detalhes:** 100% de traces em produção pode gerar custo elevado no Sentry e performance overhead.

### ISSUE-006: app.json — EAS projectId placeholder
- **Severidade:** Blocker (para build)
- **Detalhes:** `"projectId": "your-project-id"` — precisa ser substituído pelo ID real para EAS Build.

### ISSUE-007: Race condition — Referral points
- **Severidade:** Major
- **Detalhes:** `redeem_referral()` faz read-then-write nos pontos sem transação. Dois requests simultâneos podem causar pontos incorretos.

### ISSUE-008: Stripe webhook — sem verificação de idempotência
- **Severidade:** Major
- **Detalhes:** Se Stripe enviar o mesmo evento 2x, o perfil será atualizado 2x. Não é destrutivo mas gera logs confusos.

---

## 6. LISTA DE INTEGRAÇÕES/APIs

| Integração | Finalidade | Modo teste | Env vars necessárias |
|-----------|-----------|------------|---------------------|
| Supabase DB | Banco de dados | Real (via service key) | SUPABASE_URL, SUPABASE_SERVICE_KEY |
| Supabase Auth | Autenticação | Mock nos testes atuais | SUPABASE_ANON_KEY |
| Supabase Storage | Upload imagens | Real | SUPABASE_URL |
| OpenAI GPT | OCR, chat, categorização | Mock (caro) | OPENAI_API_KEY |
| Stripe | Pagamentos | Mock ou test mode | STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET |
| Resend | Emails | Real (pode testar com email real) | RESEND_API_KEY |
| Upstash Redis | Cache | Real | UPSTASH_REDIS_URL, UPSTASH_REDIS_TOKEN |
| Apify | Scraping | Real (consome créditos) | APIFY_API_TOKEN |
| Sentry | Monitoramento | Real | SENTRY_DSN |
| Webshare | Proxy para scrapers | Real | WEBSHARE_PROXY_URL |

---

## 7. CRITÉRIOS DE PASS/FAIL

### Aprovado (PASS) se:
- ✅ Todos os 51 testes existentes passam
- ✅ Zero erros de sintaxe Python
- ✅ TypeScript compila sem erros de tipo bloqueantes
- ✅ Endpoints protegidos retornam 401/403 sem auth
- ✅ Fluxo principal (scan→compare) funcional
- ✅ Auth (login/logout) estável
- ✅ Zero crashes reportados no Sentry
- ✅ Sem segredos expostos no código

### Reprovado (FAIL) se:
- ❌ Testes existentes quebram
- ❌ Endpoint público expõe dados sem auth
- ❌ Crash em fluxo principal
- ❌ Segredos hardcoded no repositório
- ❌ Build de produção falha

---

## 8. CHECKLIST DE QUALIDADE

| Check | Status | Notas |
|-------|--------|-------|
| Python syntax | ✅ PASS | Todos os arquivos OK |
| pytest (51 tests) | ✅ PASS | 51/51 passando |
| TypeScript check | ❌ FAIL | 13 erros (ISSUE-001, 002, 003) |
| Auth enforcement | ✅ PASS | 403 em todos endpoints sem token |
| Health check prod | ✅ PASS | Railway respondendo |
| Secrets no código | ✅ PASS | Nenhum segredo hardcoded |
| CI/CD | ✅ PASS | GitHub Actions configurado |
| Rate limiting | ✅ PASS | Middleware presente |

---

## 9. ÁREAS CRÍTICAS E RISCOS

### Risco ALTO
1. **Google OAuth token size** — SecureStore iOS não suporta >2048 bytes. Fix atual (in-memory token) funciona mas não persiste entre reinicializações do app
2. **Stripe Webhook** — Sem idempotência, sem log de eventos processados
3. **Admin endpoints sem key** — Se ADMIN_KEY não configurado, endpoints debug ficam abertos
4. **Referral race condition** — Read-then-write sem transação

### Risco MÉDIO
5. **TypeScript errors** — 13 erros impedem build limpo de produção
6. **Rate limiter in-memory** — Não funciona em multi-instance (Railway pode escalar)
7. **app.json projectId** — Placeholder impede EAS Build
8. **Sentry 100% trace rate** — Custo + overhead em produção

### Risco BAIXO
9. **Cache TTL** — 10 min pode ser muito curto para deals (gera muitas queries)
10. **Push notifications** — Requer dev build, não funciona no Expo Go

---

## 10. PLANO DE EXECUÇÃO

### Fase 1: Corrigir TypeScript Errors (ISSUE-001, 002, 003)
→ Menor impacto, desbloqueia build de produção

### Fase 2: Testar Backend ao vivo (endpoints reais)
→ Com token real do Supabase, validar todos os fluxos

### Fase 3: Análise de segurança detalhada
→ Admin key, webhook, CORS, injection, input validation

### Fase 4: Adicionar testes para bugs encontrados
→ Teste falhando → fix → teste passando

### Fase 5: Corrigir issues encontradas
→ Um por vez, cirúrgico, sem refactor grande

### Fase 6: RELATÓRIO 2 — Resultados

---

*Relatório gerado como parte da auditoria técnica do SmartDocket.*
*Próximo passo: Iniciar execução das fases do plano acima.*
