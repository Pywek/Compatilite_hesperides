import pytest
from pathlib import Path
from src.utils import get_path, list_files
import tempfile
import os

# ----------------------------
# Test de get_path
# ----------------------------
def test_get_path_returns_correct_path():
    # On construit un chemin relatif
    path = get_path("data", "test_pdfs", "facture_test.pdf")
    
    # Vérifie que c'est un objet Path
    assert isinstance(path, Path)
    
    # Vérifie que la fin du chemin est correcte
    assert str(path).endswith(os.path.join("data", "test_pdfs", "facture_test.pdf"))

# ----------------------------
# Test de list_files
# ----------------------------
def test_list_files_with_extensions():
    # Crée un dossier temporaire avec des fichiers
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Création de fichiers test
        (tmp_path / "file1.pdf").write_text("PDF 1")
        (tmp_path / "file2.txt").write_text("TXT 2")
        (tmp_path / "file3.pdf").write_text("PDF 3")
        
        # Liste tous les PDFs uniquement
        pdf_files = list_files(tmp_path, extensions=[".pdf"])
        pdf_names = [f.name for f in pdf_files]
        
        # Vérifie qu'on ne récupère que les .pdf
        assert "file1.pdf" in pdf_names
        assert "file3.pdf" in pdf_names
        assert "file2.txt" not in pdf_names

def test_list_files_without_extensions():
    # Crée un dossier temporaire avec des fichiers
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "file1.pdf").write_text("PDF 1")
        (tmp_path / "file2.txt").write_text("TXT 2")
        
        # Liste tous les fichiers sans filtre
        all_files = list_files(tmp_path)
        all_names = [f.name for f in all_files]
        
        assert "file1.pdf" in all_names
        assert "file2.txt" in all_names
