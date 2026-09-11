"""Verification de bout en bout contre le VRAI code d'ExtractionMAC.

Les tests unitaires recopient les expressions regulieres d'ExtractionMAC ; ce
script-ci, lui, importe reellement ses modules et deroule la chaine complete :

    relevé  ->  .rtf  ->  ExtractionMAC  ->  cellule de la fiche Excel

Il verifie donc ce qui compte vraiment : que l'adresse MAC relevee au banc
finit bien dans la bonne cellule du bon classeur.

Usage :

    git clone https://github.com/orphybel/Extraction_Mac.git ../Extraction_Mac
    python tests/verifier_chaine.py ../Extraction_Mac

Sortie : code 0 si la chaine tient, 1 sinon.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from enregistrement_mac import releve, rtf                      # noqa: E402

CAS = [
    ("260918-0144215-00092", "00:30:D6:4C:6E:05"),
    ("260918-0144215-00093", "0A:1B:2C:3D:4E:5F"),
    ("260918-0144215-00094", "AC:DE:48:00:11:22"),
]
FEUILLE, CELLULE = "Constit produit", "F27"


def _charger_fixtures(racine_extraction):
    chemin = os.path.join(racine_extraction, "tests", "fixtures.py")
    specification = importlib.util.spec_from_file_location("fixtures_extraction", chemin)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def verifier(racine_extraction):
    if not os.path.isdir(os.path.join(racine_extraction, "extraction_mac")):
        print("Dossier ExtractionMAC introuvable : %s" % racine_extraction)
        return 1
    sys.path.insert(0, os.path.abspath(racine_extraction))
    from extraction_mac import runner, xlsxcell

    fixtures = _charger_fixtures(racine_extraction)
    base = tempfile.mkdtemp(prefix="chaine-mac-")
    try:
        # 1. les fiches de test, comme sur le poste de production
        for numero_serie, _ in CAS:
            fixtures.ecrire_xlsx(os.path.join(
                base, "X301523-9_MF19_Fiche-de-Test N%s.xlsx" % numero_serie))

        # 2. ce que produit Enregistrement MAC
        sortie = os.path.join(base, rtf.SOUS_DOSSIER_DEFAUT)
        releves = [releve.Releve(n, m, "192.168.0.100", "2026-09-11 10:14:32")
                   for n, m in CAS]
        bilan = rtf.generer(releves, sortie,
                            rtf.fichiers_word_existants(base, dossier_exclu=sortie))
        print("1) génération des .rtf      : %s" % bilan.resume())
        if bilan.conflits or bilan.erreurs:
            print("   anomalies : %s" % (bilan.conflits + bilan.erreurs))
            return 1

        # 3. ExtractionMAC, sous-dossiers inclus
        options = runner.Options(dossier=base, feuille=FEUILLE, cellule=CELLULE,
                                 sous_dossiers=True, simulation=True)
        analyse = runner.executer(options)
        print("2) analyse ExtractionMAC    : %s" % analyse.resume())
        options.simulation = False
        ecriture = runner.executer(options)
        print("3) écriture ExtractionMAC   : %s" % ecriture.resume())

        # 4. la preuve : relire les cellules
        print("4) relecture des cellules :")
        bon = True
        for numero_serie, mac in CAS:
            chemin = os.path.join(base, "X301523-9_MF19_Fiche-de-Test N%s.xlsx" % numero_serie)
            valeur = xlsxcell.lire_cellule(chemin, FEUILLE, CELLULE)
            conforme = valeur == mac
            bon = bon and conforme
            print("   %s %s  %s = %r" % ("OK  " if conforme else "ÉCHEC",
                                         numero_serie, CELLULE, valeur))

        # 5. le garde-fou : un Word du fabricant portant deja le meme numero
        with open(os.path.join(base, "X130392_B_%s.doc" % CAS[0][0]), "wb") as fichier:
            fichier.write(b"\xd0\xcf\x11\xe0")
        conflit = rtf.generer(releves, sortie,
                              rtf.fichiers_word_existants(base, dossier_exclu=sortie))
        attendu = len(conflit.conflits) == 1
        print("5) garde-fou conflit Word   : %s (%s)"
              % ("OK" if attendu else "ÉCHEC", conflit.resume()))

        reussi = bon and attendu and not analyse.compter(runner.ERREUR)
        print()
        print("CHAÎNE COMPLÈTE VALIDÉE" if reussi else "*** CHAÎNE ROMPUE ***")
        return 0 if reussi else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(verifier(sys.argv[1]))
