# Spécification technique Mblo

Ce document présente : structure du projet, modèle de données, outils de l'agent, contrat de la passerelle WhatsApp, crédits, jobs, tests. Le pourquoi est dans le [README](../README.md), les sources dans [sources-de-donnees.md](sources-de-donnees.md).

## 1. Structure du projet

```
mblo/
├── pyproject.toml
├── docker-compose.yml          # postgres + api en local
├── Dockerfile
├── alembic/                    # migrations de la base
├── src/mblo/
│   ├── config.py               # variables d'environnement, une seule lecture
│   ├── db/
│   │   ├── models.py           # tables SQLAlchemy
│   │   └── session.py
│   ├── ingest/
│   │   ├── brvm_quotes.py      # cours, indices, capitalisations
│   │   ├── brvm_boc.py         # bulletin PDF
│   │   ├── sika_history.py     # historique + CSV
│   │   ├── sika_company.py     # fondamentaux 5 ans
│   │   ├── sika_news.py        # actualités + communiqués
│   │   ├── parsing.py          # nettoyage des nombres et dates
│   │   ├── indicators.py       # MM20/50, RSI, 52 semaines, PER, rendement
│   │   └── run.py              # point d'entrée du job (daily, boc, weekly, monthly, backfill)
│   ├── agent/
│   │   ├── router.py           # Haiku : intention + coût
│   │   ├── analyst.py          # Opus : analyse avec outils
│   │   ├── tools.py            # définitions et exécution des outils
│   │   ├── prompts.py
│   │   └── schemas.py          # sortie structurée de l'analyse
│   ├── credits/
│   │   ├── ledger.py           # solde, débit, crédit, idempotence
│   │   └── tariffs.py
│   ├── channels/
│   │   ├── base.py             # interface fournisseur WhatsApp
│   │   ├── wasender.py
│   │   └── formatting.py       # texte WhatsApp (gras, listes, longueur)
│   ├── payments/
│   │   └── cinetpay.py
│   ├── digest/
│   │   ├── build.py            # résumé du jour + alertes → outbox
│   │   └── sender.py           # worker : vide l'outbox à cadence limitée
│   ├── conversation/
│   │   ├── handler.py          # reçoit un message, orchestre tout
│   │   ├── onboarding.py
│   │   └── memory.py
│   └── api/
│       ├── main.py             # FastAPI
│       ├── webhooks.py         # /webhooks/whatsapp, /webhooks/cinetpay
│       └── admin.py            # endpoints du dashboard
├── tests/
│   ├── fixtures/               # pages HTML et PDF sauvegardés
│   ├── test_parsing.py
│   ├── test_ingest_*.py
│   ├── test_ledger.py
│   ├── test_handler.py
│   └── evals/                  # jeu de questions de référence
└── dashboard/                  # Next.js, plus tard
```

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, httpx, BeautifulSoup, pypdf, SDK Anthropic, Langfuse. Pas de LangChain.

## 2. Modèle de données

Toutes les dates de marché sont des dates de séance, jamais des dates d'insertion. Montants en FCFA, entiers quand c'est possible.

### Marché

**company** : `id`, `ticker` (unique), `name`, `sika_id` (ex. `SNTS.sn`), `sector_code`, `sector_name`, `country`, `shares_outstanding`, `float_pct`, `is_suspended`, `updated_at`.

**daily_quote** : `company_id`, `session_date`, `open`, `high`, `low`, `close`, `prev_close`, `volume`, `value_fcfa`, `change_pct`, `source`, `adjusted_factor` (1.0 par défaut, modifié en cas de fractionnement). Unicité `(company_id, session_date)`.

**daily_official** (issu du bulletin PDF) : `company_id`, `session_date`, `per`, `dividend_net`, `ex_dividend_date`, `yield_pct`, `ytd_pct`, `is_suspended`. Unicité `(company_id, session_date)`.

**indicator** : `company_id`, `session_date`, `ma20`, `ma50`, `rsi14`, `high_52w`, `low_52w`, `avg_volume_20`, `volume_ratio`, `per`, `yield_pct`, `sector_per_avg`. Unicité `(company_id, session_date)`.

**fundamental** : `company_id`, `fiscal_year`, `revenue`, `revenue_growth`, `net_income`, `net_income_growth`, `eps`, `per`, `dividend`. Unicité `(company_id, fiscal_year)`.

**index_quote** : `index_name`, `session_date`, `prev_close`, `close`, `change_pct`, `ytd_pct`.

**dividend_event** : `company_id`, `ex_date`, `amount`, `yield_pct`, `source`.

**news** : `id`, `published_at`, `title`, `summary`, `url`, `source`, `kind` (article, communiqué), `company_id` (nullable, déduit par nom), `is_premium`.

**corporate_action** : `company_id`, `effective_date`, `kind` (split, …), `factor`. Applique le facteur aux cotations antérieures.

### Utilisateurs et crédits

**user** : `id`, `phone` (unique, E.164), `display_name`, `language` (fr), `goal` (revenus, long_terme, speculation), `horizon`, `capital_range`, `sgi_name`, `digest_subscribed` (bool), `onboarding_step`, `created_at`, `last_seen_at`.

