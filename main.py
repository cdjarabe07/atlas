import os
import re
import shutil
from pathlib import Path
from pypdf import PdfReader
from docx import Document
import ollama

# Dossier contenant les documents à trier
DOSSIER_SOURCE = "documents_a_trier"
# Dossier où sont ranges les documents classes par client
DOSSIER_DESTINATION = "documents_classes"
# Dossier où sont preparees les fiches de rendez-vous
DOSSIER_PREPARATION = "preparations_rdv"

# Civilites et titres a ignorer pour comparer les noms
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
    """Demande au modele local d'identifier le nom du client dans le texte"""
    prompt = f"""Voici le contenu d'un document juridique. 
Identifie le nom complet du CLIENT du cabinet (pas l'avocat, pas le juge, pas l'huissier) concerne par ce document.
Reponds UNIQUEMENT avec le nom, sans civilite (pas de M., Madame, Monsieur), sans phrase, sans explication.
Si tu ne trouves aucun nom de client clair, reponds exactement : INCONNU

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
    """Normalise un nom pour comparaison : enleve civilites, ponctuation, casse"""
    nom_normalise = nom.lower()
    nom_normalise = re.sub(r'[.,]', '', nom_normalise)

    mots = nom_normalise.split()
    mots_filtres = [mot for mot in mots if mot not in CIVILITES]

    return " ".join(mots_filtres).strip()


def trouver_dossier_existant(nom_client, dossier_destination):
    """Cherche si un dossier correspondant a ce client existe deja (comparaison normalisee)"""
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
    print(f"{len(fichiers)} fichier(s) trouve(s) a traiter.\n")

    for fichier in fichiers:
        if not fichier.is_file():
            continue

        print(f"Analyse de : {fichier.name}")
        extension = fichier.suffix.lower()

        if extension not in [".txt", ".pdf", ".docx"]:
            print(f"  → Type de fichier non supporte ({extension}), ignore.\n")
            continue

        texte = lire_texte_fichier(fichier)

        if not texte or not texte.strip():
            print(f"  → Fichier vide ou illisible, ignore.\n")
            continue

        client = identifier_client(texte)

        if client == "INCONNU" or not client:
            print(f"  → Client non identifie, fichier laisse de cote.\n")
            continue

        dossier_existant = trouver_dossier_existant(client, dossier_destination)

        if dossier_existant:
            dossier_client = dossier_existant
        else:
            nom_dossier_client = "".join(c for c in client if c.isalnum() or c in " -_").strip()
            dossier_client = dossier_destination / nom_dossier_client
            dossier_client.mkdir(exist_ok=True)

        destination = dossier_client / fichier.name
        shutil.copy2(fichier, destination)

        print(f"  → Client identifie : {client}")
        print(f"  → Classe dans : {destination}\n")

    print("Classement termine.")


def preparer_dossier_client(nom_client):
    """Rassemble les documents d'un client et genere un resume avant rendez-vous"""
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_preparation = Path(DOSSIER_PREPARATION)

    dossier_client = trouver_dossier_existant(nom_client, dossier_destination)

    if not dossier_client:
        print(f"Aucun dossier trouve pour '{nom_client}'.")
        print("Verifie l'orthographe, ou que ses documents ont bien ete classes.")
        return

    dossier_preparation.mkdir(exist_ok=True)
    dossier_sortie = dossier_preparation / dossier_client.name
    dossier_sortie.mkdir(exist_ok=True)

    documents = [f for f in dossier_client.iterdir() if f.is_file()]

    if not documents:
        print(f"Le dossier de {dossier_client.name} ne contient aucun document.")
        return

    print(f"Preparation du dossier de {dossier_client.name} ({len(documents)} document(s))...\n")

    contenu_complet = ""
    for document in documents:
        shutil.copy2(document, dossier_sortie / document.name)
        texte = lire_texte_fichier(document)
        if texte:
            contenu_complet += f"\n--- {document.name} ---\n{texte}\n"

    resume = generer_resume(contenu_complet, dossier_client.name)

    fichier_resume = dossier_sortie / "RESUME.txt"
    fichier_resume.write_text(resume, encoding="utf-8")

    print(f"Documents copies dans : {dossier_sortie}")
    print(f"Resume genere : {fichier_resume}\n")
    print("--- Resume ---")
    print(resume)


def generer_resume(contenu_complet, nom_client):
    """Demande au modele local de resumer l'ensemble des documents d'un client"""
    prompt = f"""Voici l'ensemble des documents du dossier client {nom_client}.
Redige un resume court (5 a 8 lignes) reprenant :
- La nature de l'affaire
- Les points cles a retenir avant un rendez-vous avec ce client

Documents :
{contenu_complet[:4000]}
"""

    reponse = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}]
    )

    return reponse["message"]["content"].strip()


if __name__ == "__main__":
    classer_documents()