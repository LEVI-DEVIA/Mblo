# Sources de données BRVM

Inventaire réalisé le 18 septembre 2026. Toutes les pages ont été testées en HTTP simple (requests, sans navigateur) et répondent en moins de 3 secondes. Aucune ne demande de compte.

## Vue d'ensemble

| Besoin | Source retenue | Secours |
|---|---|---|
| Cours, volumes, variation du jour | brvm.org, page cours-actions | SikaFinance, page A à Z |
| Date de séance, PER et dividende officiels | Bulletin Officiel de la Cote (PDF brvm.org) | SikaFinance, fiche société |
| Historique des cours (3 ans et plus) | SikaFinance, page historiques et export CSV | Bulletins PDF archivés |
| Fondamentaux 5 ans (CA, résultat net, BPA, PER, dividende) | SikaFinance, fiche société | Bulletin PDF (PER et dividende seulement) |
| Nombre de titres, capitalisation | brvm.org, page capitalisations | SikaFinance, fiche société |
| Indices (Composite, BRVM-30, sectoriels) | brvm.org, page indices | SikaFinance, page A à Z |
| Calendrier des dividendes | SikaFinance, page dividendes | Bulletin PDF |
| Actualités marché | SikaFinance, actualités bourse | Richbourse |
| Publications officielles des sociétés (AG, rapports, suspensions) | SikaFinance, communiqués BRVM | Richbourse |

---

## 1. brvm.org (site officiel de la bourse)

Site Drupal, tableaux HTML statiques, pas d'API JSON. Le fichier robots.txt impose un **délai de 10 secondes entre deux requêtes**. À respecter.

Les pages affichent la **séance en cours** pendant les heures de bourse. L'ingestion doit tourner après la clôture.

### 1.1 Cours des actions

`https://www.brvm.org/fr/cours-actions/0`

Quatrième tableau de la page, 47 lignes, une par société cotée.

| Colonne | Exemple | Note |
|---|---|---|
| Symbole | `SNTS` | ticker, 4 à 5 lettres |
| Nom | `SONATEL` | |
| Volume | `65 452` | espaces comme séparateur de milliers |
| Cours veille (FCFA) | `39 250` | |
| Cours Ouverture (FCFA) | `42 190` | |
| Cours Clôture (FCFA) | `42 190` | |
| Variation (%) | `7,49` | virgule décimale |

Les trois premiers tableaux donnent le Top 5, le Flop 5 et l'activité du marché (valeur des transactions, capitalisation actions et obligations).

**Limite** : la date de séance n'est pas écrite sur la page. Elle est prise dans le bulletin PDF ou dans l'historique SikaFinance.

### 1.2 Cours par secteur

`https://www.brvm.org/fr/cours-actions/{id}` avec id de 194 à 200

Même tableau, filtré par secteur, avec le nom du secteur en titre. Sert à construire la table ticker → secteur une fois, puis rarement.

### 1.3 Capitalisations

`https://www.brvm.org/fr/capitalisations/0`

| Colonne | Exemple |
|---|---|
| Code | `SNTS` |
| Nom | `SONATEL` |
| Nombre de titres | `100 000 000` |
| Cours du jour | `42 190` |
| Capitalisation flottante | |
| Capitalisation globale | |
| Capitalisation globale (%) | poids dans le marché |

Le nombre de titres change rarement. Une lecture par semaine suffit.

### 1.4 Indices

`https://www.brvm.org/fr/indices/0`

Trois tableaux : indices principaux (BRVM-30, BRVM Composite, Prestige), indices sectoriels, indice total return. Colonnes : fermeture précédente, fermeture, variation du jour, variation depuis le 31 décembre.

### 1.5 Bulletin Officiel de la Cote (BOC)

`https://www.brvm.org/fr/bulletins-officiels-de-la-cote` liste les PDF. Chaque bulletin est à l'adresse `https://www.brvm.org/sites/default/files/boc_AAAAMMJJ_2.pdf` (le bulletin du 17 septembre 2026 est `boc_20260917_2.pdf`). Il est publié le soir ou le lendemain matin.

20 pages. Contenu utile :

