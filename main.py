import os
import re
import io
import random
import shutil
from pathlib import Path
from pypdf import PdfReader
from docx import Document
import ollama
import pytesseract
import fitz  # PyMuPDF
from PIL import Image

# Dossier contenant les documents à trier
DOSSIER_SOURCE = "documents_a_trier"
# Dossier où sont ranges les documents classes par client
DOSSIER_DESTINATION = "documents_classes"
# Dossier où sont preparees les fiches de rendez-vous
DOSSIER_PREPARATION = "preparations_rdv"

# Civilites et titres a ignorer pour comparer les noms
CIVILITES = ["monsieur", "madame", "mademoiselle", "mme", "mlle", "m.", "m"]

# Langue utilisee pour l'OCR (documents juridiques francais)
LANGUE_OCR = "fra"

# Nombre de tentatives si le modele repond INCONNU
NB_TENTATIVES_MAX = 3

# Options du modele : temperature basse = reponses plus stables/deterministes
OPTIONS_MODELE = {"temperature": 0.1}


# Banques de formulations variees pour rendre Atlas moins robotique
MESSAGES = {
    "document_classe_simple": [
        "C'est fait, classé dans le dossier « {dossier} ».",
        "Document rangé dans le dossier « {dossier} ».",
        "Classé sous « {dossier} ».",
        "Direction le dossier « {dossier} ».",
    ],
    "document_classe_variante": [
        "J'ai identifié {client} — reconnu comme le même client que le dossier existant « {dossier} ».",
        "'{client}' correspond au client déjà suivi sous « {dossier} », classé avec le reste de son dossier.",
        "Même client que « {dossier} » malgré une formulation différente ({client}), regroupé ensemble.",
    ],
    "client_inconnu": [
        "Je n'ai pas réussi à identifier de client pour ce document, je le laisse de côté.",
        "Aucun nom de client clair dans ce document — je préfère ne pas le classer au hasard.",
        "Ce document reste non classé, faute d'avoir identifié un client précis.",
    ],
    "fichier_vide": [
        "Ce fichier semble vide ou illisible, je l'ignore.",
        "Rien à lire dans ce fichier, il est passé de côté.",
    ],
    "type_non_supporte": [
        "Ce type de fichier ({extension}) n'est pas encore pris en charge.",
        "Format {extension} non supporté pour l'instant, fichier ignoré.",
    ],
    "conflit_detecte": [
        "⚠️ Attention : '{partie}' correspond à un client déjà existant, '{dossier_existant}'. Un conflit d'intérêts est possible.",
        "⚠️ Signal de vigilance : '{partie}' apparaît aussi comme client dans le dossier '{dossier_existant}'.",
        "⚠️ À vérifier avant d'aller plus loin : '{partie}' est déjà client sous le dossier '{dossier_existant}'.",
    ],
    "classement_termine": [
        "Classement terminé.",
        "Voilà, tous les documents ont été traités.",
        "C'est fait, le classement est à jour.",
    ],
}


def message_varie(type_message, **contexte):
    """Choisit aleatoirement une formulation parmi celles disponibles pour ce type de message"""
    formulations = MESSAGES.get(type_message, ["{fallback}"])
    formulation_choisie = random.choice(formulations)
    return formulation_choisie.format(**contexte)


def extraire_texte_par_ocr(chemin_fichier):
    """Convertit chaque page d'un PDF en image et lit le texte via OCR (Tesseract)"""
    texte_ocr = ""

    document_pdf = fitz.open(str(chemin_fichier))

    for numero_page in range(len(document_pdf)):
        page = document_pdf[numero_page]
        pixmap = page.get_pixmap(dpi=300)
        image_bytes = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(image_bytes))

        texte_page = pytesseract.image_to_string(image, lang=LANGUE_OCR)
        texte_ocr += texte_page + "\n"

    document_pdf.close()
    return texte_ocr


def lire_texte_fichier(chemin_fichier):
    """Extrait le texte d'un fichier .txt, .pdf ou .docx (avec repli sur l'OCR si necessaire)"""
    extension = chemin_fichier.suffix.lower()

    if extension == ".txt":
        return chemin_fichier.read_text(encoding="utf-8", errors="ignore")

    elif extension == ".pdf":
        lecteur = PdfReader(str(chemin_fichier))
        texte = ""
        for page in lecteur.pages:
            texte += page.extract_text() or ""

        if not texte.strip():
            print("  → Aucun texte trouvé, tentative de lecture par OCR (document scanné)...")
            texte = extraire_texte_par_ocr(chemin_fichier)

        return texte

    elif extension == ".docx":
        doc = Document(str(chemin_fichier))
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        return None


