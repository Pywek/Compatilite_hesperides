import os
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import BytesIO
import platform
import subprocess


def extraire_factures_pdf(chemin_pdf_source: str, resultats_factures: list, dossier_sortie: str = "factures_separees"):
    """
    Sépare le fichier PDF source en plusieurs fichiers basés sur les informations
    d'identification fournies par l'API Gemini.

    :param chemin_pdf_source: Le chemin d'accès au fichier PDF original.
    :param resultats_factures: Liste des dictionnaires d'informations de facture.
    :param dossier_sortie: Le nom du dossier où enregistrer les nouvelles factures.
    :return: Une liste des chemins d'accès aux fichiers PDF créés.
    """
    if not resultats_factures:
        print("Aucune information de facture fournie pour l'extraction.")
        return []

    # Créer le dossier de sortie s'il n'existe pas
    os.makedirs(dossier_sortie, exist_ok=True)
    fichiers_crees = []

    try:
        reader = PdfReader(chemin_pdf_source)
        
        print(f"\n--- Démarrage de l'extraction physique dans le dossier '{dossier_sortie}' ---")

        for facture in resultats_factures:
            nom_fournisseur = facture.get('nom_fournisseur', 'Fournisseur_Inconnu')
            num_facture = facture['numero_facture']
            
            # Conversion des pages (base 1) en index (base 0)
            start_page_index = facture['page_debut'] - 1
            end_page_index = facture['page_fin']

            writer = PdfWriter()

            # CORRECTION APPLIQUÉE : Itération pour utiliser writer.add_page()
            pages_a_ajouter = reader.pages[start_page_index:end_page_index]
            for page in pages_a_ajouter:
                 writer.add_page(page)
            
            # Nom du fichier de sortie : Utilisation du nom du fournisseur
            # Nettoyage des caractères spéciaux pour un nom de fichier valide
            nom_fournisseur_nettoye = "".join(c for c in nom_fournisseur if c.isalnum() or c in (' ', '_'))
            num_facture_nettoye = "".join(c for c in num_facture if c.isalnum() or c in ('-', '_'))

            nom_fichier_sortie = os.path.join(
                dossier_sortie, 
                f"{nom_fournisseur_nettoye}_{num_facture_nettoye}.pdf"
            )
            
            # Écriture du nouveau fichier PDF
            with open(nom_fichier_sortie, "wb") as output_stream:
                writer.write(output_stream)
            
            fichiers_crees.append(nom_fichier_sortie)
            print(f"  -> Facture extraite : {nom_fichier_sortie} (Pages {facture['page_debut']}-{facture['page_fin']})")
        
        return fichiers_crees
        
    except Exception as e:
        print(f"Erreur lors de l'extraction des pages : {e}")
        return []


def creation_texte_rouge(fournisseur: str, comptes: list, chiffres: list):
    texte_rouge = " " + fournisseur.upper() + "\n"
    for compte, chiffre in zip(comptes, chiffres):
        texte_rouge += f" - {compte[0]} : {chiffre}\n"
    return texte_rouge


