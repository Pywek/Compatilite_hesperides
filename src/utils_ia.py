def nettoyer_nom_fournisseur(nom: str) -> str:
    """
    Nettoie le nom du fournisseur extrait par l'IA.
    Supprime les balises markdown et autres artefacts.
    """
    if not nom:
        return "Inconnu"
    
    # Nettoyer les balises markdown
    nom = nom.replace('```python', '').replace('```', '').strip()
    
    # Nettoyer les guillemets et apostrophes
    nom = nom.replace('"', '').replace("'", '').strip()
    
    # Si le nom est vide après nettoyage
    if not nom or nom == "":
        return "Inconnu"
    
    return nom
