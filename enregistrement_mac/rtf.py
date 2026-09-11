"""Generation des fichiers repris par ExtractionMAC.

ExtractionMAC apparie un fichier Word et un ``.xlsx`` par le numero de serie lu
**dans le nom du fichier**, puis va chercher l'adresse MAC **dans le texte** du
Word. Son ``runner.EXTENSIONS_WORD`` accepte deja ``.rtf``, et son
``docmac.lire_texte`` decode en cp1252 tout fichier qui n'est ni un ``.docx`` ni
un ``.doc`` binaire.

On produit donc, par appareil, un minuscule ``.rtf`` :

    MAC_260918-0144215-00092.rtf
    ---------------------------------------------
    Releve automatique d'adresse physique
    Numero de serie : 260918-0144215-00092
    Adresse MAC : 00:30:D6:4C:6E:05
    Releve le 2026-09-11 a 10h14

Aucune modification d'ExtractionMAC n'est necessaire.

Trois details qui ne sont pas des details :

* **Une seule ligne porte le libelle « MAC ».** ``docmac.chercher_mac`` donne la
  priorite absolue a ces lignes et refuse le document s'il y trouve deux
  adresses differentes. D'ou le titre « adresse physique » et l'horodatage ecrit
  ``10h14`` et non ``10:14``.
* **Le numero de serie ne peut pas etre pris pour une MAC** : ses groupes font
  6, 7 et 5 chiffres, alors que ``docmac`` exige 12 caracteres hexadecimaux
  isoles, ou six paires separees.
* **Corps en ASCII pur**, sans accent : le fichier traverse un decodage cp1252
  et des echappements RTF ; autant ne rien donner a mal interpreter.

Enfin, si un vrai Word du fabricant porte deja le meme numero,
``runner.appairer`` rejetterait le couple (« 2 fichiers Word portent ce
numero »). La generation refuse donc d'ecrire dans ce cas, plutot que de
fabriquer une panne a retardement.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import numero as mod_numero

PREFIXE_FICHIER = "MAC_"
EXTENSION = ".rtf"
SOUS_DOSSIER_DEFAUT = "MAC-releves"

# identique a extraction_mac/runner.py : ce qu'ExtractionMAC considere comme un Word
EXTENSIONS_WORD = (".doc", ".docx", ".docm", ".rtf")
EXTENSIONS_EXCEL = (".xlsx", ".xlsm")

_ENTETE = r"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fswiss Arial;}}\viewkind4\uc1"


def _echapper(texte):
    """Protege les caracteres de syntaxe RTF et tout ce qui sort de l'ASCII."""
    sortie = []
    for caractere in texte or "":
        if caractere in "\\{}":
            sortie.append("\\" + caractere)
        elif ord(caractere) < 128:
            sortie.append(caractere)
        else:
            sortie.append("\\'%02x" % (ord(caractere) & 0xFF))
    return "".join(sortie)


def nom_fichier(numero):
    return "%s%s%s" % (PREFIXE_FICHIER, numero, EXTENSION)


def contenu(numero, mac, horodatage=""):
    """Texte RTF complet pour un appareil.

    Les vraies fins de ligne (CRLF) sont volontaires en plus des ``\\par`` :
    ExtractionMAC lit ce fichier comme du texte brut et raisonne ligne par
    ligne, alors qu'un lecteur RTF ignore les CRLF. Les deux lectures donnent
    ainsi le meme resultat.
    """
    # « 10:14:32 » devient « 10h14 » : aucun deux-points dans le corps, donc
    # aucune chance qu'une heure ressemble de loin a une adresse MAC.
    horodatage = re.sub(r"(\d{1,2}):(\d{2})(?::\d{2})?", r"\1h\2", horodatage or "")
    lignes = [
        _ENTETE,
        r"\pard\f0\fs22 Releve automatique d'adresse physique\par",
        r"Numero de serie : %s\par" % _echapper(numero),
        r"Adresse MAC : %s\par" % _echapper(mac),
    ]
    if horodatage:
        lignes.append(r"Releve le %s\par" % _echapper(horodatage))
    lignes.append("}")
    return "\r\n".join(lignes) + "\r\n"


