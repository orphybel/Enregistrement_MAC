"""Tests d'Enregistrement MAC. Aucune donnee client, aucun reseau, aucun appareil."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest

from enregistrement_mac import (arp, config, numero, releve, rtf, simulateur,
                                surveillance)


# ==========================================================================
# lecture de la table ARP
# ==========================================================================

TABLE_FR = """
Interface : 192.168.0.10 --- 0xb
  Adresse Internet      Adresse physique      Type
  192.168.0.100         00-30-d6-4c-6e-05     dynamique
  192.168.0.255         ff-ff-ff-ff-ff-ff     statique
  224.0.0.22            01-00-5e-00-00-16     statique
"""

TABLE_EN = """
Interface: 192.168.0.10 --- 0xb
  Internet Address      Physical Address      Type
  192.168.0.100         00-30-d6-4c-6e-05     dynamic
"""


class TestArp(unittest.TestCase):
    def test_table_francaise(self):
        table = arp.analyser_table(TABLE_FR)
        self.assertEqual(table["192.168.0.100"], "00:30:D6:4C:6E:05")

    def test_table_anglaise_donne_le_meme_resultat(self):
        """La lecture ne doit dependre ni de la langue ni des en-tetes."""
        self.assertEqual(arp.analyser_table(TABLE_EN)["192.168.0.100"],
                         arp.analyser_table(TABLE_FR)["192.168.0.100"])

    def test_en_tete_sans_mac_est_ignore(self):
        self.assertNotIn("192.168.0.10", arp.analyser_table(TABLE_FR))

    def test_format_linux(self):
        table = arp.analyser_table("? (192.168.0.100) at 00:30:d6:4c:6e:05 [ether] on eth0")
        self.assertEqual(table, {"192.168.0.100": "00:30:D6:4C:6E:05"})

    def test_format_ip_neigh(self):
        table = arp.analyser_table("192.168.0.100 dev eth0 lladdr 00:30:d6:4c:6e:05 REACHABLE")
        self.assertEqual(table, {"192.168.0.100": "00:30:D6:4C:6E:05"})

    def test_sortie_vide_ou_parasite(self):
        self.assertEqual(arp.analyser_table(""), {})
        self.assertEqual(arp.analyser_table("Aucune entree ARP trouvee"), {})
        self.assertEqual(arp.analyser_table(None), {})

    def test_ligne_a_deux_mac_est_ecartee(self):
        """Une ligne ambigue vaut mieux ignoree que devinee."""
        self.assertEqual(
            arp.analyser_table("192.168.0.100 00-30-d6-4c-6e-05 00-30-d6-4c-6e-06"), {})

    def test_normalisation_des_notations(self):
        for brut in ("00-30-D6-4C-6E-05", "00:30:d6:4c:6e:05", "0030.D64C.6E05"):
            self.assertEqual(arp.normaliser(brut), "00:30:D6:4C:6E:05")

    def test_mac_de_diffusion_refusee(self):
        self.assertFalse(arp.mac_exploitable("FF:FF:FF:FF:FF:FF")[0])
        self.assertFalse(arp.mac_exploitable("00:00:00:00:00:00")[0])

    def test_mac_de_multidiffusion_refusee(self):
        """Premier octet impair : ce n'est jamais la MAC d'un appareil."""
        self.assertFalse(arp.mac_exploitable("01:00:5E:00:00:16")[0])

    def test_mac_incomplete_refusee(self):
        self.assertFalse(arp.mac_exploitable("00:30:D6")[0])

    def test_mac_normale_acceptee(self):
        self.assertTrue(arp.mac_exploitable("00:30:D6:4C:6E:05")[0])


# ==========================================================================
# numero de serie
# ==========================================================================

class TestNumero(unittest.TestCase):
    PREFIXE = "260918-0144215"

    def test_saisie_complete(self):
        self.assertEqual(numero.composer(self.PREFIXE, "00092")[0],
                         "260918-0144215-00092")

    def test_zeros_ajoutes_a_gauche(self):
        """Le gain de temps recherche : taper 92 doit suffire."""
        self.assertEqual(numero.composer(self.PREFIXE, "92")[0], "260918-0144215-00092")
        self.assertEqual(numero.composer(self.PREFIXE, "7")[0], "260918-0144215-00007")

    def test_saisie_trop_longue_refusee(self):
        complet, erreur = numero.composer(self.PREFIXE, "123456")
        self.assertIsNone(complet)
        self.assertIn("trop long", erreur)

    def test_saisie_non_numerique_refusee(self):
        complet, erreur = numero.composer(self.PREFIXE, "9a")
        self.assertIsNone(complet)
        self.assertIn("chiffres", erreur)

    def test_saisie_vide_refusee(self):
        self.assertIsNone(numero.composer(self.PREFIXE, "   ")[0])

    def test_numero_complet_colle_accepte(self):
        """Coller un numero entier ne doit pas bloquer l'operateur."""
        self.assertEqual(numero.composer(self.PREFIXE, "260918-0144215-00092")[0],
                         "260918-0144215-00092")

    def test_prefixe_sans_separateurs(self):
        self.assertEqual(numero.composer("2609180144215", "92")[0], "260918-0144215-00092")

    def test_prefixe_trop_court_refuse(self):
        complet, erreur = numero.composer("2609", "92")
        self.assertIsNone(complet)
        self.assertIn("trop court", erreur)

    def test_prefixe_vide_refuse(self):
        self.assertIsNone(numero.composer("", "92")[0])

    def test_prefixe_normalise(self):
        self.assertEqual(numero.normaliser_prefixe("260918 0144215")[0], "260918-0144215")
        self.assertEqual(numero.normaliser_prefixe("260918-0144215-00092")[0],
                         "260918-0144215")

    def test_cle_du_nom_de_fichier(self):
        cle, erreur = numero.cle_du_nom(
            "X301523-9_MF19-Ecran-Cabine-12.1_Fiche-de-Test N°260918-0144215-00092.xlsx")
        self.assertIsNone(erreur)
        self.assertEqual(cle, "260918-0144215-00092")

    def test_cle_absente(self):
        self.assertIsNone(numero.cle_du_nom("fiche.xlsx")[0])

    def test_deduction_du_prefixe(self):
        prefixe, _ = numero.deduire_prefixe(
            ["Fiche N°260918-0144215-00092.xlsx", "Fiche N°260918-0144215-00093.xlsx"])
        self.assertEqual(prefixe, "260918-0144215")

    def test_deduction_refusee_si_prefixes_differents(self):
        """Mieux vaut ne rien proposer qu'une valeur fausse."""
        prefixe, message = numero.deduire_prefixe(
            ["N°260918-0144215-00092.xlsx", "N°260919-0144215-00093.xlsx"])
        self.assertIsNone(prefixe)
        self.assertIn("plusieurs préfixes", message)

    def test_deduction_sans_numero(self):
        self.assertIsNone(numero.deduire_prefixe(["fiche.xlsx"])[0])

    def test_groupes_configurables(self):
        self.assertEqual(numero.composer("1234", "5", groupes=(4, 3))[0], "1234-005")