def identifier_client(texte_document):
    """Demande au modele local d'identifier le nom du client, avec plusieurs tentatives si echec"""
    prompt = f"""Voici le contenu d'un document juridique. 
Identifie le nom complet du CLIENT du cabinet (pas l'avocat, pas le juge, pas l'huissier) concerne par ce document.
Reponds UNIQUEMENT avec le nom, sans civilite (pas de M., Madame, Monsieur), sans phrase, sans explication.
Si tu ne trouves aucun nom de client clair, reponds exactement : INCONNU

Document :
{texte_document[:2000]}
"""

    for tentative in range(1, NB_TENTATIVES_MAX + 1):
        reponse = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options=OPTIONS_MODELE
        )

        nom_client = reponse["message"]["content"].strip()

        if nom_client and nom_client.upper() != "INCONNU":
            return nom_client

        if tentative < NB_TENTATIVES_MAX:
            print(f"  → Tentative {tentative} infructueuse, nouvel essai...")

    return "INCONNU"


def identifier_toutes_les_parties(texte_document):
    """Demande au modele d'identifier TOUTES les personnes/entites mentionnees (client + partie adverse + tiers)"""
    prompt = f"""Voici le contenu d'un document juridique.
Identifie TOUS les noms de personnes ou d'entreprises mentionnes qui sont des PARTIES a l'affaire
(le client, la partie adverse, les tiers impliques). Ignore les avocats, juges, huissiers, notaires.

Reponds UNIQUEMENT avec une liste de noms separes par des virgules, sans phrase, sans explication.
Exemple de format : Jean Dupont, Societe ABC, Marie Martin
Si aucun nom n'est identifiable, reponds exactement : AUCUN

Document :
{texte_document[:2000]}
"""

    reponse = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}],
        options=OPTIONS_MODELE
    )

    texte_reponse = reponse["message"]["content"].strip()

    if texte_reponse.upper() == "AUCUN" or not texte_reponse:
        return []

    noms = [nom.strip() for nom in texte_reponse.split(",") if nom.strip()]
    return noms


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


def detecter_conflits_interets(parties_mentionnees, client_principal, dossier_destination):
    """Verifie si une partie mentionnee (autre que le client principal) correspond a un client existant"""
    conflits_detectes = []

    if not dossier_destination.exists():
        return conflits_detectes

    nom_normalise_client_principal = normaliser_nom(client_principal)

    for partie in parties_mentionnees:
        nom_normalise_partie = normaliser_nom(partie)

        if nom_normalise_partie == nom_normalise_client_principal:
            continue

        dossier_correspondant = trouver_dossier_existant(partie, dossier_destination)

        if dossier_correspondant:
            conflits_detectes.append((partie, dossier_correspondant.name))

    return conflits_detectes


def classer_documents():
    """Parcourt le dossier source et classe chaque document par client, avec detection de conflits"""
    dossier_source = Path(DOSSIER_SOURCE)
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_destination.mkdir(exist_ok=True)

    resultats = []

    if not dossier_source.exists():
        print(f"Le dossier '{DOSSIER_SOURCE}' n'existe pas.")
        return resultats

    fichiers = list(dossier_source.iterdir())
    print(f"{len(fichiers)} fichier(s) trouvé(s) à traiter.\n")

    for fichier in fichiers:
        if not fichier.is_file():
            continue

        print(f"Analyse de : {fichier.name}")
        extension = fichier.suffix.lower()

        if extension not in [".txt", ".pdf", ".docx"]:
            print(f"  → {message_varie('type_non_supporte', extension=extension)}\n")
            resultats.append({
                "fichier": fichier.name, "statut": "ignore",
                "client": None, "dossier": None, "conflits": []
            })
            continue

        texte = lire_texte_fichier(fichier)

        if not texte or not texte.strip():
            print(f"  → {message_varie('fichier_vide')}\n")
            resultats.append({
                "fichier": fichier.name, "statut": "vide",
                "client": None, "dossier": None, "conflits": []
            })
            continue

        client = identifier_client(texte)

        if client == "INCONNU" or not client:
            print(f"  → {message_varie('client_inconnu')}\n")
            resultats.append({
                "fichier": fichier.name, "statut": "inconnu",
                "client": None, "dossier": None, "conflits": []
            })
            continue

        parties = identifier_toutes_les_parties(texte)
        conflits = detecter_conflits_interets(parties, client, dossier_destination)

        if conflits:
            for nom_partie, nom_dossier_existant in conflits:
                print(f"  {message_varie('conflit_detecte', partie=nom_partie, dossier_existant=nom_dossier_existant)}")
            print()

        dossier_existant = trouver_dossier_existant(client, dossier_destination)

        if dossier_existant:
            dossier_client = dossier_existant
        else:
            nom_dossier_client = "".join(c for c in client if c.isalnum() or c in " -_").strip()
            dossier_client = dossier_destination / nom_dossier_client
            dossier_client.mkdir(exist_ok=True)

        destination = dossier_client / fichier.name
        shutil.copy2(fichier, destination)

        if normaliser_nom(client) == normaliser_nom(dossier_client.name):
            print(f"  → {message_varie('document_classe_simple', dossier=dossier_client.name)}\n")
        else:
            print(f"  → {message_varie('document_classe_variante', client=client, dossier=dossier_client.name)}\n")

        resultats.append({
            "fichier": fichier.name, "statut": "classe",
            "client": client, "dossier": dossier_client.name, "conflits": conflits
        })

    print(message_varie("classement_termine"))
    return resultats


