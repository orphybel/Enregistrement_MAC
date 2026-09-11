"""Numero de serie de l'appareil : ``xxxxxx-yyyyyyy-zzzzz``.

L'operateur ne saisit que le **dernier groupe** (5 chiffres) : le debut du
numero, identique pour tout un lot, est regle une fois pour toutes dans le
champ « Prefixe ». Taper ``92`` suffit donc a designer
``260918-0144215-00092``.

Les regles d'ecriture du numero sont **exactement celles de
``extraction_mac/serial.py``** : meme motif, memes garde-fous, meme forme
canonique a tirets. C'est ce qui garantit que le fichier produit ici sera
apparie avec la bonne fiche Excel par ExtractionMAC. Toute modification ici
doit etre repercutee la-bas, et le test ``test_contrat_extraction_mac`` est la
pour s'en apercevoir.
"""

from __future__ import annotations

import re

GROUPES_DEFAUT = (6, 7, 5)


def _motif(groupes):
    """Groupes de chiffres separes par au plus un caractere non alphanumerique.

    Les garde-fous ``(?<![0-9])`` / ``(?![0-9])`` empechent de tomber au milieu
    d'une suite de chiffres plus longue et d'en extraire une cle fantaisiste.
    """
    corps = "[^0-9A-Za-z]?".join("([0-9]{%d})" % n for n in groupes)
    return re.compile("(?<![0-9])" + corps + "(?![0-9])")


def cles(texte, groupes=GROUPES_DEFAUT):
    """Retourne les numeros distincts trouves dans *texte*, dans l'ordre."""
    trouves = []
    for correspondance in _motif(tuple(groupes)).finditer(texte or ""):
        cle = "-".join(correspondance.groups())
        if cle not in trouves:
            trouves.append(cle)
    return trouves


def cle_du_nom(nom, groupes=GROUPES_DEFAUT):
    """Retourne (numero, erreur) pour un nom de fichier. Numero None si absent ou ambigu."""
    tronc = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", nom)
    trouves = cles(tronc, groupes)
    if not trouves:
        attendu = "-".join("x" * n for n in groupes)
        return None, "aucun numéro de série (%s) dans le nom du fichier" % attendu
    if len(trouves) > 1:
        return None, "plusieurs numéros de série dans le nom du fichier : %s" % ", ".join(trouves)
    return trouves[0], None


def forme_attendue(groupes=GROUPES_DEFAUT):
    return "-".join("x" * n for n in groupes)


def normaliser_prefixe(prefixe, groupes=GROUPES_DEFAUT):
    """Retourne (prefixe_canonique, erreur).

    Accepte ``260918-0144215``, ``260918 0144215``, ``2609180144215`` ou meme un
    numero complet colle depuis un nom de fichier, dont seuls les premiers
    groupes sont retenus.
    """
    groupes = tuple(groupes)
    if len(groupes) < 2:
        return None, "le numéro doit comporter au moins deux groupes"
    tete = groupes[:-1]
    chiffres = re.sub(r"[^0-9]", "", prefixe or "")
    if not chiffres:
        return None, "préfixe vide ; attendu %s" % "-".join("x" * n for n in tete)
    attendu = sum(tete)
    if len(chiffres) < attendu:
        return None, ("préfixe trop court : %d chiffres au lieu de %d (attendu %s)"
                      % (len(chiffres), attendu, "-".join("x" * n for n in tete)))
    # Un numero complet colle par megarde : on ne garde que la tete.
    chiffres = chiffres[:attendu]
    morceaux, position = [], 0
    for longueur in tete:
        morceaux.append(chiffres[position:position + longueur])
        position += longueur
    return "-".join(morceaux), None


def composer(prefixe, saisie, groupes=GROUPES_DEFAUT):
    """Retourne (numero_complet, erreur) a partir du prefixe et du dernier groupe.

    La saisie est completee a gauche par des zeros : ``92`` devient ``00092``.
    Un numero complet colle dans le champ est accepte tel quel, ce qui evite de
    bloquer l'operateur quand il recopie depuis un nom de fichier.
    """
    groupes = tuple(groupes)
    brut = (saisie or "").strip()
    if not brut:
        return None, "numéro d'appareil vide"

    # cas du numero complet colle : on le prend sans discuter
    complets = cles(brut, groupes)
    if len(complets) == 1 and len(re.sub(r"[^0-9]", "", brut)) == sum(groupes):
        return complets[0], None

    if re.search(r"[^0-9\s]", brut):
        return None, "le numéro d'appareil ne doit contenir que des chiffres"
    chiffres = re.sub(r"\s", "", brut)
    dernier = groupes[-1]
    if len(chiffres) > dernier:
        return None, ("numéro trop long : %d chiffres pour un groupe final de %d"
                      % (len(chiffres), dernier))

    tete, erreur = normaliser_prefixe(prefixe, groupes)
    if erreur:
        return None, erreur
    return "%s-%s" % (tete, chiffres.zfill(dernier)), None


def partie_finale(numero, groupes=GROUPES_DEFAUT):
    """Dernier groupe d'un numero complet, pour l'affichage."""
    return (numero or "").rsplit("-", 1)[-1]


def deduire_prefixe(noms, groupes=GROUPES_DEFAUT):
    """Retourne (prefixe, message) deduit d'une liste de noms de fichiers.

    Sert a pre-remplir le champ « Prefixe » a partir des fiches Excel presentes
    dans le dossier : l'operateur n'a alors plus rien a regler. La deduction
    n'aboutit que si **tous** les numeros trouves partagent la meme tete ; sinon
    on prefere ne rien proposer plutot que de proposer une valeur fausse.
    """
    groupes = tuple(groupes)
    tetes, exemples = [], []
    for nom in noms:
        numero, _ = cle_du_nom(nom, groupes)
        if not numero:
            continue
        tete = numero.rsplit("-", 1)[0]
        if tete not in tetes:
            tetes.append(tete)
        exemples.append(numero)
    if not tetes:
        return None, "aucun numéro de série reconnu dans les noms de fichiers"
    if len(tetes) > 1:
        return None, ("plusieurs préfixes différents dans le dossier : %s"
                      % ", ".join(tetes[:4]))
    return tetes[0], "préfixe déduit de %d fichier(s) : %s" % (len(exemples), tetes[0])


def numeros_des_fiches(noms, groupes=GROUPES_DEFAUT):
    """Numeros portes par une liste de noms de fichiers, pour controler une saisie."""
    trouves = set()
    for nom in noms:
        numero, _ = cle_du_nom(nom, groupes)
        if numero:
            trouves.add(numero)
    return trouves
