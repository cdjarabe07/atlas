import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import shutil
from pathlib import Path
from unittest.mock import patch
import main


def nettoyer_dossiers_test(dossier_source, dossier_destination):
    """Supprime les dossiers de test s'ils existent, pour repartir propre"""
    if dossier_source.exists():
        shutil.rmtree(dossier_source)
    if dossier_destination.exists():
        shutil.rmtree(dossier_destination)
    dossier_source.mkdir()


def test_deux_clients_identiques_vont_dans_le_meme_dossier():
    """Vérifie que 'Martin Dupont' et 'M. Martin DUPONT' finissent dans le même dossier"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    (dossier_source / "doc1.txt").write_text("Contrat - Client Martin Dupont", encoding="utf-8")
    (dossier_source / "doc2.txt").write_text("Facture - Client M. Martin DUPONT", encoding="utf-8")

    # On simule les réponses de l'IA pour ne pas dépendre d'Ollama dans ce test
    reponses_simulees = ["Martin Dupont", "M. Martin DUPONT"]

    with patch("main.identifier_client", side_effect=reponses_simulees):
        main.DOSSIER_SOURCE = str(dossier_source)
        main.DOSSIER_DESTINATION = str(dossier_destination)
        main.classer_documents()

    dossiers_crees = [d.name for d in dossier_destination.iterdir() if d.is_dir()]

    assert len(dossiers_crees) == 1, f"Attendu 1 seul dossier, trouvé : {dossiers_crees}"

    nettoyer_dossiers_test(dossier_source, dossier_destination)
    shutil.rmtree(dossier_destination, ignore_errors=True)


def test_fichier_vide_est_ignore():
    """Vérifie qu'un fichier vide n'est pas classé et ne fait pas planter le programme"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    (dossier_source / "vide.txt").write_text("", encoding="utf-8")

    main.DOSSIER_SOURCE = str(dossier_source)
    main.DOSSIER_DESTINATION = str(dossier_destination)
    main.classer_documents()

    dossiers_crees = list(dossier_destination.iterdir()) if dossier_destination.exists() else []

    assert len(dossiers_crees) == 0, "Un fichier vide n'aurait pas dû créer de dossier client"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)


def test_client_inconnu_nest_pas_classe():
    """Vérifie qu'un document sans client identifiable reste de côté"""
    dossier_source = Path("test_source_temp")
    dossier_destination = Path("test_destination_temp")
    nettoyer_dossiers_test(dossier_source, dossier_destination)

    (dossier_source / "note.txt").write_text("Note interne sans client précis.", encoding="utf-8")

    with patch("main.identifier_client", return_value="INCONNU"):
        main.DOSSIER_SOURCE = str(dossier_source)
        main.DOSSIER_DESTINATION = str(dossier_destination)
        main.classer_documents()

    dossiers_crees = list(dossier_destination.iterdir()) if dossier_destination.exists() else []

    assert len(dossiers_crees) == 0, "Un client INCONNU n'aurait pas dû créer de dossier"

    shutil.rmtree(dossier_source, ignore_errors=True)
    shutil.rmtree(dossier_destination, ignore_errors=True)