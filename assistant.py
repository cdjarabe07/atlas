import ollama
from main import classer_documents

def interpreter_instruction(instruction):
    """Demande au modèle local de comprendre l'intention de l'utilisateur"""
    prompt = f"""Tu es un assistant qui contrôle un programme de classement de documents juridiques.
Voici les actions possibles :
- classer : classer automatiquement tous les documents du dossier documents_a_trier

Instruction de l'utilisateur : "{instruction}"

Réponds UNIQUEMENT avec un seul mot, sans guillemets, sans ponctuation, sans phrase :
classer
ou
inconnu
"""

    reponse = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}]
    )

    action_brute = reponse["message"]["content"].strip().lower()

    # Nettoyage : on enlève guillemets, points, espaces superflus
    action_nettoyee = action_brute.strip('."\'` \n')

    # On vérifie si "classer" est présent dans la réponse, plutôt qu'une égalité stricte
    if "classer" in action_nettoyee:
        return "classer"
    else:
        return "inconnu"


def executer_action(action):
    if action == "classer":
        print("→ Lancement du classement des documents...\n")
        classer_documents()
    else:
        print(f"Je n'ai pas compris cette instruction (action détectée : '{action}').")


def main():
    print("Atlas est prêt. Que veux-tu faire ?")
    print("(tape 'quitter' pour sortir)\n")

    while True:
        instruction = input("> ")

        if instruction.lower() in ["quitter", "exit", "quit"]:
            print("À bientôt.")
            break

        action = interpreter_instruction(instruction)
        executer_action(action)
        print()


if __name__ == "__main__":
    main()