def preparer_dossier_client(nom_client):
    """Rassemble les documents d'un client et genere un resume avant rendez-vous"""
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_preparation = Path(DOSSIER_PREPARATION)

    dossier_client = trouver_dossier_existant(nom_client, dossier_destination)

    if not dossier_client:
        print(f"Aucun dossier trouvé pour '{nom_client}'.")
        print("Vérifie l'orthographe, ou que ses documents ont bien été classés.")
        return

    dossier_preparation.mkdir(exist_ok=True)
    dossier_sortie = dossier_preparation / dossier_client.name
    dossier_sortie.mkdir(exist_ok=True)

    documents = [f for f in dossier_client.iterdir() if f.is_file()]

    if not documents:
        print(f"Le dossier de {dossier_client.name} ne contient aucun document.")
        return

    print(f"Préparation du dossier de {dossier_client.name} ({len(documents)} document(s))...\n")

    contenu_complet = ""
    for document in documents:
        shutil.copy2(document, dossier_sortie / document.name)
        texte = lire_texte_fichier(document)
        if texte:
            contenu_complet += f"\n--- {document.name} ---\n{texte}\n"

    resume = generer_resume(contenu_complet, dossier_client.name)

    fichier_resume = dossier_sortie / "RESUME.txt"
    fichier_resume.write_text(resume, encoding="utf-8")

    print(f"Documents copiés dans : {dossier_sortie}")
    print(f"Résumé généré : {fichier_resume}\n")
    print("--- Résumé ---")
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
        messages=[{"role": "user", "content": prompt}],
        options=OPTIONS_MODELE
    )

    return reponse["message"]["content"].strip()


def lister_documents_client(nom_client):
    """Liste les documents d'un client donne"""
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_client = trouver_dossier_existant(nom_client, dossier_destination)

    if not dossier_client:
        print(f"Aucun dossier trouvé pour '{nom_client}'.")
        return []

    documents = [f for f in dossier_client.iterdir() if f.is_file()]

    if not documents:
        print(f"Le dossier de {dossier_client.name} est vide.")
        return []

    print(f"Documents de {dossier_client.name} :")
    for document in documents:
        print(f"  - {document.name}")

    return documents


def renommer_document(nom_client, ancien_nom, nouveau_nom):
    """Renomme un document dans le dossier d'un client"""
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_client = trouver_dossier_existant(nom_client, dossier_destination)

    if not dossier_client:
        print(f"Aucun dossier trouvé pour '{nom_client}'.")
        return False

    chemin_ancien = dossier_client / ancien_nom

    if not chemin_ancien.exists():
        print(f"Le document '{ancien_nom}' n'existe pas dans le dossier de {dossier_client.name}.")
        return False

    if not Path(nouveau_nom).suffix:
        nouveau_nom = nouveau_nom + chemin_ancien.suffix

    chemin_nouveau = dossier_client / nouveau_nom
    chemin_ancien.rename(chemin_nouveau)

    print(f"Document renommé : '{ancien_nom}' → '{nouveau_nom}' (dossier {dossier_client.name})")
    return True


def deplacer_document(nom_document, client_source, client_destination):
    """Deplace un document du dossier d'un client vers un autre"""
    dossier_destination_racine = Path(DOSSIER_DESTINATION)

    dossier_source = trouver_dossier_existant(client_source, dossier_destination_racine)
    if not dossier_source:
        print(f"Aucun dossier trouvé pour '{client_source}'.")
        return False

    chemin_document = dossier_source / nom_document
    if not chemin_document.exists():
        print(f"Le document '{nom_document}' n'existe pas dans le dossier de {dossier_source.name}.")
        return False

    dossier_cible = trouver_dossier_existant(client_destination, dossier_destination_racine)
    if not dossier_cible:
        nom_dossier_cible = "".join(c for c in client_destination if c.isalnum() or c in " -_").strip()
        dossier_cible = dossier_destination_racine / nom_dossier_cible
        dossier_cible.mkdir(exist_ok=True)

    chemin_cible = dossier_cible / nom_document
    shutil.move(str(chemin_document), str(chemin_cible))

    print(f"Document déplacé : '{nom_document}' de {dossier_source.name} vers {dossier_cible.name}")
    return True


def supprimer_document(nom_client, nom_document):
    """Supprime un document du dossier d'un client (avec confirmation obligatoire cote appelant)"""
    dossier_destination = Path(DOSSIER_DESTINATION)
    dossier_client = trouver_dossier_existant(nom_client, dossier_destination)

    if not dossier_client:
        print(f"Aucun dossier trouvé pour '{nom_client}'.")
        return False

    chemin_document = dossier_client / nom_document

    if not chemin_document.exists():
        print(f"Le document '{nom_document}' n'existe pas dans le dossier de {dossier_client.name}.")
        return False

    chemin_document.unlink()
    print(f"Document supprimé : '{nom_document}' (dossier {dossier_client.name})")
    return True


if __name__ == "__main__":
    classer_documents()