def ajouter_texte_rouge(input_pdf: str, texte_rouge: str) -> float:
    """
    Ajoute ou met à jour une zone de texte rouge fixe dans le coin supérieur gauche d’un PDF.

    - Le fond blanc commence pile au coin supérieur gauche (recouvre toute ancienne annotation).
    - Le texte rouge reste lisible légèrement plus bas (position stable).
    - Si la fonction est appelée plusieurs fois sur le même PDF, la nouvelle version
      recouvre la précédente (grâce au fond blanc redessiné par-dessus).
    - Le fichier source est modifié directement (aucun nouveau fichier créé).

    Args:
        input_pdf (str): Chemin du fichier PDF à annoter (sera écrasé).
        texte_rouge (str): Texte à écrire en rouge (peut contenir des retours à la ligne).

    Returns:
        float: Position verticale (y) après le texte rouge (utile pour positionner un autre texte dessous).
    """

    # --- Lecture du PDF (sans fermer le flux avant fusion) ---
    f = open(input_pdf, "rb")
    reader = PdfReader(f)
    page = reader.pages[0]

    largeur = float(page.mediabox.width)
    hauteur = float(page.mediabox.height)

    # --- Paramètres visuels ---
    police = ("Helvetica", 12)
    espace_ligne = 14
    padding_x = 8
    padding_y = 4
    x_texte = 10
    y_top = hauteur - 20  # position du texte rouge

    # --- Calcul de la hauteur du texte ---
    lignes = texte_rouge.split("\n")
    hauteur_texte = len(lignes) * espace_ligne
    hauteur_totale = hauteur_texte + (padding_y * 1.5)
    largeur_zone = largeur / 2.5

    # --- Création du calque temporaire ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(largeur, hauteur))

    # Fond blanc opaque : recouvre tout ce qui était à cet emplacement
    can.setFillColorRGB(1, 1, 1)
    can.rect(
        0, hauteur - hauteur_totale,  # coin supérieur gauche
        largeur_zone + padding_x,
        hauteur_totale,
        fill=1, stroke=0
    )

    # Texte rouge
    can.setFont(*police)
    can.setFillColorRGB(1, 0, 0)
    y = y_top
    for ligne in lignes:
        can.drawString(x_texte, y, ligne)
        y -= espace_ligne

    can.save()

    # --- Fusion du calque ---
    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    page.merge_page(overlay_pdf.pages[0])

    # --- Sauvegarde dans le même fichier ---
    writer = PdfWriter()
    writer.add_page(page)
    with open(input_pdf, "wb") as f_out:
        writer.write(f_out)

    # On ferme le fichier d’entrée à la fin seulement
    f.close()

    print(f"✅ Zone rouge mise à jour dans {input_pdf}")


def validation_imputation(texte_rouge: str = "") -> tuple[str, str]:
    """
    Demande à l'utilisateur de choisir un type d'imputation et génère le texte associé.

    Paramètres :
        texte_rouge (str, optionnel) :
            Texte rouge déjà défini en amont. Utilisé uniquement si l'utilisateur
            choisit l'option 6 (réécriture manuelle). Par défaut : chaîne vide.

    Options disponibles :
        1. BAP
        2. Prélèvement
        3. CB
        4. Chèque → saisie du numéro de chèque
        5. Commentaire libre → saisie manuelle
        6. Réécriture manuelle → saisie du texte rouge et du texte noir

    Retourne :
        tuple[str, str] :
            - texte_rouge : texte rouge éventuellement mis à jour
            - texte_noir : texte généré ou saisi selon le choix utilisateur 
    """
    texte_noir = ""

    while True:
        choix = input(
            "\nChoisissez une option :\n"
            "  1. BAP\n"
            "  2. Prélèvement\n"
            "  3. CB\n"
            "  4. Chèque (numéro)\n"
            "  5. Commentaire libre\n"
            "  6. Réécriture manuelle\n"
            "Votre choix : "
        ).strip()

        if choix in {"1", "2", "3", "4", "5", "6"}:
            break
        else:
            print("⚠️ Veuillez choisir une option valide (1 à 6).")

    if choix == "1":
        texte_noir = "BAP"
    elif choix == "2":
        texte_noir = "Prélèvement"
    elif choix == "3":
        texte_noir = "CB"
    elif choix == "4":
        num_cheque = input("Entrez le numéro du chèque : ").strip()
        texte_noir = f"Chèque n° : {num_cheque}"
    elif choix == "5":
        texte_noir = input("Entrez le commentaire libre : ").strip()
    elif choix == "6":
        # print("\n--- Saisie du texte rouge ---")
        # print("Appuyez sur Entrée sans rien écrire pour terminer.\n")

        lignes = []
        lignes.append(input("Nom du fournisseur : ").strip())
        lignes.append(" - " + input("Première imputation : ").strip())
        

        # Imputations supplémentaires
        while True:
            ligne = " - " + input("Autre imputation (ou Entrée pour arrêter) : ").strip()
            if ligne == " - ":
                break
            lignes.append(ligne)

        texte_rouge = "\n".join(lignes)

        # Texte noir ensuite
        texte_noir = input("\nTexte noir : ").strip()

    # Mise en forme du texte noir
    texte_noir = " -> " + texte_noir

    return texte_rouge, texte_noir


