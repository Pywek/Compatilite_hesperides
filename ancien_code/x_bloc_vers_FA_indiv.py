import os
import json
from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter
from dotenv import load_dotenv

# Charger les variables depuis le fichier .env
load_dotenv()

# Récupérer la clé API
GENAI_KEY = os.getenv("GENAI_KEY")

# ----------------------------------------------------------------------
## Fonction d'Analyse par Gemini
# ----------------------------------------------------------------------

def analyser_et_separer_factures(chemin_pdf: str, nom_modele: str = 'gemini-2.5-flash'):
    """
    Analyse un fichier PDF contenant potentiellement plusieurs factures
    et utilise Gemini pour identifier les informations clés, y compris les
    numéros de page de début et de fin de chaque facture.

    :param chemin_pdf: Le chemin d'accès au fichier PDF multi-factures.
    :param nom_modele: Le modèle Gemini à utiliser.
    :return: Une liste des informations de facture identifiées, ou None en cas d'erreur.
    """
    print(f"Chargement du fichier PDF : {chemin_pdf}...")
    
    # --- 1. Initialisation de l'API ---
    try:
        client = genai.Client(api_key=GENAI_KEY)
        print("Client Gemini initialisé avec succès.")
    except Exception as e:
        print(f"Erreur d'initialisation du client Gemini. Erreur: {e}")
        return None

    # 2. Vérification et lecture du nombre de pages
    try:
        reader = PdfReader(chemin_pdf)
        nombre_pages = len(reader.pages)
        print(f"Le document contient {nombre_pages} pages.")
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier PDF : {e}")
        return None

    # --- 3. Définition du Schéma de Réponse (Structure JSON attendue) ---
    # AJOUT : 'nom_fournisseur' pour nommer le fichier
    facture_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "nom_fournisseur": types.Schema(type=types.Type.STRING, description="Le nom de l'entreprise ou du fournisseur qui a émis la facture."), 
            "numero_facture": types.Schema(type=types.Type.STRING, description="Le numéro unique de la facture."),
            "page_debut": types.Schema(type=types.Type.INTEGER, description="Le numéro de la première page de cette facture (base 1)."),
            "page_fin": types.Schema(type=types.Type.INTEGER, description="Le numéro de la dernière page de cette facture (base 1)."),
            "montant_total": types.Schema(type=types.Type.STRING, description="Le montant total de la facture, y compris la devise.")
        },
        required=["nom_fournisseur", "numero_facture", "page_debut", "page_fin"] 
    )

    liste_factures_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "factures": types.Schema(
                type=types.Type.ARRAY,
                items=facture_schema,
                description="Une liste de toutes les factures identifiées dans le document."
            )
        },
        required=["factures"]
    )
    
    # --- 4. Création de l'Instruction (Prompt) ---
    prompt = f"""
    Le fichier PDF fourni contient potentiellement plusieurs factures.
    Votre tâche est d'analyser l'intégralité du document (pages 1 à {nombre_pages})
    et d'identifier chaque facture distincte. Pour chaque facture, vous devez extraire :
    1. Le nom du fournisseur (nom_fournisseur).
    2. Son numéro unique (numero_facture).
    3. La première page où elle commence (page_debut, base 1).
    4. La dernière page où elle se termine (page_fin, base 1).
    5. Le montant total.
    
    Retournez la liste de toutes les factures identifiées dans le format JSON spécifié.
    """

    # --- 5. Envoi à l'API Gemini ---
    fichier_media = None # Initialisation pour le bloc finally
    try:
        # Upload du fichier pour l'analyse
        fichier_media = client.files.upload(file=chemin_pdf)
        print(f"Fichier téléversé : {fichier_media.name}")
        
        # Appel à l'API
        response = client.models.generate_content(
            model=nom_modele,
            contents=[prompt, fichier_media],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=liste_factures_schema,
            ),
        )

        # Traitement de la Réponse
        resultats = json.loads(response.text)
        return resultats.get("factures", [])
        
    except Exception as e:
        print(f"Une erreur est survenue lors de l'appel à l'API Gemini : {e}")
        return None
    finally:
        # Suppression du fichier téléversé après utilisation (même en cas d'erreur)
        if fichier_media:
            client.files.delete(name=fichier_media.name)
            print("Fichier téléversé supprimé.")


# ----------------------------------------------------------------------
## Fonction d'Extraction Physique
# ----------------------------------------------------------------------

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
            nom_fournisseur_nettoye = "".join(c for c in nom_fournisseur if c.isalnum() or c in (' ', '_')).replace(' ', '_')
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
    

# ----------------------------------------------------------------------
## Bloc Principal d'Exécution
# ----------------------------------------------------------------------

if __name__ == "__main__":

    liste_noms_factures = []

    # CHEMIN 
    dossier_test_factures = 'test_factures'
    fichiers_a_analyser = [os.path.join(dossier_test_factures, f) for f in os.listdir(dossier_test_factures) if f.endswith('.pdf')]

    for fichier_a_analyser in fichiers_a_analyser:
        if os.path.exists(fichier_a_analyser):
            print("\n--- 1. Démarrage de l'Analyse par Gemini ---")
            resultats_factures = analyser_et_separer_factures(fichier_a_analyser)

            if resultats_factures:
                print("\n--- 2. Résultats de l'Analyse ---")
                for i, facture in enumerate(resultats_factures):
                    print(f"Facture {i+1}: {facture.get('nom_fournisseur', 'N/A')} - {facture['numero_facture']} (Pages {facture['page_debut']} à {facture['page_fin']})")
                    liste_noms_factures.append(facture.get('nom_fournisseur', 'N/A'))

                # APPEL À LA FONCTION D'EXTRACTION
                chemins_fichiers = extraire_factures_pdf(fichier_a_analyser, resultats_factures)
                
                if chemins_fichiers:
                    print(f"\n✅ Succès : {len(chemins_fichiers)} factures PDF individuelles ont été créées dans le dossier 'factures_separees'.")
                else:
                    print("\n❌ Échec de la création des fichiers PDF individuels.")
                    
            else:
                print("\nAnalyse échouée ou aucune facture n'a été identifiée pour l'extraction.")
        else:
            print(f"\nERREUR: Le fichier à analyser '{fichier_a_analyser}' n'a pas été trouvé. Veuillez vérifier le chemin d'accès.")

    # liste des fournisseurs
    # print(liste_noms_factures)
