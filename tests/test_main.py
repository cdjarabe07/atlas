import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import shutil
from pathlib import Path
from unittest.mock import patch
from docx import Document
from fpdf import FPDF
import main


def nettoyer_dossiers_test(dossier_source, dossier_destination):
    """Supprime les dossiers de test s'ils existent, pour repartir propre"""
    if dossier_source.exists():
        shutil.rmtree(dossier_source)
    if dossier_destination.exists():
        shutil.rmtree(dossier_destination)
    dossier_source.mkdir()


def test_deux_clients_identiques_vont_dans_le_meme_dossier():
    """Verifie que 'Martin Dupont' et 'M. Martin DUPONT' finissent dans le meme dossier"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    (dossier_source / "doc1.txt").write_text("Contrat - Client Martin Dupont", encoding="utf-8")
    (dossier_source / "doc2.txt").write_text("Facture - Client M. Martin DUPONT", encoding="utf-8")

    reponses_simulees = ["Martin Dupont", "M. Martin DUPONT"]

    with patch("main.identifier_client", side_effect=reponses_simulees):
        main.DOSSIER_SOURCE = str(dossier_source)
        main.DOSSIER_DESTINATION = str(dossier_destination)
        main.classer_documents()

    dossiers_crees = [d.name for d in dossier_destination.iterdir() if d.is_dir()]

    assert len(dossiers_crees) == 1, f"Attendu 1 seul dossier, trouve : {dossiers_crees}"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)


def test_fichier_vide_est_ignore():
    """Verifie qu'un fichier vide n'est pas classe et ne fait pas planter le programme"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    (dossier_source / "vide.txt").write_text("", encoding="utf-8")

    main.DOSSIER_SOURCE = str(dossier_source)
    main.DOSSIER_DESTINATION = str(dossier_destination)
    main.classer_documents()

    dossiers_crees = list(dossier_destination.iterdir()) if dossier_destination.exists() else []

    assert len(dossiers_crees) == 0, "Un fichier vide n'aurait pas du creer de dossier client"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)


def test_client_inconnu_nest_pas_classe():
    """Verifie qu'un document sans client identifiable reste de cote"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    (dossier_source / "note.txt").write_text("Note interne sans client precis.", encoding="utf-8")

    with patch("main.identifier_client", return_value="INCONNU"):
        main.DOSSIER_SOURCE = str(dossier_source)
        main.DOSSIER_DESTINATION = str(dossier_destination)
        main.classer_documents()

    dossiers_crees = list(dossier_destination.iterdir()) if dossier_destination.exists() else []

    assert len(dossiers_crees) == 0, "Un client INCONNU n'aurait pas du creer de dossier"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)


def test_document_word_est_lu_et_classe():
    """Verifie qu'un vrai fichier .docx est correctement lu et classe"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    doc = Document()
    doc.add_paragraph("Convention d'honoraires pour Julien Fabre")
    doc.save(str(dossier_source / "test.docx"))

    with patch("main.identifier_client", return_value="Julien Fabre"):
        main.DOSSIER_SOURCE = str(dossier_source)
        main.DOSSIER_DESTINATION = str(dossier_destination)
        main.classer_documents()

    dossiers_crees = [d.name for d in dossier_destination.iterdir() if d.is_dir()]

    assert "Julien Fabre" in dossiers_crees, f"Dossier Julien Fabre non trouve : {dossiers_crees}"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)


def test_document_pdf_est_lu_et_classe():
    """Verifie qu'un vrai fichier .pdf est correctement lu et classe"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Assignation pour Claire Moreau")
    pdf.output(str(dossier_source / "test.pdf"))

    with patch("main.identifier_client", return_value="Claire Moreau"):
        main.DOSSIER_SOURCE = str(dossier_source)
        main.DOSSIER_DESTINATION = str(dossier_destination)
        main.classer_documents()

    dossiers_crees = [d.name for d in dossier_destination.iterdir() if d.is_dir()]

    assert "Claire Moreau" in dossiers_crees, f"Dossier Claire Moreau non trouve : {dossiers_crees}"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)