**credit_ledger** : `id`, `user_id`, `created_at`, `kind` (welcome, debit, recharge, adjustment), `amount` (signé), `balance_after`, `action` (causerie, analyse, …), `reference` (id de message ou de transaction), `meta` json. Index sur `(user_id, created_at)`. Unicité sur `reference` pour les recharges.

**tariff** : `action` (clé), `credits`, `label`, `active`. Valeurs initiales : causerie 10, analyse 150, comparaison 250, digest 0.

**payment** : `id`, `user_id`, `provider` (cinetpay), `provider_ref` (unique), `amount_fcfa`, `credits`, `status` (pending, paid, failed), `created_at`, `paid_at`, `raw` json.

**watchlist** : `user_id`, `company_id`, `added_at`. **position** : `user_id`, `company_id`, `quantity`, `avg_price`, `updated_at`.

### Conversation et mémoire

**message** : `id`, `user_id`, `direction` (in, out), `channel_msg_id`, `text`, `media_type`, `created_at`, `credits_charged`, `trace_id` (Langfuse).

**advice** : `id`, `user_id`, `company_id`, `created_at`, `verdict`, `confidence`, `price_at_advice`, `summary`, `full` json. C'est ce qui permet « je t'avais parlé de SNTS à 39 250 ».

**user_memory** : `user_id`, `key`, `value`, `updated_at`. Faits durables extraits des échanges (préférences, contraintes).

**outbox** : `id`, `user_id`, `kind` (digest, alert, system), `text`, `scheduled_for`, `sent_at`, `status`, `attempts`, `dedupe_key` (unique, ex. `digest:2026-09-18:42`).

**digest** : `session_date` (unique), `market_text`, `built_at`. Généré une fois, partagé par tous.

## 3. Traitement d'un message entrant

```
webhook WhatsApp
 1. valider la signature, ignorer les doublons (channel_msg_id)
 2. charger ou créer l'utilisateur (phone)
 3. enregistrer le message entrant
 4. mots-clés gratuits, avant tout LLM :
      recharge          → lien CinetPay
      solde / tarifs    → solde + barème
      résumé oui/stop   → abonnement
      stop              → désinscription totale
 5. onboarding inachevé → étape suivante (nom, objectif, horizon, SGI), puis
      +1000 crédits (welcome), barème, proposition d'abonnement au résumé
 6. routeur (Haiku 4.5) → intention ∈ {causerie, analyse, comparaison, digest,
      watchlist, portefeuille, hors_sujet} + tickers détectés
 7. coût = tariff[intention] (digest et watchlist : 0)
 8. solde < coût → message « coût, solde, recharge, barème », fin
 9. exécuter :
      causerie      → réponse courte (Haiku)
      digest        → texte du jour + partie watchlist, 0 crédit
      analyse       → analyste (Opus) + outils
      comparaison   → analyste (Opus) + outils, 2 à 3 tickers
      watchlist     → ajout / retrait, 0 crédit
10. débit (ledger), enregistrer advice si analyse, message sortant
11. envoyer via le fournisseur, tracer dans Langfuse
```

Toute erreur après l'étape 8 annule le débit. Le débit n'est écrit qu'une fois la réponse générée.

Notes vocales : transcription (à choisir, hors périmètre de la première version), puis même circuit.

## 4. Les outils de l'agent analyste

Tous lisent la base. Aucun n'accède au web. Chaque résultat porte sa `session_date` pour que l'agent cite des chiffres datés.

| Outil | Paramètres | Retour |
|---|---|---|
| `get_quote` | ticker | dernière séance : close, change_pct, volume, prev_close, is_suspended, session_date |
| `get_history` | ticker, days (≤ 750) | liste de (date, close, volume) ajustée des fractionnements |
| `get_indicators` | ticker | ma20, ma50, rsi14, high_52w, low_52w, volume_ratio, per, yield_pct, sector_per_avg, position vs MM |
| `get_fundamentals` | ticker | 5 ans : revenue, net_income, eps, per, dividend, croissances |
| `get_dividends` | ticker | historique 5 ans + prochain détachement |
| `get_news` | ticker ou null, days | titres, dates, résumés, type |
| `get_sector_peers` | ticker | même secteur : close, per, yield_pct, change_ytd |
| `screen` | critères (per_max, yield_min, sector, trend) | liste de tickers avec valeurs |
| `get_user_context` | — | objectif, horizon, capital_range, watchlist, positions, derniers conseils |
| `resolve_company` | texte libre | ticker le plus probable (« Sonatel » → SNTS) |

### Sortie structurée de l'analyse

```json
{
  "ticker": "SNTS",
  "verdict": "acheter | conserver | vendre | attendre",
  "confidence": "faible | moyenne | forte",
  "one_liner": "phrase de synthèse",
  "thesis": ["point 1", "point 2", "point 3"],
  "risks": ["risque 1", "risque 2"],
  "key_figures": {"close": 42190, "per": 10.2, "yield_pct": 4.1, "rsi14": 72},
  "data_date": "2026-09-18",
  "sources": ["brvm.org", "BOC 17/09/2026", "SikaFinance"]
}
```