# ==========================================================================
# machine a etats
# ==========================================================================

A = "00:30:D6:4C:6E:05"
B = "00:30:D6:4C:6E:12"


class TestSurveillance(unittest.TestCase):
    def setUp(self):
        self.s = surveillance.Surveillance(scrutations_stables=3, scrutations_absence=2)
        self.s.demarrer()

    def _scruter(self, mac, fois=1):
        dernier = None
        for _ in range(fois):
            evenement = self.s.scruter(mac)
            if evenement:
                dernier = evenement
        return dernier

    def test_detection_apres_trois_scrutations_stables(self):
        self.assertIsNone(self._scruter(A))
        self.assertIsNone(self._scruter(A))
        self.assertEqual(self._scruter(A), (surveillance.DETECTION, A))
        self.assertEqual(self.s.etat, surveillance.DETECTE)

    def test_une_apparition_fugace_ne_declenche_rien(self):
        """Pendant le branchement la table ARP passe par des etats transitoires."""
        self._scruter(A)
        self._scruter(None)
        self._scruter(A)
        self._scruter(B)
        self.assertEqual(self.s.etat, surveillance.ATTENTE)

    def test_scenario_complet_deux_appareils(self):
        self.assertEqual(self._scruter(A, 3), (surveillance.DETECTION, A))
        self.assertTrue(self.s.enregistrer())
        self.assertEqual(self.s.etat, surveillance.ATTENTE_RETRAIT)
        self.assertEqual(self._scruter(None, 2), (surveillance.RETRAIT, None))
        self.assertEqual(self.s.etat, surveillance.ATTENTE)
        self.assertEqual(self._scruter(B, 3), (surveillance.DETECTION, B))

    def test_garde_fou_mac_identique(self):
        """Le piege central : meme IP, cache ARP pas vide, appareil pas change."""
        self._scruter(A, 3)
        self.s.enregistrer()
        self._scruter(None, 2)
        self.assertEqual(self._scruter(A, 3), (surveillance.IDENTIQUE, A))
        self.assertEqual(self.s.etat, surveillance.ATTENTE)
        self.assertIsNone(self.s.mac_courante)

    def test_mac_identique_signalee_une_seule_fois(self):
        self._scruter(A, 3)
        self.s.enregistrer()
        self._scruter(None, 2)
        self.assertEqual(self._scruter(A, 3), (surveillance.IDENTIQUE, A))
        self.assertIsNone(self._scruter(A, 5))

    def test_appareil_non_debranche_reste_bloquant(self):
        """Tant qu'on n'a pas vu l'appareil partir, on ne rearme pas."""
        self._scruter(A, 3)
        self.s.enregistrer()
        self.assertIsNone(self._scruter(A, 10))
        self.assertEqual(self.s.etat, surveillance.ATTENTE_RETRAIT)

    def test_echange_rapide_sans_absence_visible(self):
        self._scruter(A, 3)
        self.s.enregistrer()
        self.assertEqual(self._scruter(B), (surveillance.RETRAIT, None))
        self.assertEqual(self._scruter(B, 3), (surveillance.DETECTION, B))

    def test_appareil_perdu_avant_la_saisie(self):
        self._scruter(A, 3)
        self.assertEqual(self._scruter(None, 2), (surveillance.PERDU, None))
        self.assertEqual(self.s.etat, surveillance.ATTENTE)

    def test_absence_breve_ne_perd_pas_l_appareil(self):
        self._scruter(A, 3)
        self.assertIsNone(self._scruter(None))
        self.assertIsNone(self._scruter(A))
        self.assertEqual(self.s.etat, surveillance.DETECTE)

    def test_autre_mac_pendant_la_saisie(self):
        self._scruter(A, 3)
        self._scruter(B)
        self.assertEqual(self.s.etat, surveillance.ATTENTE)
        self.assertEqual(self._scruter(B, 2), (surveillance.DETECTION, B))

    def test_ignorer_ne_redetecte_pas_le_meme(self):
        self._scruter(A, 3)
        self.assertTrue(self.s.ignorer())
        self.assertEqual(self.s.etat, surveillance.ATTENTE_RETRAIT)
        self._scruter(None, 2)
        self.assertEqual(self._scruter(A, 3), (surveillance.IDENTIQUE, A))

    def test_rearmement_manuel(self):
        self._scruter(A, 3)
        self.s.enregistrer()
        self.assertTrue(self.s.rearmer())
        self.assertEqual(self.s.etat, surveillance.ATTENTE)

    def test_arret_ne_produit_plus_d_evenement(self):
        self.s.arreter()
        self.assertIsNone(self._scruter(A, 10))

    def test_enregistrer_hors_detection_refuse(self):
        self.assertFalse(self.s.enregistrer())


