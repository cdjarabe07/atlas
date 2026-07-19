from pathlib import Path
from docx import Document
from fpdf import FPDF

DOSSIER_SOURCE = Path("documents_a_trier")
DOSSIER_SOURCE.mkdir(exist_ok=True)


def creer_docx_test():
    """Cree un vrai fichier .docx avec du contenu client"""
    doc = Document()
    doc.add_paragraph("Convention d'honoraires")
    doc.add_paragraph("Pour le compte de notre client, Monsieur Julien Fabre,")
    doc.add_paragraph("concernant un litige commercial avec son fournisseur.")

    chemin = DOSSIER_SOURCE / "test_word.docx"
    doc.save(str(chemin))
    print(f"Cree : {chemin}")


def creer_pdf_test():
    """Cree un vrai fichier .pdf avec du contenu client"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Assignation en justice\n\nAffaire concernant notre cliente, Madame Claire Moreau,\ndans le cadre d'un litige de copropriete.")

    chemin = DOSSIER_SOURCE / "test_pdf.pdf"
    pdf.output(str(chemin))
    print(f"Cree : {chemin}")


if __name__ == "__main__":
    creer_docx_test()
    creer_pdf_test()