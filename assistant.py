import re
import ollama
from main import classer_documents, preparer_dossier_client

def interpreter_instruction(instruction):
    """Demande au modele local de comprendre l'intention de l'utilisateur"""
    prompt = f"""Tu es un assistant qui controle un programme de gestion documentaire juridique.
Voici les actions possibles :
- classer : classer automatiquement tous les documents du dossier documents_a_trier
- preparer : preparer le dossier d'un client specifique avant un rendez-vous (necessite un nom de client)

Instruction de l'utilisateur : "{instruction}"

Reponds UNIQUEMENT au format suivant, sans phrase ni explication :
ACTION: <classer ou preparer ou inconnu>
CLIENT: <nom du client si action=preparer, sinon laisser vide>
"""

    reponse = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}]
    )

    texte_reponse = reponse["message"]["content"].strip()

    action_match = re.search(r"ACTION:\s*(\w+)", texte_reponse, re.IGNORECASE)
    client_match = re.search(r"CLIENT:\s*(.*)", texte_reponse, re.IGNORECASE)

    action = action_match.group(1).lower() if action_match else "inconnu"
    client = client_match.group(1).strip() if client_match else ""

    if "classer" in action:
        action = "classer"
    elif "preparer" in action:
        action = "preparer"
    else:
        action = "inconnu"

    return action, client


def executer_action(action, client):
    if action == "classer":
        print("→ Lancement du classement des documents...\n")
        classer_documents()
    elif action == "preparer":
        if not client:
            print("Je n'ai pas compris pour quel client preparer le dossier.")
        else:
            preparer_dossier_client(client)
    else:
        print(f"Je n'ai pas compris cette instruction.")


def main():
    print("Atlas est pret. Que veux-tu faire ?")
    print("(tape 'quitter' pour sortir)\n")

    while True:
        instruction = input("> ")

        if instruction.lower() in ["quitter", "exit", "quit"]:
            print("A bientot.")
            break

        action, client = interpreter_instruction(instruction)
        executer_action(action, client)
        print()


if __name__ == "__main__":
    main()