def ajouter_texte_definitif(input_pdf: str, texte_rouge: str, texte_noir: str = None) -> float:
    """
    Ajoute ou met à jour une zone en haut à gauche avec :
      - texte rouge (en haut)
      - texte noir (juste en dessous) optionnel
    Le fond blanc recouvre l'ancienne annotation et s'ajuste à la hauteur totale
    (rouge + noir). Le fichier d'entrée est écrasé.
    
    Gère les fichiers multi-pages en appliquant le texte uniquement sur la première page
    et en conservant toutes les autres pages.

    Args:
        input_pdf: chemin du PDF (sera réécrit).
        texte_rouge: texte (multi-lignes) en rouge.
        texte_noir: texte (multi-lignes) en noir, placé directement sous le rouge.

    Returns:
        float: coordonnée Y du bas du fond blanc (utile si besoin).
    """
    # Lecture (on garde le flux ouvert jusqu'à la réécriture)
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    # --- Paramètres visuels ---
    font_name = "Helvetica" # Retour à la police normale (pas gras)
    font_size = 12
    line_spacing = 14  # Espace entre les lignes
    padding = 5        # Marge interne du fond blanc

    # Calcul des dimensions nécessaires pour le fond blanc
    lignes_rouge = texte_rouge.split('\n') if texte_rouge else []
    lignes_noir = texte_noir.split('\n') if texte_noir else []
    
    # Largeur max (estimation simple : ~7 points par caractère moyen en taille 12)
    max_len_rouge = max([len(l) for l in lignes_rouge]) if lignes_rouge else 0
    max_len_noir = max([len(l) for l in lignes_noir]) if lignes_noir else 0
    max_char = max(max_len_rouge, max_len_noir)
    
    rect_width = (max_char * 7) + (padding * 2)
    rect_height = ((len(lignes_rouge) + len(lignes_noir)) * line_spacing) + (padding * 2)

    # --- Traitement de toutes les pages ---
    for i, page in enumerate(reader.pages):
        if i == 0:
            # --- Page 1 : On ajoute le texte ---
            packet = BytesIO()
            can = canvas.Canvas(packet)
            
            # Récupération des dimensions de la page
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            # Position du coin haut gauche (avec marge)
            x_start = 0 # Collé à gauche comme avant
            y_start = page_height # Collé en haut comme avant (le rectangle se dessine vers le bas)

            # 1. Dessiner le fond blanc
            can.setFillColorRGB(1, 1, 1) # Blanc
            can.setStrokeColorRGB(1, 1, 1)
            # Rectangle (x, y, width, height) - y est le bas du rectangle
            can.rect(x_start, y_start - rect_height, rect_width, rect_height, fill=1, stroke=1)

            # 2. Dessiner le texte
            current_y = y_start - padding - 10 # Première ligne

            # Texte Rouge
            can.setFont(font_name, font_size)
            can.setFillColorRGB(1, 0, 0) # Rouge
            for ligne in lignes_rouge:
                can.drawString(x_start + padding, current_y, ligne)
                current_y -= line_spacing
            
            # Texte Noir
            can.setFillColorRGB(0, 0, 0) # Noir
            for ligne in lignes_noir:
                can.drawString(x_start + padding, current_y, ligne)
                current_y -= line_spacing
            
            can.save()

            # Fusionner le calque avec la page originale
            packet.seek(0)
            overlay_pdf = PdfReader(packet)
            page.merge_page(overlay_pdf.pages[0])
            writer.add_page(page)
        else:
            # --- Autres pages : On copie simplement ---
            writer.add_page(page)

    # Écriture du fichier final
    with open(input_pdf, "wb") as f:
        writer.write(f)
    
    return 0.0 # Retour dummy