- Page 1 : indices, capitalisation, volumes, nombre de titres en hausse et en baisse, plus fortes hausses et baisses, indices sectoriels avec **PER moyen par secteur**.
- Page 2 : **la date de séance** (« jeudi 17 septembre 2026 »).
- Pages 3 et suivantes : une ligne par titre avec code secteur (CB, CD, ENE, FIN…), ticker, nom, cours veille, ouverture, clôture, variation, volume, valeur, variation annuelle, **dividende net, date de détachement, rendement, PER**. Les titres suspendus portent la mention `SP`.

C'est la **source de référence** : officielle, datée, avec PER et dividende. L'extraction du texte fusionne parfois deux colonnes (`40,520-août-21`), le parseur devra séparer par expressions régulières et vérifier chaque ligne contre les cours HTML du même jour.

### 1.6 Actualités

`https://www.brvm.org/fr/actualites` : peu d'articles, contenu institutionnel. Non retenu pour l'instant.

---

## 2. SikaFinance

Site d'information financière ivoirien, le plus complet sur la BRVM. HTML statique, pas de délai imposé dans robots.txt (seules les zones `/docs/`, `/listes/` et `/portif/` sont interdites). On s'imposera **2 secondes entre deux requêtes** par courtoisie.

Les tickers portent un suffixe pays : `SNTS.sn`, `ABJC.ci`, `BOAB.bj`, `BOABF.bf`, `BOAM.ml`, `ONTBF.bf`, `ETIT.tg`… La correspondance ticker BRVM → identifiant SikaFinance se construit une fois depuis la page A à Z.

Les données de SikaFinance sont protégées par le droit d'auteur. Usage interne pour calcul, jamais de reproduction de leurs textes ni de leurs conseils. Un contact pour partenariat est à prévoir avant le lancement public.

### 2.1 Toutes les valeurs de A à Z

`https://www.sikafinance.com/marches/aaz`

Deuxième tableau, 48 lignes : Nom, Ouverture, Plus haut, Plus bas, Volume (titres), Volume (XOF), Dernier, Variation. Le premier tableau donne les indices sectoriels. Les liens de chaque ligne fournissent l'identifiant `cotation_XXXX.cc`.

Sert de contrôle croisé des cours brvm.org et de source des plus haut et plus bas du jour.

### 2.2 Fiche de cotation

`https://www.sikafinance.com/marches/cotation_SNTS.sn`

Cinq petits tableaux : volumes, ouverture, plus haut, plus bas, clôture veille ; **RSI et bêta 1 an** ; capital échangé et valorisation ; plus haut, plus bas et variation sur 1 semaine, 1 mois, depuis le 1er janvier, 1 an, 3 ans ; **dividendes par année avec rendement** (5 ans).

### 2.3 Historique des cours

`https://www.sikafinance.com/marches/historiques/SNTS.sn`

Tableau de 64 séances par défaut : Date, Clôture, Plus bas, Plus haut, Ouverture, Volume titres, Volume FCFA, Variation. Un formulaire (période journalière à annuelle, date de début, date de fin) permet de remonter plus loin. C'est la source du **chargement initial de l'historique** et du calcul des moyennes mobiles, du RSI et des plus haut et bas 52 semaines.

### 2.4 Export CSV

`https://www.sikafinance.com/marches/download/SNTS.sn`

Formulaire date de début, date de fin, limité à **un mois par téléchargement**. Fichier CSV : date, ouverture, plus haut, plus bas, clôture, volume. Pour 3 ans d'historique sur 47 titres, environ 1 700 requêtes à faire une seule fois, à 2 secondes d'intervalle, soit une heure.

### 2.5 Fiche société

`https://www.sikafinance.com/marches/societe/SNTS.sn`

Tableau 5 ans (2021 à 2025) :

| Ligne | Exemple SONATEL 2025 |
|---|---|
| Chiffre d'affaires (millions FCFA) | 1 923 122 |
| Croissance CA | 8,26 % |
| Résultat net | 413 588 |
| Croissance RN | 5,06 % |
| BNPA (bénéfice net par action) | 4 136,00 |
| PER | 10,20 |
| Dividende | 1 740,00 |

