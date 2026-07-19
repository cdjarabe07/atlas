import os
import re
import shutil
from pathlib import Path
from pypdf import PdfReader
from docx import Document
import ollama

# Dossier contenant les documents à trier
DOSSIER_SOURCE = "documents_a_trier"
# Dossier où seront rangés les documents classés par client
DOSSIER_DESTINATION = "documents_classes"

# Civilités et titres à ignorer pour comparer les noms
CIVILITES = ["monsieur", "madame", "mademoiselle", "mme", "mlle", "m.", "m"]


def lire_texte_fichier(chemin_fichier):
    """Extrait le texte d'un fichier .txt, .pdf ou .docx"""
    extension = chemin_fichier.suffix.lower()

    if extension == ".txt":
        return chemin_fichier.read_text(encoding="utf-8", errors="ignore")

    elif extension == ".pdf":
        lecteur = PdfReader(str(chemin_fichier))
        texte = ""
        for page in lecteur.pages:
            texte += page.extract_text() or ""
        return texte

    elif extension == ".docx":
        doc = Document(str(chemin_fichier))
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        return None


def identifier_client(texte_document):
    """Demande au modèle local d'identifier le nom du client dans le texte"""
    prompt = f"""Voici le contenu d'un document juridique. 
Identifie le nom complet du CLIENT du cabinet (pas l'avocat, pas le juge, pas l'huissier) concerné par ce document.
Réponds UNIQUEMENT avec le nom, sans civilité (pas de M., Madame, Monsieur), sans phrase, sans explication.
Si tu ne trouves aucun nom de client clair, réponds exactement : INCONNU

Document :
{texte_document[:2000]}
"""

    reponse = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}]
    )

    nom_client = reponse["message"]["content"].strip()
    return nom_client


def normaliser_nom(nom):
    """Normalise un nom pour comparaison : enlève civilités, ponctuation, casse"""
    nom_normalise = nom.lower()
    nom_normalise = re.sub(r'[.,]', '', nom_normalise)

    mots = nom_normalise.split()
    mots_filtres = [mot for mot in mots if mot not in CIVILITES]

    return " ".join(mots_filtres).strip()


def trouver_dossier_existant(nom_client, dossier_destination):
    """Cherche si un dossier correspondant à ce client existe déjà (comparaison normalisée)"""
    nom_normalise_cible = normaliser_nom(nom_client)

    if not dossier_destination.exists():
        return None

    for dossier_existant in dossier_destination.iterdir():
        if dossier_existant.is_dir():
            if normaliser_nom(dossier_existant.name) == nom_normalise_cible:
                return dossier_existant

    return None


def classer_documents():
    """Parcourt le dossier source et classe chaque document par client"""
    dossier_source = Path(DOSSIER_SOURCE)
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_destination.mkdir(exist_ok=True)

    if not dossier_source.exists():
        print(f"Le dossier '{DOSSIER_SOURCE}' n'existe pas.")
        return

    fichiers = list(dossier_source.iterdir())
    print(f"{len(fichiers)} fichier(s) trouvé(s) à traiter.\n")

    for fichier in fichiers:
        if not fichier.is_file():
            continue

        print(f"Analyse de : {fichier.name}")
        extension = fichier.suffix.lower()

        if extension not in [".txt", ".pdf", ".docx"]:
            print(f"  → Type de fichier non supporté ({extension}), ignoré.\n")
            continue

        texte = lire_texte_fichier(fichier)

        if not texte or not texte.strip():
            print(f"  → Fichier vide ou illisible, ignoré.\n")
            continue

        client = identifier_client(texte)

        if client == "INCONNU" or not client:
            print(f"  → Client non identifié, fichier laissé de côté.\n")
            continue

        # Vérifier si un dossier équivalent existe déjà (même client, autre formulation)
        dossier_existant = trouver_dossier_existant(client, dossier_destination)

        if dossier_existant:
            dossier_client = dossier_existant
        else:
            nom_dossier_client = "".join(c for c in client if c.isalnum() or c in " -_").strip()
            dossier_client = dossier_destination / nom_dossier_client
            dossier_client.mkdir(exist_ok=True)

        destination = dossier_client / fichier.name
        shutil.copy2(fichier, destination)

        print(f"  → Client identifié : {client}")
        print(f"  → Classé dans : {destination}\n")

    print("Classement terminé.")


if __name__ == "__main__":
    classer_documents()