"""Fenetre Tkinter : surveiller l'IP, saisir le numero, constituer la liste.

Le geste de l'operateur doit tenir en une touche : l'appareil est detecte, le
curseur est deja dans le champ du numero, il tape les derniers chiffres et
appuie sur Entree. Tout le reste — le prefixe, le dossier, le fichier — est
regle une fois pour toutes dans un profil.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__, arp, config, numero as mod_numero, releve, rtf, surveillance
from .simulateur import SimulateurArp

NOM_DIAGNOSTIC = "EnregistrementMAC-diagnostic.txt"

COULEUR_ATTENTE = "#5c5c5c"
COULEUR_DETECTE = "#0a7a28"
COULEUR_ALERTE = "#c01c28"
COULEUR_INFO = "#1a5fb4"


class Application(ttk.Frame):
    def __init__(self, racine, source=None):
        super().__init__(racine, padding=12)
        self.racine = racine
        self.grid(row=0, column=0, sticky="nsew")
        racine.columnconfigure(0, weight=1)
        racine.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(8, weight=1)

        self.source = source                     # None = vraie table ARP
        self.profils, dernier = config.charger()
        self.releves = []
        self.mac_a_enregistrer = None
        self.origine_manuelle = False
        self.boucle = None
        self.surveillance = surveillance.Surveillance()

        self.var_profil = tk.StringVar()
        self.var_ip = tk.StringVar()
        self.var_prefixe = tk.StringVar()
        self.var_dossier = tk.StringVar()
        self.var_csv = tk.StringVar()
        self.var_vider = tk.BooleanVar(value=True)
        self.var_numero = tk.StringVar()
        self.var_mac = tk.StringVar(value="—")
        self.var_apercu = tk.StringVar(value="")
        self.var_etat_banc = tk.StringVar(value=surveillance.LIBELLES[surveillance.ARRET])
        self.var_etat = tk.StringVar(value="Prêt.")

        self._construire()
        self._appliquer_profil(self.profils.get(dernier, config.profil_vide()))
        self.var_profil.set(dernier)
        self._rafraichir_profils()
        self.var_numero.trace_add("write", lambda *_: self._rafraichir_apercu())

        if self.source is not None:
            self._dire("Mode simulation : aucun appareil réel n'est lu. "
                       "Configuration : %s" % config.chemin_config())
        else:
            self._dire("Configuration : %s" % config.chemin_config())
        self._charger_liste()
        self.racine.protocol("WM_DELETE_WINDOW", self._fermer)

    # ------------------------------------------------------------------ vue
    def _construire(self):
        ligne = 0

        # --- profil ---------------------------------------------------------
        ttk.Label(self, text="Profil").grid(row=ligne, column=0, sticky="w", pady=3)
        cadre = ttk.Frame(self)
        cadre.grid(row=ligne, column=1, sticky="ew", pady=3, padx=(8, 0))
        cadre.columnconfigure(0, weight=1)
        self.liste_profils = ttk.Combobox(cadre, textvariable=self.var_profil)
        self.liste_profils.grid(row=0, column=0, sticky="ew")
        self.liste_profils.bind("<<ComboboxSelected>>", self._changer_profil)
        ttk.Button(cadre, text="Enregistrer", command=self._enregistrer_profil,
                   width=12).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(cadre, text="Supprimer", command=self._supprimer_profil,
                   width=10).grid(row=0, column=2, padx=(6, 0))
        ligne += 1

        ttk.Separator(self, orient="horizontal").grid(
            row=ligne, column=0, columnspan=2, sticky="ew", pady=8)
        ligne += 1

        # --- reglages -------------------------------------------------------
        ttk.Label(self, text="Adresse IP surveillée").grid(row=ligne, column=0, sticky="w", pady=3)
        cadre = ttk.Frame(self)
        cadre.grid(row=ligne, column=1, sticky="ew", pady=3, padx=(8, 0))
        cadre.columnconfigure(0, weight=1)
        ttk.Entry(cadre, textvariable=self.var_ip).grid(row=0, column=0, sticky="ew")
        ttk.Button(cadre, text="Tester", command=self._tester_ip,
                   width=12).grid(row=0, column=1, padx=(6, 0))
        ligne += 1

        ttk.Label(self, text="Préfixe du numéro").grid(row=ligne, column=0, sticky="w", pady=3)
        cadre = ttk.Frame(self)
        cadre.grid(row=ligne, column=1, sticky="ew", pady=3, padx=(8, 0))
        cadre.columnconfigure(0, weight=1)
        ttk.Entry(cadre, textvariable=self.var_prefixe).grid(row=0, column=0, sticky="ew")
        ttk.Button(cadre, text="Déduire du dossier", command=self._deduire_prefixe,
                   width=20).grid(row=0, column=1, padx=(6, 0))
        ligne += 1

        ttk.Label(self, text="Dossier des fiches Excel").grid(row=ligne, column=0, sticky="w", pady=3)
        cadre = ttk.Frame(self)
        cadre.grid(row=ligne, column=1, sticky="ew", pady=3, padx=(8, 0))
        cadre.columnconfigure(0, weight=1)
        ttk.Entry(cadre, textvariable=self.var_dossier).grid(row=0, column=0, sticky="ew")
        ttk.Button(cadre, text="Parcourir…", command=self._choisir_dossier,
                   width=12).grid(row=0, column=1, padx=(6, 0))
        ligne += 1

        ttk.Label(self, text="Fichier liste (CSV)").grid(row=ligne, column=0, sticky="w", pady=3)
        cadre = ttk.Frame(self)
        cadre.grid(row=ligne, column=1, sticky="ew", pady=3, padx=(8, 0))
        cadre.columnconfigure(0, weight=1)
        ttk.Entry(cadre, textvariable=self.var_csv).grid(row=0, column=0, sticky="ew")
        ttk.Button(cadre, text="Parcourir…", command=self._choisir_csv,
                   width=12).grid(row=0, column=1, padx=(6, 0))
        ligne += 1

        ttk.Checkbutton(self, text="Vider le cache ARP entre deux appareils "
                                   "(demande les droits administrateur)",
                        variable=self.var_vider).grid(row=ligne, column=1, sticky="w",
                                                      padx=(8, 0), pady=(2, 6))
        ligne += 1

        # --- banc -----------------------------------------------------------
        banc = ttk.LabelFrame(self, text="Banc de test", padding=10)
        banc.grid(row=ligne, column=0, columnspan=2, sticky="ew", pady=4)
        banc.columnconfigure(1, weight=1)

        commandes = ttk.Frame(banc)
        commandes.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.bouton_marche = ttk.Button(commandes, text="Démarrer la surveillance",
                                        command=self._basculer_surveillance, width=26)
        self.bouton_marche.grid(row=0, column=0)
        ttk.Button(commandes, text="Vider le cache ARP", command=self._vider_cache,
                   width=20).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(commandes, text="Saisir la MAC à la main", command=self._saisie_manuelle,
                   width=24).grid(row=0, column=2, padx=(8, 0))
        self.bouton_admin = ttk.Button(commandes, text="Relancer en administrateur",
                                       command=self._relancer_admin, width=26)
        # affiche seulement si un vidage a echoue

        self.etiquette_etat_banc = ttk.Label(banc, textvariable=self.var_etat_banc,
                                             foreground=COULEUR_ATTENTE)
        self.etiquette_etat_banc.grid(row=1, column=0, columnspan=3, sticky="w")

        self.etiquette_mac = ttk.Label(banc, textvariable=self.var_mac,
                                       font=("Consolas", 24, "bold"),
                                       foreground=COULEUR_ATTENTE)
        self.etiquette_mac.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 6))

        ttk.Label(banc, text="N° appareil").grid(row=3, column=0, sticky="w")
        self.champ_numero = ttk.Entry(banc, textvariable=self.var_numero,
                                      font=("Consolas", 16), width=10, state="disabled")
        self.champ_numero.grid(row=3, column=1, sticky="w", padx=(8, 0))
        self.champ_numero.bind("<Return>", lambda _: self._enregistrer_appareil())
        self.bouton_valider = ttk.Button(banc, text="Enregistrer (Entrée)",
                                         command=self._enregistrer_appareil,
                                         state="disabled", width=22)
        self.bouton_valider.grid(row=3, column=2, sticky="e")
        ttk.Label(banc, textvariable=self.var_apercu, foreground=COULEUR_INFO).grid(
            row=4, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(4, 0))
        ligne += 1

        # --- liste ----------------------------------------------------------
        cadre_liste = ttk.LabelFrame(self, text="Liste des relevés", padding=6)
        cadre_liste.grid(row=ligne, column=0, columnspan=2, sticky="nsew", pady=6)
        cadre_liste.columnconfigure(0, weight=1)
        cadre_liste.rowconfigure(0, weight=1)
        colonnes = ("numero", "mac", "ip", "horodatage")
        titres = {"numero": "N° de série", "mac": "Adresse MAC",
                  "ip": "IP", "horodatage": "Relevé le"}
        largeurs = {"numero": 190, "mac": 170, "ip": 120, "horodatage": 160}
        self.table = ttk.Treeview(cadre_liste, columns=colonnes, show="headings", height=8)
        for colonne in colonnes:
            self.table.heading(colonne, text=titres[colonne])
            self.table.column(colonne, width=largeurs[colonne], anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew")
        barre = ttk.Scrollbar(cadre_liste, orient="vertical", command=self.table.yview)
        barre.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=barre.set)

        boutons = ttk.Frame(cadre_liste)
        boutons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(boutons, text="Supprimer la ligne", command=self._supprimer_ligne,
                   width=20).grid(row=0, column=0)
        ttk.Button(boutons, text="Recharger la liste", command=self._charger_liste,
                   width=20).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(boutons, text="Générer les fichiers pour ExtractionMAC",
                   command=self._generer, width=40).grid(row=0, column=3, sticky="e")
        boutons.columnconfigure(2, weight=1)
        ligne += 1

        ttk.Label(self, textvariable=self.var_etat, relief="sunken", anchor="w",
                  padding=(6, 3)).grid(row=ligne, column=0, columnspan=2,
                                       sticky="ew", pady=(4, 0))

    # -------------------------------------------------------------- services
    def _dire(self, message):
        self.var_etat.set(message)

    def _groupes(self):
        profil = self._profil_courant()
        return tuple(profil["groupes_numero"])

    def _profil_courant(self):
        profil = config.profil_vide()
        profil.update({
            "ip_surveillee": self.var_ip.get().strip(),
            "prefixe_numero": self.var_prefixe.get().strip(),
            "dossier_fiches": self.var_dossier.get().strip(),
            "fichier_csv": self.var_csv.get().strip(),
            "vider_cache_arp": bool(self.var_vider.get()),
        })
        ancien = self.profils.get(self.var_profil.get().strip())
        if ancien:
            for cle in ("groupes_numero", "sous_dossier_rtf", "intervalle_ms",
                        "scrutations_stables", "scrutations_absence"):
                profil[cle] = ancien[cle]
        return profil

    def _appliquer_profil(self, profil):
        self.var_ip.set(profil["ip_surveillee"])
        self.var_prefixe.set(profil["prefixe_numero"])
        self.var_dossier.set(profil["dossier_fiches"])
        self.var_csv.set(profil["fichier_csv"])
        self.var_vider.set(profil["vider_cache_arp"])
        self.surveillance = surveillance.Surveillance(
            profil["scrutations_stables"], profil["scrutations_absence"])

    def _rafraichir_profils(self):
        self.liste_profils["values"] = sorted(self.profils)

    def _changer_profil(self, _=None):
        nom = self.var_profil.get().strip()
        if nom in self.profils:
            if self.surveillance.etat != surveillance.ARRET:
                self._arreter()          # le profil remplace la machine a etats
            self._appliquer_profil(self.profils[nom])
            self._charger_liste()
            self._dire("Profil « %s » chargé." % nom)

    def _enregistrer_profil(self):
        nom = self.var_profil.get().strip()
        if not nom:
            messagebox.showinfo("Profil", "Saisir d'abord un nom de profil.", parent=self)
            return
        self.profils[nom] = self._profil_courant()
        try:
            chemin = config.enregistrer(self.profils, nom)
        except OSError as erreur:
            messagebox.showerror("Profil", "Enregistrement impossible : %s" % erreur, parent=self)
            return
        self._rafraichir_profils()
        self._dire("Profil « %s » enregistré dans %s" % (nom, chemin))

    def _supprimer_profil(self):
        nom = self.var_profil.get().strip()
        if nom not in self.profils:
            return
        if not messagebox.askyesno("Profil", "Supprimer le profil « %s » ?" % nom, parent=self):
            return
        del self.profils[nom]
        try:
            config.enregistrer(self.profils, "")
        except OSError as erreur:
            messagebox.showerror("Profil", "Enregistrement impossible : %s" % erreur, parent=self)
            return
        self.var_profil.set("")
        self._rafraichir_profils()
        self._dire("Profil « %s » supprimé." % nom)

    # --------------------------------------------------------------- dossiers
    def _choisir_dossier(self):
        choix = filedialog.askdirectory(title="Dossier des fiches de test Excel",
                                        parent=self)
        if choix:
            self.var_dossier.set(choix)
            if not self.var_csv.get().strip():
                self.var_csv.set(os.path.join(choix, releve.NOM_DEFAUT))
                self._charger_liste()

    def _choisir_csv(self):
        choix = filedialog.asksaveasfilename(
            title="Fichier de la liste", defaultextension=".csv",
            initialfile=releve.NOM_DEFAUT,
            filetypes=[("Fichier CSV", "*.csv"), ("Tous les fichiers", "*.*")],
            confirmoverwrite=False, parent=self)
        if choix:
            self.var_csv.set(choix)
            self._charger_liste()

    def _deduire_prefixe(self):
        dossier = self.var_dossier.get().strip()
        if not os.path.isdir(dossier):
            messagebox.showinfo("Préfixe", "Choisir d'abord le dossier des fiches Excel.",
                                parent=self)
            return
        fiches = rtf.numeros_des_fiches(dossier, self._groupes())
        prefixe, message = mod_numero.deduire_prefixe(
            [os.path.basename(c) for c in fiches.values()], self._groupes())
        if not prefixe:
            messagebox.showwarning("Préfixe", message, parent=self)
            self._dire(message)
            return
        self.var_prefixe.set(prefixe)
        self._dire(message)

    # ------------------------------------------------------------------ liste
    def _charger_liste(self):
        chemin = self.var_csv.get().strip()
        self.releves, message = releve.charger(chemin)
        self._rafraichir_table()
        if message:
            self._dire(message)

    def _rafraichir_table(self):
        self.table.delete(*self.table.get_children())
        for index, element in enumerate(self.releves):
            self.table.insert("", "end", iid=str(index),
                              values=(element.numero, element.mac,
                                      element.ip, element.horodatage))
        enfants = self.table.get_children()
        if enfants:
            self.table.see(enfants[-1])

    def _sauver_liste(self):
        chemin = self.var_csv.get().strip()
        if not chemin:
            messagebox.showinfo("Liste", "Choisir d'abord le fichier de la liste (CSV) : "
                                         "sans lui, rien ne peut être enregistré.", parent=self)
            return False
        try:
            releve.enregistrer(chemin, self.releves)
        except OSError as erreur:
            messagebox.showerror("Liste", "Écriture impossible : %s" % erreur, parent=self)
            return False
        return True

    def _supprimer_ligne(self):
        selection = self.table.selection()
        if not selection:
            return
        index = int(selection[0])
        element = self.releves[index]
        if not messagebox.askyesno(
                "Liste", "Retirer %s (%s) de la liste ?" % (element.numero, element.mac),
                parent=self):
            return
        del self.releves[index]
        self._rafraichir_table()
        if self._sauver_liste():
            self._dire("%s retiré de la liste." % element.numero)

    # ------------------------------------------------------------ surveillance
    def _source_lire(self, ip):
        if self.source is not None:
            return self.source.lire(ip)
        return arp.lire(ip)

    def _source_vider(self, ip):
        if self.source is not None:
            return self.source.vider(ip)
        return arp.vider(ip)

    def _basculer_surveillance(self):
        if self.surveillance.etat == surveillance.ARRET:
            self._demarrer()
        else:
            self._arreter()

    def _demarrer(self):
        ip = self.var_ip.get().strip()
        if not ip:
            messagebox.showinfo("Surveillance", "Saisir l'adresse IP à surveiller.", parent=self)
            return
        if not self.var_csv.get().strip():
            messagebox.showinfo("Surveillance", "Choisir d'abord le fichier de la liste (CSV).",
                                parent=self)
            return
        prefixe, erreur = mod_numero.normaliser_prefixe(self.var_prefixe.get(), self._groupes())
        if erreur:
            messagebox.showwarning("Préfixe", erreur, parent=self)
            return
        self.var_prefixe.set(prefixe)
        self.surveillance.demarrer()
        self.bouton_marche.configure(text="Arrêter la surveillance")
        self._peindre_etat()
        self._dire("Surveillance de %s en cours." % ip)
        self._scruter()

    def _arreter(self):
        if self.boucle is not None:
            self.racine.after_cancel(self.boucle)
            self.boucle = None
        self.surveillance.arreter()
        self.bouton_marche.configure(text="Démarrer la surveillance")
        self._armer_saisie(None)
        self._peindre_etat()
        self._dire("Surveillance arrêtée.")

    def _intervalle(self):
        profil = self.profils.get(self.var_profil.get().strip())
        return (profil or config.PROFIL_DEFAUT)["intervalle_ms"]

    def _scruter(self):
        self.boucle = None
        if self.surveillance.etat == surveillance.ARRET:
            return
        ip = self.var_ip.get().strip()
        evenement = self.surveillance.scruter(self._source_lire(ip))
        if evenement:
            self._traiter(evenement, ip)
        self._peindre_etat()
        self.boucle = self.racine.after(self._intervalle(), self._scruter)

    def _traiter(self, evenement, ip):
        nature, mac = evenement
        if nature == surveillance.DETECTION:
            self._avertir_sonore()
            self._armer_saisie(mac)
            self._dire("Appareil détecté : %s" % mac)
        elif nature == surveillance.IDENTIQUE:
            self._armer_saisie(None)
            self.var_mac.set(mac)
            self.etiquette_mac.configure(foreground=COULEUR_ALERTE)
            self._dire("MAC identique au relevé précédent : cache ARP non vidé ou "
                       "appareil non remplacé. Débrancher, puis vider le cache ARP.")
        elif nature == surveillance.RETRAIT:
            self._armer_saisie(None)
            if self.var_vider.get():
                succes, message = self._source_vider(ip)
                self._dire(message)
                if not succes:
                    self.bouton_admin.grid(row=0, column=3, padx=(8, 0))
            else:
                self._dire("Appareil retiré. En attente du suivant…")
        elif nature == surveillance.PERDU:
            self._armer_saisie(None)
            self._dire("L'appareil a disparu avant la saisie du numéro.")

    def _armer_saisie(self, mac):
        """Ouvre ou ferme le champ du numero selon qu'un appareil attend d'etre nomme."""
        self.mac_a_enregistrer = mac
        self.origine_manuelle = False
        if mac:
            self.var_mac.set(mac)
            self.etiquette_mac.configure(foreground=COULEUR_DETECTE)
            self.champ_numero.configure(state="normal")
            self.bouton_valider.configure(state="normal")
            self.var_numero.set("")
            self.champ_numero.focus_set()
        else:
            self.var_mac.set("—")
            self.etiquette_mac.configure(foreground=COULEUR_ATTENTE)
            self.champ_numero.configure(state="disabled")
            self.bouton_valider.configure(state="disabled")
            self.var_numero.set("")
            self.var_apercu.set("")

    def _peindre_etat(self):
        etat = self.surveillance.etat
        self.var_etat_banc.set(surveillance.LIBELLES[etat])
        couleurs = {surveillance.ARRET: COULEUR_ATTENTE,
                    surveillance.ATTENTE: COULEUR_INFO,
                    surveillance.DETECTE: COULEUR_DETECTE,
                    surveillance.ATTENTE_RETRAIT: COULEUR_INFO}
        self.etiquette_etat_banc.configure(foreground=couleurs[etat])

    def _avertir_sonore(self):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except (ImportError, RuntimeError, AttributeError):
            try:
                self.racine.bell()
            except tk.TclError:
                pass

    # --------------------------------------------------------- enregistrement
    def _rafraichir_apercu(self):
        if not self.mac_a_enregistrer:
            self.var_apercu.set("")
            return
        complet, erreur = mod_numero.composer(self.var_prefixe.get(),
                                              self.var_numero.get(), self._groupes())
        self.var_apercu.set(complet if complet else (erreur or ""))

    def _enregistrer_appareil(self):
        mac = self.mac_a_enregistrer
        if not mac:
            return
        complet, erreur = mod_numero.composer(self.var_prefixe.get(),
                                              self.var_numero.get(), self._groupes())
        if erreur:
            messagebox.showwarning("Numéro", erreur, parent=self)
            self.champ_numero.focus_set()
            return

        avertissements = releve.controler(self.releves, complet, mac)
        dossier = self.var_dossier.get().strip()
        if os.path.isdir(dossier):
            fiches = rtf.numeros_des_fiches(dossier, self._groupes())
            if fiches and complet not in fiches:
                avertissements.append(
                    "aucune fiche Excel du dossier ne porte le numéro %s "
                    "(faute de frappe ?)" % complet)
        if avertissements:
            texte = "\n".join("• " + a for a in avertissements)
            if not messagebox.askyesno("Vérification",
                                       "%s\n\nEnregistrer quand même %s ?" % (texte, complet),
                                       parent=self, icon="warning"):
                self.champ_numero.focus_set()
                return

        self.releves.append(releve.Releve(complet, mac, self.var_ip.get().strip()))
        self._rafraichir_table()
        if not self._sauver_liste():
            self.releves.pop()
            self._rafraichir_table()
            return

        manuelle = self.origine_manuelle
        self._armer_saisie(None)
        if not manuelle:
            self.surveillance.enregistrer()
        elif not self.surveillance.ignorer():
            # La machine n'avait rien detecte : on retient quand meme cette MAC,
            # pour que le garde-fou « MAC identique » joue au coup suivant.
            self.surveillance.derniere_enregistree = mac
        if self.source is not None and hasattr(self.source, "suivant"):
            self.source.suivant()
        self._peindre_etat()
        self._dire("%s → %s enregistré (%d au total). Débrancher l'appareil."
                   % (complet, mac, len(self.releves)))

    def _saisie_manuelle(self):
        """Roue de secours : recopier la MAC affichee par Tftpd32.

        La detection automatique couvre le cas normal ; ce bouton evite d'etre
        totalement bloque le jour ou elle ne passe pas (appareil muet en ARP,
        poste sans droits, adresse IP inattendue).
        """
        from tkinter import simpledialog
        brut = simpledialog.askstring(
            "Saisie manuelle",
            "Adresse MAC relevée dans Tftpd32 :\n(00:30:D6:4C:6E:05, 00-30-D6-4C-6E-05…)",
            parent=self)
        if not brut:
            return
        mac = arp.normaliser(brut)
        exploitable, raison = arp.mac_exploitable(mac)
        if not exploitable:
            messagebox.showwarning("Saisie manuelle", raison, parent=self)
            return
        self._armer_saisie(mac)
        self.origine_manuelle = True
        self.etiquette_mac.configure(foreground=COULEUR_INFO)
        self._dire("MAC saisie à la main : %s — saisir le numéro de l'appareil." % mac)

    # ---------------------------------------------------------------- outils
    def _tester_ip(self):
        ip = self.var_ip.get().strip()
        if not ip:
            return
        mac = self._source_lire(ip)
        if mac:
            self._dire("%s répond : %s" % (ip, mac))
        else:
            self._dire("Aucune réponse de %s (appareil débranché, IP différente, "
                       "ou pas encore d'entrée ARP)." % ip)

    def _vider_cache(self):
        ip = self.var_ip.get().strip()
        if not ip:
            return
        succes, message = self._source_vider(ip)
        self._dire(message)
        if not succes:
            self.bouton_admin.grid(row=0, column=3, padx=(8, 0))

    def _relancer_admin(self):
        if not messagebox.askyesno(
                "Administrateur",
                "Le programme va se relancer avec les droits administrateur.\n"
                "Fermer cette fenêtre ensuite.\n\nContinuer ?", parent=self):
            return
        succes, message = arp.relancer_en_administrateur()
        self._dire(message)
        if succes:
            self.racine.after(500, self._fermer)

    def _generer(self):
        if not self.releves:
            messagebox.showinfo("Génération", "La liste est vide.", parent=self)
            return
        dossier = self.var_dossier.get().strip()
        if not os.path.isdir(dossier):
            messagebox.showinfo("Génération",
                                "Choisir d'abord le dossier des fiches de test Excel.",
                                parent=self)
            return
        profil = self.profils.get(self.var_profil.get().strip()) or config.PROFIL_DEFAUT
        sortie = os.path.join(dossier, profil["sous_dossier_rtf"])
        groupes = self._groupes()

        if not messagebox.askyesno(
                "Génération",
                "Écrire %d fichier(s) dans :\n%s\n\n"
                "Lancer ensuite ExtractionMAC sur :\n%s\n"
                "en cochant « Inclure les sous-dossiers »."
                % (len(self.releves), sortie, dossier), parent=self):
            return

        bilan = rtf.generer(self.releves, sortie,
                            rtf.fichiers_word_existants(dossier, groupes, sortie))
        lignes = [bilan.resume(), "", "Dossier : %s" % sortie]
        if bilan.conflits or bilan.erreurs:
            lignes.append("")
            for numero, message in bilan.conflits + bilan.erreurs:
                lignes.append("• %s : %s" % (numero, message))
        fiches = rtf.numeros_des_fiches(dossier, groupes)
        orphelins = [n for n, _ in bilan.ecrits if fiches and n not in fiches]
        if orphelins:
            lignes.append("")
            lignes.append("Sans fiche Excel correspondante : %s" % ", ".join(orphelins[:8]))
        texte = "\n".join(lignes)
        if bilan.conflits or bilan.erreurs or orphelins:
            messagebox.showwarning("Génération", texte, parent=self)
        else:
            messagebox.showinfo("Génération", texte, parent=self)
        self._dire(bilan.resume() + " dans " + sortie)

    def _fermer(self):
        if self.boucle is not None:
            self.racine.after_cancel(self.boucle)
            self.boucle = None
        self.racine.destroy()


# --------------------------------------------------------------------------
# points d'entree
# --------------------------------------------------------------------------

def diagnostic():
    """Ecrit les emplacements resolus dans un fichier, a cote de la configuration.

    Sert au support (« ou sont passes mes profils ? ») et permet de verifier,
    sur l'executable reellement produit, que la configuration est bien ecrite
    a cote de lui.
    """
    lignes = [
        "Enregistrement MAC %s" % __version__,
        "figé par PyInstaller : %s" % bool(getattr(sys, "frozen", False)),
        "exécutable           : %s" % sys.executable,
        "dossier du programme : %s" % config.dossier_programme(),
        "dossier de repli     : %s" % config.dossier_repli(),
        "fichier de config    : %s" % config.chemin_config(),
    ]
    texte = "\n".join(lignes)
    cible = os.path.join(os.path.dirname(config.chemin_config()), NOM_DIAGNOSTIC)
    try:
        with open(cible, "w", encoding="utf-8") as fichier:
            fichier.write(texte + "\n")
    except OSError as erreur:
        texte += "\n(diagnostic non enregistré : %s)" % erreur
    if sys.stdout is not None:                     # absent en mode fenetre
        print(texte)
    return texte


def principal(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    options = {a.lstrip("-/").lower() for a in argv}
    if "diagnostic" in options:
        diagnostic()
        return 0
    lancer(simulation="simulation" in options)
    return 0


def lancer(simulation=False):
    racine = tk.Tk()
    titre = "Enregistrement MAC - relevé au banc  v%s" % __version__
    if simulation:
        titre += "   [SIMULATION]"
    racine.title(titre)
    racine.minsize(820, 760)
    try:
        racine.call("ttk::style", "theme", "use", "vista")
    except tk.TclError:
        pass
    Application(racine, source=SimulateurArp() if simulation else None)
    racine.mainloop()