Le texte WhatsApp est rendu à partir de ce JSON, pas écrit librement par le modèle. Contrôles avant envoi : le ticker existe, chaque chiffre de `key_figures` correspond à la base, la réponse fait moins de 1 200 caractères.

### Prompt de l'analyste, principes

- Français correct et simple, phrases courtes, termes techniques expliqués en quelques mots à la première occurrence.
- Adapter à l'objectif de l'utilisateur : revenus (rendement, régularité du dividende), long terme (croissance du résultat, solidité), spéculation (tendance, volume, RSI).
- Présenter, ne pas ordonner. Toujours au moins un risque. Dire quand une donnée manque et baisser la confiance.
- Ne jamais inventer un chiffre : tout vient des outils.

## 5. Passerelle WhatsApp

Interface unique, implémentée d'abord pour WasenderAPI :

```python
class WhatsAppProvider(Protocol):
    def parse_incoming(self, payload: dict, headers: dict) -> IncomingMessage | None
    def send_text(self, phone: str, text: str) -> str          # retourne l'id fournisseur
    def send_typing(self, phone: str) -> None
    def download_media(self, media_id: str) -> bytes
```

`IncomingMessage` : `phone`, `channel_msg_id`, `text`, `media_type`, `media_id`, `timestamp`. Les messages de groupe et les statuts sont ignorés.

Règles d'envoi : réponses immédiates ; messages proactifs via l'outbox seulement, cadence globale configurable (`SEND_RATE_PER_MIN`, 20 au départ), délai aléatoire de 1 à 4 secondes entre deux envois, pause globale possible depuis le dashboard (`sending_paused`).

## 6. Paiement CinetPay

- `recharge` → création d'un paiement (500 FCFA, `transaction_id` = uuid), lien envoyé, ligne `payment` en `pending`.
- Webhook CinetPay → vérification de la signature et du statut auprès de l'API (jamais confiance au seul webhook), passage en `paid`, ligne `credit_ledger` de +1000 avec `reference = provider_ref` (unicité = idempotence), message de confirmation via l'outbox.
- Paiement `pending` depuis plus de 24 h → `failed`.

## 7. Jobs planifiés

| Job | Horaire (UTC) | Commande |
|---|---|---|
| Ingestion quotidienne | lun–ven 16:30 | `mblo-ingest daily` |
| Réconciliation bulletin | mar–sam 06:00 | `mblo-ingest boc` |
| Digest et alertes | lun–ven 17:00 | `mblo-digest build` |
| Hebdomadaire | lun 05:00 | `mblo-ingest weekly` |
| Mensuel | 1er du mois 05:00 | `mblo-ingest monthly` |
| Chargement initial | une fois | `mblo-ingest backfill --years 3` |

Le worker d'envoi tourne en continu dans le conteneur de l'API. Chaque job est idempotent : relancé deux fois, il ne duplique rien.

Le digest : `market_text` généré une fois (Opus, à partir des indices, tops, flops et actualités du jour, 8 lignes max), puis pour chaque abonné (`digest_subscribed`) une ligne `outbox` avec la partie watchlist personnalisée. Le résumé est gratuit : aucun débit.

## 8. Configuration

Variables d'environnement, lues une fois dans `config.py` :

`DATABASE_URL`, `ANTHROPIC_API_KEY`, `MODEL_ANALYST` (claude-opus-5), `MODEL_ROUTER` (claude-haiku-4-5), `WASENDER_API_KEY`, `WASENDER_WEBHOOK_SECRET`, `CINETPAY_API_KEY`, `CINETPAY_SITE_ID`, `CINETPAY_SECRET`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `ADMIN_TOKEN`, `SEND_RATE_PER_MIN`, `PUBLIC_BASE_URL`.

En production, elles viennent de Key Vault. En local, d'un fichier `.env` non versionné.

## 9. Tests et evals

- **Parsing** : chaque source a une page sauvegardée dans `tests/fixtures/`. Les tests vérifient les colonnes, le nombre de lignes et quelques valeurs connues.
- **Ledger** : débit refusé sous le solde, recharge en double ignorée, solde égal à la somme des lignes.
- **Handler** : mots-clés gratuits, onboarding, refus à solde insuffisant, annulation du débit si erreur.
- **Evals de l'agent** : `tests/evals/questions.jsonl`, 40 questions au départ (analyse, comparaison, question naïve, ticker inexistant, titre suspendu, donnée manquante). Pour chaque réponse on vérifie : ticker correct, chiffres présents en base, verdict cohérent avec les indicateurs, au moins un risque, longueur. Score suivi dans Langfuse.

## 10. Ordre de construction

1. Base, migrations, parsing, ingestion quotidienne et bulletin, tests sur fixtures.
2. Indicateurs et chargement initial de l'historique.
3. Outils, routeur, analyste, sortie structurée, evals.
4. Handler de conversation, onboarding, crédits, formatage WhatsApp.
5. Passerelle WasenderAPI, webhooks.
6. CinetPay.
7. Digest, outbox, worker.
8. Déploiement Azure, Langfuse.
9. Dashboard admin.
