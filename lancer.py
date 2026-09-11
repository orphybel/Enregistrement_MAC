"""Point d'entree utilise par PyInstaller et par un double-clic sur ce fichier."""

import sys

from enregistrement_mac.gui import principal

if __name__ == "__main__":
    sys.exit(principal())
