import streamlit as st
from pathlib import Path
import shutil
from main import classer_documents, preparer_dossier_client, DOSSIER_SOURCE, DOSSIER_PREPARATION

st.set_page_config(page_title="Atlas", page_icon="⚖️", layout="centered")

st.title("⚖️ Atlas")
st.caption("Assistant local pour la gestion documentaire du cabinet")

onglet_classement, onglet_preparation = st.tabs(["📂 Classer des documents", "🗂️ Préparer un rendez-vous"])


with onglet_classement:
    st.subheader("Classer les documents en attente")

    dossier_source = Path(DOSSIER_SOURCE)
    dossier_source.mkdir(exist_ok=True)

    fichiers_uploades = st.file_uploader(
        "Dépose ici les documents à classer (txt, pdf, docx)",
        type=["txt", "pdf", "docx"],
        accept_multiple_files=True
    )

    if fichiers_uploades:
        for fichier_uploade in fichiers_uploades:
            chemin_destination = dossier_source / fichier_uploade.name
            with open(chemin_destination, "wb") as f:
                f.write(fichier_uploade.getbuffer())
        st.success(f"{len(fichiers_uploades)} fichier(s) prêt(s) à être classé(s).")

    fichiers_en_attente = [f.name for f in dossier_source.iterdir() if f.is_file()]

    if fichiers_en_attente:
        st.info(f"{len(fichiers_en_attente)} fichier(s) en attente : {', '.join(fichiers_en_attente)}")

    if st.button("🚀 Lancer le classement", type="primary", disabled=not fichiers_en_attente):
        with st.spinner("Analyse en cours (le modèle local traite chaque document)..."):
            resultats = classer_documents()

        st.success("Classement terminé.")

        for resultat in resultats:
            if resultat["statut"] == "classe":
                if resultat["conflits"]:
                    st.warning(
                        f"**{resultat['fichier']}** → Client : {resultat['client']} "
                        f"→ Classé dans : {resultat['dossier']}\n\n"
                        f"⚠️ **Conflit d'intérêts potentiel :** "
                        + ", ".join(f"'{p}' correspond à '{d}'" for p, d in resultat["conflits"])
                    )
                else:
                    st.success(f"**{resultat['fichier']}** → Client : {resultat['client']} → Classé dans : {resultat['dossier']}")
            elif resultat["statut"] == "inconnu":
                st.warning(f"**{resultat['fichier']}** → Client non identifié, laissé de côté.")
            elif resultat["statut"] == "vide":
                st.info(f"**{resultat['fichier']}** → Fichier vide ou illisible, ignoré.")
            else:
                st.info(f"**{resultat['fichier']}** → Type de fichier non supporté, ignoré.")


with onglet_preparation:
    st.subheader("Préparer le dossier d'un client avant rendez-vous")

    nom_client = st.text_input("Nom du client")

    if st.button("📋 Préparer le dossier", type="primary", disabled=not nom_client):
        with st.spinner("Préparation en cours..."):
            preparer_dossier_client(nom_client)

        dossier_preparation = Path(DOSSIER_PREPARATION)
        dossier_client_prepare = None

        for dossier in dossier_preparation.iterdir() if dossier_preparation.exists() else []:
            if dossier.is_dir() and nom_client.lower() in dossier.name.lower():
                dossier_client_prepare = dossier
                break

        if dossier_client_prepare:
            fichier_resume = dossier_client_prepare / "RESUME.txt"
            if fichier_resume.exists():
                st.success(f"Dossier préparé : {dossier_client_prepare}")
                st.markdown("### 📄 Résumé")
                st.write(fichier_resume.read_text(encoding="utf-8"))
            else:
                st.warning("Dossier préparé, mais aucun résumé trouvé.")
        else:
            st.error(f"Aucun dossier trouvé pour '{nom_client}'. Vérifie l'orthographe.")