import re
import difflib
import ollama
from main import (
    classer_documents, preparer_dossier_client,
    lister_documents_client, renommer_document,
    deplacer_document, supprimer_document, apercu_document
)

MOTS_DE_SORTIE = ["quitter", "exit", "quit", "stop", "sortir"]
SEUIL_SIMILARITE = 0.75


def est_une_demande_de_sortie(instruction):
    """Verifie si l'instruction ressemble a une demande de sortie, meme avec une faute de frappe"""
    instruction_nettoyee = instruction.strip().lower()

    if not instruction_nettoyee:
        return False

    for mot in MOTS_DE_SORTIE:
        similarite = difflib.SequenceMatcher(None, instruction_nettoyee, mot).ratio()
        if similarite >= SEUIL_SIMILARITE:
            return True

    return False


def interpreter_instruction(instruction):
    """Demande au modele local de comprendre l'intention de l'utilisateur"""
    prompt = f"""Tu es un assistant qui controle un programme de gestion documentaire juridique.
Voici les actions possibles :
- classer : classer automatiquement tous les documents du dossier documents_a_trier
- preparer : preparer le dossier d'un client specifique avant un rendez-vous (necessite un nom de client)
- lister : lister les documents d'un client (necessite un nom de client)
- renommer : renommer un document d'un client (necessite nom de client, ancien nom de fichier, nouveau nom)
- deplacer : deplacer un document vers un autre client (necessite nom de document, client source, client destination)
- supprimer : supprimer un document d'un client (necessite nom de client, nom de document)
- apercu : afficher le contenu d'un document specifique (necessite nom de client, nom de document)

Instruction de l'utilisateur : "{instruction}"

Reponds UNIQUEMENT au format suivant, une ligne par champ, sans phrase ni explication.
Laisse un champ vide (juste le prefixe) si non applicable a cette action.

ACTION: <classer, preparer, lister, renommer, deplacer, supprimer, apercu ou inconnu>
CLIENT: <nom du client concerne>
CLIENT_DESTINATION: <nom du client destination, uniquement pour deplacer>
DOCUMENT: <nom du fichier concerne, si applicable>
NOUVEAU_NOM: <nouveau nom de fichier, uniquement pour renommer>
"""

    reponse = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1}
    )

    texte_reponse = reponse["message"]["content"].strip()

    def extraire_champ(nom_champ):
        match = re.search(rf"{nom_champ}:\s*(.*)", texte_reponse, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    action_brute = extraire_champ("ACTION").lower()
    actions_valides = ["classer", "preparer", "lister", "renommer", "deplacer", "supprimer", "apercu"]
    action = next((a for a in actions_valides if a in action_brute), "inconnu")

    return {
        "action": action,
        "client": extraire_champ("CLIENT"),
        "client_destination": extraire_champ("CLIENT_DESTINATION"),
        "document": extraire_champ("DOCUMENT"),
        "nouveau_nom": extraire_champ("NOUVEAU_NOM"),
    }


def executer_action(details):
    action = details["action"]

    if action == "classer":
        print("→ Lancement du classement des documents...\n")
        classer_documents()

    elif action == "preparer":
        if not details["client"]:
            print("Je n'ai pas compris pour quel client préparer le dossier.")
        else:
            preparer_dossier_client(details["client"])

    elif action == "lister":
        if not details["client"]:
            print("Je n'ai pas compris de quel client tu parles.")
        else:
            lister_documents_client(details["client"])

    elif action == "renommer":
        if not details["client"] or not details["document"] or not details["nouveau_nom"]:
            print("Il me manque des informations pour renommer (client, document actuel, et nouveau nom).")
        else:
            renommer_document(details["client"], details["document"], details["nouveau_nom"])

    elif action == "deplacer":
        if not details["client"] or not details["document"] or not details["client_destination"]:
            print("Il me manque des informations pour déplacer (document, client source, client destination).")
        else:
            deplacer_document(details["document"], details["client"], details["client_destination"])

    elif action == "supprimer":
        if not details["client"] or not details["document"]:
            print("Il me manque des informations pour supprimer (client et nom du document).")
        else:
            confirmation = input(
                f"⚠️ Confirmer la suppression de '{details['document']}' "
                f"du dossier de {details['client']} ? (oui/non) : "
            )
            if confirmation.strip().lower() in ["oui", "o", "yes", "y"]:
                supprimer_document(details["client"], details["document"])
            else:
                print("Suppression annulée.")

    elif action == "apercu":
        if not details["client"] or not details["document"]:
            print("Il me manque des informations pour l'aperçu (client et nom du document).")
        else:
            apercu_document(details["client"], details["document"])

    else:
        print("Je n'ai pas compris cette instruction.")


def main():
    print("Atlas est prêt. Que veux-tu faire ?")
    print("(tape 'quitter' pour sortir)\n")

    while True:
        instruction = input("> ")

        if est_une_demande_de_sortie(instruction):
            print("À bientôt.")
            break

        details = interpreter_instruction(instruction)
        executer_action(details)
        print()


if __name__ == "__main__":
    main()