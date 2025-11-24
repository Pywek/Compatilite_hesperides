import os
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
import json
import time
import ast


def initialisation_client_gemini():
    """
    Initialise et retourne un client Gemini (API Google Generative AI).

    Cette fonction :
    - Charge les variables d'environnement depuis le fichier `.env`.
    - Récupère la clé API `GENAI_KEY`.
    - Crée une instance du client `genai.Client` pour interagir avec l'API Gemini.

    En cas de succès :
        → Retourne l'objet client initialisé.
    En cas d'échec :
        → Retourne `None` et affiche un message d'erreur.

    Returns:
        genai.Client | None: Instance du client Gemini ou None si l'initialisation échoue.
    """
    # Charger les variables depuis le fichier .env
    load_dotenv()

    # Récupérer la clé API
    GENAI_KEY = os.getenv("GENAI_KEY")

    # Initialisation de l'API
    try:
        client = genai.Client(api_key=GENAI_KEY)
        print("Client Gemini initialisé avec succès.")
        return client
    except Exception as e:
        print(f"Erreur d'initialisation du client Gemini. Erreur: {e}")
        return None
    

def get_infos_facture(pdf_path: str, client: genai.Client) -> tuple:
    """
    Analyse un fichier PDF de facture avec Gemini afin d'extraire le nom du fournisseur et la date.

    Retourne:
        tuple: (nom_fournisseur, date_facture) ou (None, None) en cas d'erreur.
    """
    pdf_file = None
    try:
        print(f"⏳ Téléchargement du fichier PDF ({pdf_path}) dans le service Gemini...")
        pdf_file = client.files.upload(file=pdf_path)
        
        while pdf_file.state != 'ACTIVE':
            if pdf_file.state != 'PROCESSING':
                 raise RuntimeError(f"Le traitement du fichier a échoué. État actuel : {pdf_file.state}")
            time.sleep(1)
            pdf_file = client.files.get(name=pdf_file.name)
        
        prompt = (
            "À partir de cette facture, extrais :\n"
            "1. Le nom complet du fournisseur.\n"
            "2. La date de la facture (format JJ/MM/AAAA).\n"
            "Renvoie UNIQUEMENT un tuple Python : ('Nom Fournisseur', 'JJ/MM/AAAA')."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, pdf_file]
        )
        
        texte = response.text.strip()
        try:
            resultat = ast.literal_eval(texte)
            if isinstance(resultat, tuple) and len(resultat) == 2:
                return resultat
            return (texte, "Date Inconnue") # Fallback si le format n'est pas respecté
        except:
            return (texte, "Date Inconnue")

    except Exception as e:
        print(f"Erreur Gemini: {e}")
        return (None, None)
        
    finally:
        if pdf_file:
             client.files.delete(name=pdf_file.name)


def analyser_et_separer_factures(chemin_pdf: str, client: genai.Client, nom_modele: str = 'gemini-2.5-flash'):
    """
    Analyse un fichier PDF contenant potentiellement plusieurs factures
    et utilise Gemini pour identifier les informations clés, y compris les
    numéros de page de début et de fin de chaque facture.

    :param chemin_pdf: Le chemin d'accès au fichier PDF multi-factures.
    :param nom_modele: Le modèle Gemini à utiliser.
    :return: Une liste des informations de facture identifiées, ou None en cas d'erreur.
    """
    print(f"Chargement du fichier PDF : {chemin_pdf}...")
    
   

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



def application_regle_imputation(pdf_path: str, client: genai.Client, regles_imputation: list) -> tuple:
    """
    Analyse un fichier PDF de facture avec Gemini afin d'extraire des informations selon les règles d'imputation.
    Retourne un tuple contenant les résultats.
    """
    
    pdf_file = None
    try:
        print(f"⏳ Téléchargement du fichier PDF ({pdf_path}) dans le service Gemini...")
        pdf_file = client.files.upload(file=pdf_path)
        print(f"   Fichier téléversé : {pdf_file.name}")

        # Attente de l'état ACTIF
        while pdf_file.state != 'ACTIVE':
            if pdf_file.state != 'PROCESSING':
                raise RuntimeError(f"Le traitement du fichier a échoué. État actuel : {pdf_file.state}")
            print(f"   État du fichier : {pdf_file.state}. Attente de 2 secondes...")
            time.sleep(2)
            pdf_file = client.files.get(name=pdf_file.name)
        
        print("✅ Le fichier est maintenant ACTIF et prêt à être utilisé.")

        # Préparation du prompt
        regles = [r[1] for r in regles_imputation]
        prompt = (
            f"A partir du fichier pdf joint, renvoie moi les données suivantes dans un tuple :\n"
            f"{regles}\n"
            f"Donne moi UNIQUEMENT le tuple Python au format (résultat1, résultat2, ...)"
        )

        print("⏳ Envoi de la demande d'analyse...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, pdf_file]
        )

        print("✅ Réponse reçue de Gemini.")
        texte_reponse = response.text.strip()
        print(f"🔍 Texte brut reçu : {texte_reponse}")

        # Conversion sécurisée du str en tuple
        try:
            resultat_tuple = ast.literal_eval(texte_reponse)
            if not isinstance(resultat_tuple, tuple):
                raise ValueError("La réponse n'est pas un tuple valide.")
            return resultat_tuple
        except (SyntaxError, ValueError) as e:
            raise RuntimeError(f"Format de tuple invalide renvoyé par Gemini : {texte_reponse} ({e})")

    except APIError as e:
        return f"Erreur API Gemini : {e}"
    except RuntimeError as e:
        return f"Erreur de traitement du fichier : {e}"
    except Exception as e:
        return f"Une erreur inattendue s'est produite : {e}"
    finally:
        if pdf_file:
            print(f"🗑️ Suppression du fichier temporaire : {pdf_file.name}")
            client.files.delete(name=pdf_file.name)


def application_regle_imputation_V2(pdf_path: str, client: genai.Client, regles_imputation: list) -> tuple:
    """
    Analyse un fichier PDF de facture avec Gemini sans upload.
    Envoie le PDF directement en mémoire pour extraire les données selon les règles d'imputation.
    Retourne un tuple contenant les résultats.
    """
    try:
        # Lecture du fichier PDF en mémoire
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        print(f"📄 Fichier PDF chargé en mémoire : {pdf_path} ({len(pdf_bytes)} octets)")

        # Préparation du prompt
        regles = [r[1] for r in regles_imputation]
        prompt = (
            f"À partir du fichier PDF joint, renvoie-moi les données suivantes dans un tuple Python :\n"
            f"{regles}\n"
            f"Donne-moi UNIQUEMENT le tuple au format (résultat1, résultat2, ...)"
        )

        # Envoi direct du PDF au modèle Gemini (sans upload)
        print("⏳ Envoi du PDF au modèle Gemini...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "application/pdf", "data": pdf_bytes}},
                    ],
                }
            ],
        )

        print("✅ Réponse reçue de Gemini.")
        texte_reponse = response.text.strip()
        print(f"🔍 Texte brut reçu : {texte_reponse}")

        # Conversion sécurisée du texte en tuple Python
        try:
            resultat_tuple = ast.literal_eval(texte_reponse)
            if not isinstance(resultat_tuple, tuple):
                raise ValueError("La réponse n'est pas un tuple valide.")
            return resultat_tuple

        except (SyntaxError, ValueError) as e:
            raise RuntimeError(f"Format de tuple invalide renvoyé par Gemini : {texte_reponse} ({e})")

    except Exception as e:
        return f"❌ Erreur inattendue : {e}"

















