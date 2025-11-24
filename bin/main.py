from src.utils import *
from src.appels_ia import *
from src.pdf_manager import *
from src.gestion_bdd import *

import os


# CHEMINS
dossier_import = 'data\\input'
dossier_sortie = 'data\\output'

# VARIABLES GLOBALES ET CONSTANTES
liste_noms_factures = []
DB_FILE = get_path("data", "Comptabilité.db")


# PROGRAMME PRINCIPAL

# region 1. Verification de la disponibilité de la base de données et initialisation du client Gemini
status_bdd = bdd_est_disponible(DB_FILE)
client = initialisation_client_gemini()
if client is None or status_bdd == False:
    input("\nAppuyez sur Entrée pour fermer le programme...")
    exit()
# endregion


# # region 2. Séparation d'un bloc PDF en plusieurs factures
# fichiers_a_analyser = [os.path.join(dossier_import, f) for f in os.listdir(dossier_import) if f.endswith('.pdf')]
# for fichier_a_analyser in fichiers_a_analyser:
#     if os.path.exists(fichier_a_analyser):
#         print("\n--- 1. Démarrage de l'Analyse par Gemini ---")
#         resultats_factures = analyser_et_separer_factures(fichier_a_analyser, client)

#         if resultats_factures:
#             print("\n--- 2. Résultats de l'Analyse ---")
#             for i, facture in enumerate(resultats_factures):
#                 print(f"Facture {i+1}: {facture.get('nom_fournisseur', 'N/A')} - {facture['numero_facture']} (Pages {facture['page_debut']} à {facture['page_fin']})")
#                 liste_noms_factures.append(facture.get('nom_fournisseur', 'N/A'))

#             # APPEL À LA FONCTION D'EXTRACTION
#             chemins_fichiers = extraire_factures_pdf(fichier_a_analyser, resultats_factures, dossier_sortie)
            
#             if chemins_fichiers:
#                 print(f"\n✅ Succès : {len(chemins_fichiers)} factures PDF individuelles ont été créées dans le dossier '{dossier_sortie}'.")
#             else:
#                 print("\n❌ Échec de la création des fichiers PDF individuels.")
#         else:
#             print("\nAnalyse échouée ou aucune facture n'a été identifiée pour l'extraction.")
#     else:
#         print(f"\nERREUR: Le fichier à analyser '{fichier_a_analyser}' n'a pas été trouvé. Veuillez vérifier le chemin d'accès.")
# # endregion


# region 3. Analyse des factures individuelles et ajout dans la base de données
fichiers_a_analyser = [os.path.join(dossier_sortie, f) for f in os.listdir(dossier_sortie) if f.endswith('.pdf')]
for fichier_a_analyser in fichiers_a_analyser:
    nom_fournisseur = os.path.basename(fichier_a_analyser).split('_', 1)[0]
    imputations = trouver_associations_fournisseur(nom_fournisseur, DB_FILE)
    # print(nom_fournisseur," : ", imputations)
    imputation_calculées = application_regle_imputation_V2(fichier_a_analyser, client, imputations)
    # pb :  Suppression du fichier temporaire : files/z85juhcbtvdg
    texte_rouge = creation_texte_rouge(nom_fournisseur, imputations, imputation_calculées)
    ajouter_texte_rouge(fichier_a_analyser, texte_rouge)
    # ouvrir_visionneuse_pdf(fichier_a_analyser)

    '''
    TODO : 
        mettre une boucle while pour la validation
        creer une fonction imputation manuelle
        si non, fonction imputation manuelle
        (integrer imputation manuel en choix 6 dans la fonction validation_imputation)
        - Texte noir : penser à ajouter un retour à la ligne automatiquement au bout de 40 caractères
 
    '''
    # ----- boucle while
    texte_rouge, texte_noir = validation_imputation(texte_rouge)
    ajouter_texte_definitif(fichier_a_analyser,texte_rouge, texte_noir) 
    # ouvrir_visionneuse_pdf(fichier_a_analyser)
    # Validation / sinon 
    
# endregion

'''
On obtiens :
Nom du fournisseur : Bruneau
[('5/25', '50% du total TTC'), ('6/25', '50% du total HT')]

 -> appel IA pour rechercher imputations[i][1] dans boucle for 
 (voir si IA arrive a faire les opération / sinon integrer % dans tuple)

 - > affichage du resultat (texte rouge) dans pdf 

--------- voir si on sépare pas la patie imputation de la partie validation des facture

 - > ouvertuure du pdf pour validation utilisateur (nouvelle fenetres)
 - > choix multiple (boucle while) (texte noir)
    1. BAP
    2. prel
    3. chq : (input : num cheque)
    4. commentaire libre
    5. réécritre manuelle 
        5.1 prposition rouge
            entrer nom fourniseeur
            entrer compte (jusqu'a saisie vide)
        5.2 prposition noir
- > renomage facture et archivage dans dossier
- > saisie dans table comptabilité
'''