def fichiers_word_existants(racine, groupes=mod_numero.GROUPES_DEFAUT, dossier_exclu=None):
    """{numero: chemin} des Word deja presents sous *racine*, hors *dossier_exclu*.

    Le dossier de sortie est exclu : regenerer la liste doit pouvoir ecraser les
    fichiers de la fois precedente sans les prendre pour des conflits.
    """
    trouves = {}
    if not racine or not os.path.isdir(racine):
        return trouves
    exclu = os.path.abspath(dossier_exclu) if dossier_exclu else None
    for dossier, _, noms in os.walk(racine):
        if exclu and os.path.abspath(dossier) == exclu:
            continue
        for nom in noms:
            if nom.startswith("~$") or nom.startswith("."):
                continue
            if os.path.splitext(nom)[1].lower() not in EXTENSIONS_WORD:
                continue
            cle, _ = mod_numero.cle_du_nom(nom, groupes)
            if cle:
                trouves.setdefault(cle, os.path.join(dossier, nom))
    return trouves


def numeros_des_fiches(racine, groupes=mod_numero.GROUPES_DEFAUT):
    """{numero: chemin} des fiches Excel presentes sous *racine*."""
    trouves = {}
    if not racine or not os.path.isdir(racine):
        return trouves
    for dossier, _, noms in os.walk(racine):
        for nom in noms:
            if nom.startswith("~$") or nom.startswith("."):
                continue
            if os.path.splitext(nom)[1].lower() not in EXTENSIONS_EXCEL:
                continue
            cle, _ = mod_numero.cle_du_nom(nom, groupes)
            if cle:
                trouves.setdefault(cle, os.path.join(dossier, nom))
    return trouves


@dataclass
class Bilan:
    ecrits: list = field(default_factory=list)      # (numero, chemin)
    conflits: list = field(default_factory=list)    # (numero, message)
    erreurs: list = field(default_factory=list)     # (numero, message)

    def resume(self):
        parties = ["%d fichier(s) écrit(s)" % len(self.ecrits)]
        if self.conflits:
            parties.append("%d conflit(s)" % len(self.conflits))
        if self.erreurs:
            parties.append("%d erreur(s)" % len(self.erreurs))
        return ", ".join(parties)


def generer(releves, dossier_sortie, word_existants=None):
    """Ecrit un .rtf par releve. Retourne un Bilan.

    *word_existants* est le ``{numero: chemin}`` rendu par
    ``fichiers_word_existants`` sur le dossier des fiches : tout numero qui s'y
    trouve deja est refuse, car ExtractionMAC rejetterait le couple.
    """
    word_existants = word_existants or {}
    bilan = Bilan()
    try:
        os.makedirs(dossier_sortie, exist_ok=True)
    except OSError as erreur:
        bilan.erreurs.append(("", "dossier de sortie inaccessible : %s" % erreur))
        return bilan

    for releve in releves:
        conflit = word_existants.get(releve.numero)
        if conflit:
            bilan.conflits.append((
                releve.numero,
                "un fichier Word porte déjà ce numéro (%s) ; ExtractionMAC "
                "refuserait le couple" % os.path.basename(conflit)))
            continue
        chemin = os.path.join(dossier_sortie, nom_fichier(releve.numero))
        try:
            with open(chemin, "w", encoding="cp1252", errors="replace", newline="") as fichier:
                fichier.write(contenu(releve.numero, releve.mac, releve.horodatage))
        except OSError as erreur:
            bilan.erreurs.append((releve.numero, "écriture impossible : %s" % erreur))
            continue
        bilan.ecrits.append((releve.numero, chemin))
    return bilan
