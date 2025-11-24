from src.pdf_manager import *



# CHEMINS
dossier_import = 'data\\input'
dossier_sortie = 'data\\output'

texte_rouge = """ LA RECRE DES ANCIENS
 - 05/25 : 102.21
 - 05/26 : 102.21"""

texte_noir = " --> BAP"

# ajouter_texte_fixe_dans_pdf("data\\input\\recre.pdf", "data\\output\\test_imputed.pdf", texte)

# ajouter_double_zone_texte("data\\input\\recre.pdf", "data\\output\\test_imputed.pdf", texte_rouge, texte_noir)

ajouter_texte_fixe_dans_pdf("data\\input\\recre.pdf", "data\\output\\test_imputed.pdf", texte_rouge, texte_noir)