Plus le profil : activité, dirigeants, nombre de titres, flottant, valorisation, principaux actionnaires. Mise à jour annuelle après publication des comptes. Une lecture par mois suffit.

### 2.6 Calendrier des dividendes

`https://www.sikafinance.com/marches/dividendes`

Premier tableau : dividendes à venir (date de détachement, société, montant, rendement). Deuxième tableau, 40 lignes : dividende et rendement sur 4 ans pour chaque société. Lecture hebdomadaire.

### 2.7 Actualités bourse BRVM

`https://www.sikafinance.com/marches/actualites_bourse_brvm`

Liste `li.news-item` avec un lien `a.news-thumb`, un chapeau `div.news-chapeau` et une date `time.news-date` (attribut `datetime` ISO). Les articles marqués `(P)` sont réservés aux abonnés premium : on n'en lit que le titre et le chapeau. Sert au « à retenir » du résumé quotidien et à l'outil actualités de l'agent. Lecture à chaque ingestion.

La page d'actualités par valeur (`news_valeur?s=SNTS.sn`) ne renvoie pas de contenu en HTTP simple. On filtrera la liste générale par nom de société.

### 2.8 Communiqués officiels

`https://www.sikafinance.com/marches/communiques_brvm`

Tableau Date, Publication : avis de convocation d'assemblées, rapports des commissaires aux comptes, paiements de dividendes, suspensions. Lecture à chaque ingestion. Source précieuse pour les alertes.

### 2.9 Analyses et conseils

`https://www.sikafinance.com/analyses/conseil/SNTS.sn`

Conseils propres à SikaFinance. **Non utilisé** : Mblo produit ses propres analyses à partir des chiffres.

---

## 3. Richbourse

`https://www.richbourse.com/common/actualite/index`

Liste des publications officielles (paiement de dividendes, rapports d'activité, suspensions de cotation, homologations AMF-UMOA) avec la date dans l'adresse de chaque document. Redondant avec les communiqués SikaFinance. Gardé en secours.

---

## 4. Points de vigilance

- **Séance en cours** : brvm.org et SikaFinance affichent les chiffres intraday. Ne jamais enregistrer avant la clôture, et dater chaque ligne avec la date lue dans le bulletin ou l'historique, jamais avec la date d'insertion.
- **Formats numériques** : espaces (et parfois espaces insécables) pour les milliers, virgule décimale, signe moins collé. Un seul nettoyeur commun, testé.
- **Titres suspendus** : mention `SP` dans le bulletin, ligne sans volume sur les pages HTML. À stocker comme état, l'agent doit le dire.
- **PER non calculable** : BPA absent ou négatif. Ne jamais diviser par zéro, marquer le PER comme indisponible.
- **Changements de structure** : sauvegarder chaque page brute dans Blob, et alerter si le nombre de lignes du jour diffère de la veille de plus de 2.
- **Fractionnement d'actions** : Sonatel prépare un fractionnement (AGE du 8 octobre 2026). Les historiques devront être ajustés, sinon les moyennes mobiles et les variations deviennent fausses. À prévoir dans le modèle de données dès le départ (facteur d'ajustement par titre et par date).

---

## 5. Plan d'ingestion

| Quand | Quoi | Source |
|---|---|---|
| Chaque jour de bourse, 16:30 UTC | Cours, volumes, indices, actualités, communiqués | brvm.org cours-actions et indices, SikaFinance A à Z, actualités, communiqués |
| Lendemain, 06:00 UTC | Réconciliation officielle : date de séance, PER, dividende, rendement, suspensions | Bulletin PDF |
| Chaque lundi | Nombre de titres, capitalisation, calendrier des dividendes | brvm.org capitalisations, SikaFinance dividendes |
| Chaque mois | Fondamentaux 5 ans, profil société | SikaFinance fiche société |
| Une fois, au lancement | Historique 3 ans de tous les titres | SikaFinance export CSV ou historiques |

Volume quotidien : une dizaine de requêtes vers brvm.org (une minute et demie avec le délai de 10 secondes) et une centaine vers SikaFinance (moins de 4 minutes). Le job tient largement dans une exécution de 10 minutes.