# ==========================================================================
# liste et CSV
# ==========================================================================

class TestReleve(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.chemin = os.path.join(self.dossier, "liste.csv")

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_aller_retour(self):
        origine = [releve.Releve("260918-0144215-00092", A, "192.168.0.100", "2026-09-11 10:14:32"),
                   releve.Releve("260918-0144215-00093", B, "192.168.0.100", "2026-09-11 10:20:01")]
        releve.enregistrer(self.chemin, origine)
        relus, message = releve.charger(self.chemin)
        self.assertEqual([(r.numero, r.mac, r.ip, r.horodatage) for r in relus],
                         [(r.numero, r.mac, r.ip, r.horodatage) for r in origine])
        self.assertIn("2 relevé", message)

    def test_fichier_absent_n_est_pas_une_erreur(self):
        relus, message = releve.charger(os.path.join(self.dossier, "rien.csv"))
        self.assertEqual(relus, [])
        self.assertEqual(message, "")

    def test_separateur_point_virgule_pour_excel(self):
        releve.enregistrer(self.chemin, [releve.Releve("260918-0144215-00092", A)])
        with open(self.chemin, encoding="utf-8-sig") as fichier:
            entete = fichier.readline()
        self.assertEqual(entete.strip(), "numero;mac;ip;horodatage")

    def test_bom_present_pour_excel_francais(self):
        releve.enregistrer(self.chemin, [releve.Releve("260918-0144215-00092", A)])
        with open(self.chemin, "rb") as fichier:
            self.assertTrue(fichier.read(3) == b"\xef\xbb\xbf")

    def test_relecture_d_un_csv_a_virgules(self):
        with open(self.chemin, "w", encoding="utf-8") as fichier:
            fichier.write("numero,mac,ip,horodatage\n260918-0144215-00092,%s,,\n" % A)
        relus, _ = releve.charger(self.chemin)
        self.assertEqual(relus[0].mac, A)

    def test_en_tete_inattendu_signale(self):
        with open(self.chemin, "w", encoding="utf-8") as fichier:
            fichier.write("a;b;c\n1;2;3\n")
        relus, message = releve.charger(self.chemin)
        self.assertEqual(relus, [])
        self.assertIn("en-tête", message)

    def test_lignes_incompletes_ignorees_et_signalees(self):
        with open(self.chemin, "w", encoding="utf-8") as fichier:
            fichier.write("numero;mac;ip;horodatage\n;%s;;\n260918-0144215-00092;%s;;\n" % (A, A))
        relus, message = releve.charger(self.chemin)
        self.assertEqual(len(relus), 1)
        self.assertIn("incomplète", message)

    def test_doublon_de_numero_signale(self):
        liste = [releve.Releve("260918-0144215-00092", A)]
        anomalies = releve.controler(liste, "260918-0144215-00092", B)
        self.assertTrue(any("déjà dans la liste" in a for a in anomalies))

    def test_mac_deja_relevee_sous_un_autre_numero(self):
        liste = [releve.Releve("260918-0144215-00092", A)]
        anomalies = releve.controler(liste, "260918-0144215-00093", A)
        self.assertTrue(any("déjà relevée" in a for a in anomalies))

    def test_aucune_anomalie_sur_un_cas_normal(self):
        liste = [releve.Releve("260918-0144215-00092", A)]
        self.assertEqual(releve.controler(liste, "260918-0144215-00093", B), [])

    def test_ecriture_ne_laisse_pas_de_fichier_temporaire(self):
        releve.enregistrer(self.chemin, [releve.Releve("260918-0144215-00092", A)])
        self.assertEqual([n for n in os.listdir(self.dossier) if n.endswith(".tmp")], [])


# ==========================================================================
# generation des .rtf
# ==========================================================================

class TestRtf(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.sortie = os.path.join(self.dossier, rtf.SOUS_DOSSIER_DEFAUT)
        self.releves = [releve.Releve("260918-0144215-00092", A, "192.168.0.100",
                                      "2026-09-11 10:14:32")]

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_nom_de_fichier_porte_le_numero(self):
        self.assertEqual(rtf.nom_fichier("260918-0144215-00092"),
                         "MAC_260918-0144215-00092.rtf")

    def test_generation_ecrit_un_fichier_par_releve(self):
        bilan = rtf.generer(self.releves, self.sortie)
        self.assertEqual(len(bilan.ecrits), 1)
        self.assertTrue(os.path.isfile(bilan.ecrits[0][1]))

    def test_horodatage_sans_deux_points(self):
        """Une heure « 10:14:32 » ne doit pas pouvoir ressembler a une MAC."""
        texte = rtf.contenu("260918-0144215-00092", A, "2026-09-11 10:14:32")
        horodatage = [l for l in texte.splitlines() if "Releve le" in l]
        self.assertEqual(len(horodatage), 1)
        self.assertIn("10h14", horodatage[0])
        self.assertNotIn(":", horodatage[0])

    def test_seule_la_ligne_mac_contient_des_deux_points(self):
        """Les deux-points restants ne sont que ceux des libelles et de la MAC."""
        texte = rtf.contenu("260918-0144215-00092", A, "2026-09-11 10:14:32")
        for ligne in texte.splitlines():
            if ":" in ligne:
                self.assertRegex(ligne, r"(Numero de serie|Adresse MAC) :")

    def test_une_seule_ligne_porte_le_libelle_mac(self):
        texte = rtf.contenu("260918-0144215-00092", A, "2026-09-11 10:14:32")
        etiquetees = [l for l in texte.splitlines() if re.search(r"\bMAC\b", l, re.I)]
        self.assertEqual(len(etiquetees), 1)

    def test_conflit_avec_un_word_existant(self):
        """ExtractionMAC rejetterait le couple : mieux vaut refuser tout de suite."""
        with open(os.path.join(self.dossier, "X130392_B_260918-0144215-00092.doc"), "wb") as f:
            f.write(b"\xd0\xcf\x11\xe0")
        existants = rtf.fichiers_word_existants(self.dossier, dossier_exclu=self.sortie)
        bilan = rtf.generer(self.releves, self.sortie, existants)
        self.assertEqual(bilan.ecrits, [])
        self.assertEqual(len(bilan.conflits), 1)

    def test_regeneration_ne_se_prend_pas_pour_un_conflit(self):
        """Les .rtf de la fois precedente doivent pouvoir etre ecrases."""
        rtf.generer(self.releves, self.sortie)
        existants = rtf.fichiers_word_existants(self.dossier, dossier_exclu=self.sortie)
        bilan = rtf.generer(self.releves, self.sortie, existants)
        self.assertEqual(len(bilan.ecrits), 1)
        self.assertEqual(bilan.conflits, [])

    def test_fiches_excel_reperees(self):
        for nom in ("Fiche N°260918-0144215-00092.xlsx", "Fiche N°260918-0144215-00093.xlsm"):
            open(os.path.join(self.dossier, nom), "wb").close()
        fiches = rtf.numeros_des_fiches(self.dossier)
        self.assertEqual(set(fiches), {"260918-0144215-00092", "260918-0144215-00093"})

    def test_fichiers_temporaires_excel_ignores(self):
        open(os.path.join(self.dossier, "~$Fiche N°260918-0144215-00092.xlsx"), "wb").close()
        self.assertEqual(rtf.numeros_des_fiches(self.dossier), {})

    def test_echappement_rtf(self):
        self.assertEqual(rtf._echapper("a{b}c\\d"), "a\\{b\\}c\\\\d")
        self.assertEqual(rtf._echapper("é"), "\\'e9")


# ==========================================================================
# contrat avec ExtractionMAC — le test qui garantit que la chaine tient
# ==========================================================================

class TestContratExtractionMac(unittest.TestCase):
    """Le .rtf produit ici doit etre lu sans ambiguite par ExtractionMAC.

    Les expressions regulieres ci-dessous sont **recopiees telles quelles** de
    ``extraction_mac/docmac.py`` et ``extraction_mac/serial.py``. Si elles
    changent la-bas, ces tests doivent etre mis a jour — et c'est precisement le
    but : une divergence entre les deux logiciels doit se voir ici, pas en
    production sur une fiche de test mal remplie.
    """

    # --- copie de extraction_mac/docmac.py ---
    MAC_SEPARE = re.compile(
        r"(?<![0-9A-Za-z])([0-9A-Fa-f]{2})([:\-])"
        r"(?:[0-9A-Fa-f]{2}\2){4}[0-9A-Fa-f]{2}(?![0-9A-Za-z])")
    MAC_POINTS = re.compile(
        r"(?<![0-9A-Za-z])[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}(?![0-9A-Za-z])")
    MAC_BRUT = re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{12}(?![0-9A-Za-z])")
    LIBELLE_MAC = re.compile(r"\bMAC\b", re.IGNORECASE)

    # --- copie de extraction_mac/serial.py ---
    CLE = re.compile(r"(?<![0-9])([0-9]{6})[^0-9A-Za-z]?([0-9]{7})[^0-9A-Za-z]?([0-9]{5})(?![0-9])")

    CAS = [
        ("260918-0144215-00092", "00:30:D6:4C:6E:05"),
        ("260918-0144215-00007", "0A:1B:2C:3D:4E:5F"),
        ("123456-7654321-99999", "AC:DE:48:00:11:22"),
        ("000001-0000001-00001", "FE:DC:BA:98:76:54"),
    ]

    def _candidats(self, ligne, autoriser_brut):
        trouves = []
        for regex in (self.MAC_SEPARE, self.MAC_POINTS):
            for m in regex.finditer(ligne):
                valeur = re.sub(r"[^0-9A-Fa-f]", "", m.group(0)).upper()
                if valeur not in trouves:
                    trouves.append(valeur)
        if not trouves and autoriser_brut:
            for m in self.MAC_BRUT.finditer(ligne):
                if m.group(0).upper() not in trouves:
                    trouves.append(m.group(0).upper())
        return trouves

    def _chercher_mac(self, texte):
        """Reproduit docmac.chercher_mac : priorite aux lignes libellees « MAC »."""
        lignes = [l for l in texte.splitlines() if l.strip()]
        retenus = []
        for ligne in lignes:
            if self.LIBELLE_MAC.search(ligne):
                for v in self._candidats(ligne, True):
                    if v not in retenus:
                        retenus.append(v)
        if not retenus:
            for ligne in lignes:
                for v in self._candidats(ligne, False):
                    if v not in retenus:
                        retenus.append(v)
        return retenus

    def _texte_lu_comme_extraction_mac(self, chemin):
        """Reproduit docmac.lire_texte pour un fichier ni .docx ni .doc binaire."""
        with open(chemin, "rb") as fichier:
            donnees = fichier.read()
        self.assertFalse(donnees.startswith(b"PK\x03\x04"), "ne doit pas etre vu comme un .docx")
        self.assertFalse(donnees.startswith(b"\xd0\xcf\x11\xe0"), "ne doit pas etre vu comme un .doc")
        texte = donnees.decode("cp1252", "replace")
        return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]+", "\n", texte).replace("\r", "\n")

    def setUp(self):
        self.dossier = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_extension_rtf_acceptee_par_extraction_mac(self):
        self.assertIn(rtf.EXTENSION, rtf.EXTENSIONS_WORD)

    def test_une_seule_mac_trouvee_dans_chaque_fichier(self):
        """Le point critique : deux MAC dans le document et ExtractionMAC refuse le fichier."""
        releves = [releve.Releve(n, m, "192.168.0.100", "2026-09-11 10:14:32")
                   for n, m in self.CAS]
        bilan = rtf.generer(releves, self.dossier)
        self.assertEqual(len(bilan.ecrits), len(self.CAS))
        for (numero_attendu, mac_attendue), (_, chemin) in zip(self.CAS, bilan.ecrits):
            texte = self._texte_lu_comme_extraction_mac(chemin)
            trouvees = self._chercher_mac(texte)
            self.assertEqual(len(trouvees), 1,
                             "%s : %d MAC trouvées %s" % (os.path.basename(chemin),
                                                          len(trouvees), trouvees))
            self.assertEqual(trouvees[0], mac_attendue.replace(":", ""))

    def test_le_numero_de_serie_n_est_jamais_pris_pour_une_mac(self):
        for numero_serie, _ in self.CAS:
            ligne = "Numero de serie : %s" % numero_serie
            self.assertEqual(self._candidats(ligne, autoriser_brut=True), [],
                             "%s confondu avec une MAC" % numero_serie)

    def test_une_seule_cle_dans_le_nom_de_fichier(self):
        for numero_serie, _ in self.CAS:
            nom = rtf.nom_fichier(numero_serie)
            tronc = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", nom)
            cles = {"-".join(m.groups()) for m in self.CLE.finditer(tronc)}
            self.assertEqual(cles, {numero_serie})

    def test_notre_lecture_du_numero_est_celle_d_extraction_mac(self):
        """numero.py et serial.py doivent trouver exactement la meme cle."""
        noms = [
            "X130392_B_260918-0144215-00092.doc",
            "X301523-9_MF19-Ecran-Cabine-12.1_Fiche-de-Test N°260918-0144215-00092.xlsx",
            "MAC_260918-0144215-00092.rtf",
            "260918014421500092.xlsx",
            "260918_0144215_00092.xlsx",
        ]
        for nom in noms:
            tronc = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", nom)
            attendu = ["-".join(m.groups()) for m in self.CLE.finditer(tronc)]
            self.assertEqual(numero.cles(tronc), attendu, nom)


# ==========================================================================
# configuration et simulateur
# ==========================================================================

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self._vrai_dossier = config.dossier_config
        self._vrais_chemins = config.chemins_lecture
        config.dossier_config = lambda: self.dossier
        config.chemins_lecture = lambda: [os.path.join(self.dossier, config.NOM_FICHIER)]

    def tearDown(self):
        config.dossier_config = self._vrai_dossier
        config.chemins_lecture = self._vrais_chemins
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_aller_retour(self):
        profil = config.profil_vide()
        profil["ip_surveillee"] = "10.0.0.5"
        profil["prefixe_numero"] = "260918-0144215"
        config.enregistrer({"banc 1": profil}, "banc 1")
        profils, dernier = config.charger()
        self.assertEqual(dernier, "banc 1")
        self.assertEqual(profils["banc 1"]["ip_surveillee"], "10.0.0.5")

    def test_config_absente_donne_une_config_vide(self):
        self.assertEqual(config.charger(), ({}, ""))

    def test_fichier_illisible_ne_leve_pas(self):
        with open(os.path.join(self.dossier, config.NOM_FICHIER), "w") as fichier:
            fichier.write("{ceci n'est pas du json")
        self.assertEqual(config.charger(), ({}, ""))

    def test_valeurs_hors_bornes_ramenees(self):
        profil = config.normaliser_profil({"intervalle_ms": 99999})
        self.assertEqual(profil["intervalle_ms"], config.BORNES["intervalle_ms"][1])
        profil = config.normaliser_profil({"scrutations_stables": 0})
        self.assertEqual(profil["scrutations_stables"], 1)

    def test_cle_inconnue_ignoree(self):
        self.assertNotIn("inconnu", config.normaliser_profil({"inconnu": 1}))

    def test_groupes_invalides_ignores(self):
        self.assertEqual(config.normaliser_profil({"groupes_numero": ["a"]})["groupes_numero"],
                         config.PROFIL_DEFAUT["groupes_numero"])


class TestSimulateur(unittest.TestCase):
    def test_l_appareil_reste_branche_jusqu_a_l_enregistrement(self):
        """Un operateur lent ne doit pas voir l'appareil disparaitre en pleine saisie."""
        faux = simulateur.SimulateurArp(["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB"])
        for _ in range(20):
            self.assertEqual(faux.lire("192.168.0.100"), "AA:AA:AA:AA:AA:AA")

    def test_sequence_complete(self):
        faux = simulateur.SimulateurArp(["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB"],
                                        scrutations_vides=2)
        self.assertEqual(faux.lire(), "AA:AA:AA:AA:AA:AA")
        faux.suivant()
        self.assertIsNone(faux.lire())
        self.assertIsNone(faux.lire())
        self.assertEqual(faux.lire(), "BB:BB:BB:BB:BB:BB")
        faux.suivant()
        self.assertTrue(faux.termine)

    def test_deroule_avec_la_machine_a_etats(self):
        """Repetition a blanc de bout en bout, sans appareil ni reseau."""
        faux = simulateur.SimulateurArp(["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB"],
                                        scrutations_vides=2)
        machine = surveillance.Surveillance(3, 2)
        machine.demarrer()
        detectees = []
        for _ in range(40):
            evenement = machine.scruter(faux.lire())
            if evenement and evenement[0] == surveillance.DETECTION:
                detectees.append(evenement[1])
                machine.enregistrer()
                faux.suivant()
        self.assertEqual(detectees, ["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB"])


if __name__ == "__main__":
    unittest.main()


class TestVidageCacheArp(unittest.TestCase):
    """Le vidage ne doit pas crier au manque de droits quand il n'y a rien a vider."""

    def setUp(self):
        self.vraie_table = arp.table

    def tearDown(self):
        arp.table = self.vraie_table

    def test_entree_absente_n_est_pas_un_echec(self):
        arp.table = lambda: {}
        succes, message = arp.vider("192.168.0.100")
        self.assertTrue(succes)
        self.assertIn("aucune entrée", message)

    def test_entree_presente_declenche_la_commande(self):
        arp.table = lambda: {"192.168.0.100": A}
        appels = []
        vrai_executer = arp._executer
        arp._executer = lambda arguments, delai=3: (appels.append(arguments), (1, "refusé"))[1]
        try:
            succes, message = arp.vider("192.168.0.100")
        finally:
            arp._executer = vrai_executer
        self.assertEqual(appels, [["arp", "-d", "192.168.0.100"]])
        self.assertFalse(succes)
        self.assertIn("administrateur", message)
