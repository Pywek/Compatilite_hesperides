import os
import fitz  # PyMuPDF


def rasteriser_et_compresser(
    input_path: str,
    output_path: str,
    dpi: int = 150,
    jpeg_quality: int = 50,
) -> bool:
    """Rasterise chaque page du PDF en image JPEG puis crée un PDF image‑only.

    - `dpi` : résolution de rendu (150 dpi est un bon compromis lisibilité/taille).
    - `jpeg_quality` : qualité JPEG (50 ≈ compression forte, texte encore lisible).
    - Retourne ``True`` si la conversion réussit, sinon ``False``.
    """
    try:
        # Ouvrir le PDF source
        src_doc = fitz.open(input_path)
        # Nouveau PDF vide
        out_doc = fitz.open()
        for page in src_doc:
            # Rendu de la page en pixmap JPEG
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
            img_bytes = pix.tobytes("jpeg", jpg_quality=jpeg_quality)
            # Crée une page de même taille que l'image
            rect = fitz.Rect(0, 0, pix.width, pix.height)
            new_page = out_doc.new_page(width=rect.width, height=rect.height)
            # Insère l'image JPEG
            new_page.insert_image(rect, stream=img_bytes)
        # Sauvegarde avec compression maximale
        out_doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True,
            linear=True,
        )
        out_doc.close()
        src_doc.close()
        # Affichage des tailles (optionnel, utile en dev)
        before_kb = os.path.getsize(input_path) / 1024
        after_kb = os.path.getsize(output_path) / 1024
        reduction = ((before_kb - after_kb) / before_kb) * 100 if before_kb else 0
        print(
            f"✅ PDF rasterisé : {before_kb:.1f} KB → {after_kb:.1f} KB (-{reduction:.1f} %)"
        )
        return True
    except Exception as e:
        print(f"❌ Erreur lors du rasterisation/compression : {e}")
        return False
