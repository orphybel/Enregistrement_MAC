# Enregistrement MAC — relevé des adresses MAC au banc de test

Les appareils sont branchés **un par un** sur le même accès LAN. Tftpd32 leur
attribue à chaque fois **la même adresse IP**, effacée avant de brancher le
suivant.

Ce programme surveille cette adresse IP. Dès qu'un appareil se présente, il
affiche sa MAC, sonne, et attend le numéro de l'appareil — dont il n'y a que
**les cinq derniers chiffres à taper**. Il constitue ainsi une liste
`numéro ; MAC`, puis produit les fichiers que
[ExtractionMAC](https://github.com/orphybel/Extraction_Mac) reprend pour écrire
chaque MAC dans la bonne cellule de la bonne fiche de test Excel.

```
appareil branché ──► Enregistrement MAC ──► MAC-releves.csv
                                        └─► MAC-releves\*.rtf ──► ExtractionMAC ──► fiche .xlsx
```

## Installation

### Option 1 — l'exécutable (rien à installer)

`EnregistrementMAC.exe` est autonome : ni Python, ni bibliothèque, ni droits
administrateur pour le lancer. Le copier où l'on veut et double-cliquer.

Il est reconstruit à chaque modification du code par
[l'action GitHub « Construire l'exécutable Windows »](../../actions/workflows/build-exe.yml) :
ouvrir la dernière exécution réussie et télécharger l'artefact
**EnregistrementMAC-windows**. Il contient l'exécutable et son empreinte SHA-256.

> Le premier lancement peut déclencher un avertissement SmartScreen
> (« Windows a protégé votre ordinateur ») : c'est le comportement normal pour
> un exécutable non signé. *Informations complémentaires* → *Exécuter quand même*.
> Certains antivirus signalent aussi à tort les exécutables PyInstaller ; comparer
> l'empreinte SHA-256 fournie permet de vérifier que le fichier est bien celui produit.

### Option 2 — depuis les sources

Le programme n'utilise que la bibliothèque standard de Python : **aucun
`pip install` n'est nécessaire**.

1. Installer Python 3.8 ou plus récent depuis <https://www.python.org/downloads/windows/>
   en cochant **« Add python.exe to PATH »** et **« tcl/tk and IDLE »**.
2. Double-cliquer sur `Lancer_EnregistrementMac.bat`.

`Creer_executable.bat` refabrique l'exécutable localement, sur un poste Windows
disposant de Python.

## Utilisation

### Réglages, une fois par série

| Champ | Rôle |
| --- | --- |
| **Adresse IP surveillée** | celle que Tftpd32 distribue, par exemple `192.168.0.100`. Le bouton *Tester* dit immédiatement qui répond. |
| **Préfixe du numéro** | le début du numéro de série, commun à toute la série : `260918-0144215`. Le bouton *Déduire du dossier* le trouve tout seul à partir des noms des fiches Excel. |
| **Dossier des fiches Excel** | le dossier contenant les `.xlsx` à compléter. Sert aussi à vérifier les numéros saisis. |
| **Fichier liste (CSV)** | où s'écrit la liste. Proposé automatiquement dans le dossier des fiches. |

Saisir un nom dans le champ **Profil** puis cliquer sur **Enregistrer** : tout
est mémorisé. Au lancement suivant, le dernier profil utilisé est rechargé.

### Le cycle, appareil par appareil

1. **Démarrer la surveillance**.
2. Brancher l'appareil. Le programme sonne et affiche sa MAC en grand ; le
   curseur est déjà dans le champ du numéro.
3. Taper les derniers chiffres — `92` suffit pour `00092` — puis **Entrée**.
   Le numéro complet reconstitué s'affiche avant validation.
4. Débrancher l'appareil. Le programme vide le cache ARP et se réarme seul.
   Retour à l'étape 2.
5. En fin de série : **Générer les fichiers pour ExtractionMAC**.

### Contrôles à la saisie

Rien n'est ajouté à la liste en silence. Le programme demande confirmation si :

- le numéro est **déjà dans la liste** ;
- la MAC est **déjà relevée sous un autre numéro** ;
- **aucune fiche Excel du dossier ne porte ce numéro** — c'est ce qui attrape
  les fautes de frappe sur les cinq chiffres.

## Le point délicat : le cache ARP

C'est la seule vraie difficulté du montage, et elle mérite d'être comprise.

Windows garde en mémoire l'association « adresse IP → adresse MAC » pendant
quelques dizaines de secondes. Comme **tous les appareils reçoivent la même
IP**, après un échange rapide cette mémoire peut encore contenir la MAC de
l'appareil précédent. Sans précaution, le programme enregistrerait une MAC
fausse sous un numéro juste — une erreur silencieuse, donc coûteuse.

Trois garde-fous, dans cet ordre :

1. **Une MAC identique à celle qui vient d'être enregistrée n'est jamais
   proposée.** Le programme affiche « cache ARP non vidé ou appareil non
   remplacé » et attend.
2. **L'appareil doit être vu disparaître** avant que la détection se réarme. Un
   appareil laissé branché ne peut pas être compté deux fois.
3. **Le cache est vidé automatiquement** (`arp -d`) entre deux appareils. Cette
   commande demande les **droits administrateur**.

Si le vidage échoue, le programme le dit en barre d'état et propose un bouton
*Relancer en administrateur*. Sans élévation le programme reste utilisable, mais
il ne repose alors que sur les deux premiers garde-fous : **prendre le temps de
débrancher franchement chaque appareil**.

L'exécutable ne force pas l'élévation à chaque lancement, volontairement : cela
rendrait le programme inutilisable sur un poste sans droits administrateur.

## Ce que produit le programme

### `MAC-releves.csv` — la liste de référence

Point-virgule et UTF-8 avec BOM : Excel en français l'ouvre d'un double-clic,
sans assistant d'importation.

```
numero;mac;ip;horodatage
260918-0144215-00092;00:30:D6:4C:6E:05;192.168.0.100;2026-09-11 10:14:32
260918-0144215-00093;0A:1B:2C:3D:4E:5F;192.168.0.100;2026-09-11 10:20:01
```

Ce fichier est **relu au démarrage** : la liste survit à une fermeture du
programme, et les doublons sont détectés d'une séance sur l'autre. Il s'écrit de
façon atomique — une coupure ne peut pas laisser une liste tronquée.

### `MAC-releves\*.rtf` — le relais vers ExtractionMAC

Un fichier minuscule par appareil, nommé avec le numéro de série :

```
MAC_260918-0144215-00092.rtf
    Releve automatique d'adresse physique
    Numero de serie : 260918-0144215-00092
    Adresse MAC : 00:30:D6:4C:6E:05
    Releve le 2026-09-11 a 10h14
```

ExtractionMAC accepte déjà l'extension `.rtf` : **aucune modification de ce
logiciel n'est nécessaire**. Il apparie ces fichiers aux `.xlsx` par le numéro
présent dans le nom, y lit la MAC, et l'écrit dans la cellule voulue.

## Enchaîner avec ExtractionMAC

1. **Générer les fichiers pour ExtractionMAC** : ils sont écrits dans le
   sous-dossier `MAC-releves` du dossier des fiches.
2. Ouvrir ExtractionMAC, choisir le **dossier des fiches** et cocher
   **« Inclure les sous-dossiers »**.
3. **Analyser (sans écrire)** pour vérifier, puis **Écrire dans Excel**.

> **Pourquoi un sous-dossier ?** Si un vrai `.doc` du fabricant porte le même
> numéro qu'un `.rtf` généré, ExtractionMAC voit deux fichiers Word pour un même
> numéro et refuse le couple. Le sous-dossier évite le mélange, et la génération
> **refuse d'écrire** tout numéro déjà porté par un fichier Word présent dans le
> dossier — le conflit est signalé tout de suite, pas découvert plus tard.

La génération signale aussi les numéros relevés **sans fiche Excel
correspondante** : c'est en général une faute de frappe, ou une fiche manquante.

## Répétition à blanc, sans appareil

```
EnregistrementMAC.exe --simulation
```

Des appareils fictifs se présentent l'un après l'autre : tout le déroulé
fonctionne — détection, saisie, retrait, réarmement — et un vrai CSV et de vrais
`.rtf` sont produits. Utile pour former un opérateur, ou pour vérifier un
préfixe et un dossier de fiches sans mobiliser le banc.

## Où sont enregistrés les profils

Dans **`EnregistrementMAC-config.json`, à côté de l'exécutable**. L'outil est
donc portable : copier le dossier — ou le mettre sur une clé USB — et les
profils suivent. La barre d'état affiche l'emplacement exact au démarrage.

> **Repli automatique.** Si ce dossier n'est pas accessible en écriture —
> exécutable posé dans `C:\Program Files`, sur un partage réseau en lecture
> seule, sur une clé protégée — la configuration bascule vers
> `%APPDATA%\EnregistrementMac\`. À la lecture, le fichier situé à côté de
> l'exécutable est prioritaire.
>
> En cas de doute, `EnregistrementMAC.exe --diagnostic` écrit un fichier
> `EnregistrementMAC-diagnostic.txt` indiquant les emplacements retenus.

## Développement

```
enregistrement_mac/
├── arp.py           lecture de la table ARP, sollicitation de l'IP, vidage du cache
├── numero.py        prefixe + derniers chiffres -> numéro de série canonique
├── releve.py        la liste des appareils et son fichier CSV
├── rtf.py           génération des fichiers repris par ExtractionMAC
├── surveillance.py  machine à états : attente / détecté / attente du retrait
├── simulateur.py    fausse table ARP, pour la répétition à blanc
├── config.py        profils enregistrés (à côté du programme, repli %APPDATA%)
└── gui.py           fenêtre Tkinter
```

Tests (79 cas, sans aucune donnée client, sans réseau et sans appareil) :

```
python -m unittest discover -s tests -t .
```

Le plus important d'entre eux, `TestContratExtractionMac`, repasse les fichiers
produits dans les expressions régulières d'ExtractionMAC pour vérifier qu'il en
sort **exactement une** adresse MAC et **exactement un** numéro de série. C'est
lui qui garantit que les deux logiciels restent d'accord.

Vérification de bout en bout contre le vrai code d'ExtractionMAC — relevé →
`.rtf` → ExtractionMAC → cellule Excel relue :

```
git clone https://github.com/orphybel/Extraction_Mac.git ../Extraction_Mac
python tests/verifier_chaine.py ../Extraction_Mac
```

## Réglages avancés

Certains réglages ne sont pas exposés dans la fenêtre mais modifiables dans
`EnregistrementMAC-config.json`, par profil :

| Clé | Défaut | Rôle |
| --- | --- | --- |
| `groupes_numero` | `[6, 7, 5]` | longueurs des groupes du numéro de série ; doit rester identique à celle d'ExtractionMAC |
| `sous_dossier_rtf` | `"MAC-releves"` | sous-dossier où sont générés les `.rtf` |
| `intervalle_ms` | `1500` | délai entre deux lectures de la table ARP |
| `scrutations_stables` | `3` | lectures identiques exigées avant de déclarer un appareil détecté |
| `scrutations_absence` | `2` | lectures à vide exigées avant de déclarer l'appareil retiré |
