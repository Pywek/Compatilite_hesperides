from pathlib import Path
import sys


def get_path(*subpaths):
    """
    Retourne le chemin complet vers un fichier ou dossier dans le projet.
    subpaths : morceaux du chemin à ajouter à la racine du projet
    """
    root = Path(__file__).parent.parent  # remonte de src/ à la racine
    return root.joinpath(*subpaths)

# print(get_path("data", "fichiers_test", "traqfood.pdf"))

def list_files(folder_path, extensions=None):
    """
    Retourne une liste de chemins complets pour tous les fichiers dans un dossier.
    
    Parameters:
    - folder_path : str ou Path → chemin du dossier à parcourir
    - extensions : list de str (ex: ['.pdf', '.txt']) → si précisé, ne garde que les fichiers avec ces extensions
    
    Returns:
    - List[Path] → chemins complets des fichiers
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"{folder_path} n'est pas un dossier valide.")

    files = []
    for f in folder.iterdir():
        if f.is_file():
            if extensions is None or f.suffix.lower() in extensions:
                files.append(f)
    return files

def add_project_root_to_sys_path():
    """
    Ajoute automatiquement la racine du projet au sys.path
    pour permettre d'importer les modules comme src.utils.
    
    Utilisation : appeler cette fonction tout en haut du script.
    """
    project_root = Path(__file__).parent.parent  # remonte de src/ à la racine
    sys.path.insert(0, str(project_root))





