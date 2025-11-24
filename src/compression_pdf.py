import os


def compresser_pdf(input_path: str, output_path: str):
    """
    Compresse un PDF en réduisant la qualité des images.
    Cible : 1.4MB → 100-500KB tout en gardant la lisibilité.
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(input_path)
        images_traitees = 0
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                
                try:
                    pix = fitz.Pixmap(doc, xref)
                    
                    # Convertir CMYK en RGB
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    
                    # Redimensionner si > 800px
                    if pix.width > 800 or pix.height > 800:
                        zoom = 800 / max(pix.width, pix.height)
                        mat = fitz.Matrix(zoom, zoom)
                        pix = fitz.Pixmap(pix, mat)
                    
                    # Compresser en JPEG qualité 60
                    img_bytes = pix.tobytes("jpeg", jpg_quality=60)
                    
                    # Remplacer seulement si ça réduit la taille
                    if len(img_bytes) < pix.size:
                        doc.update_stream(xref, img_bytes)
                        images_traitees += 1
                    
                except Exception as e:
                    print(f"⚠️ Erreur image {img_index} page {page_num}: {e}")
                    continue
        
        # Sauvegarder avec compression maximale
        doc.save(output_path, garbage=4, deflate=True, clean=True, linear=True)
        doc.close()
        
        # Afficher les tailles
        taille_avant = os.path.getsize(input_path) / 1024
        taille_apres = os.path.getsize(output_path) / 1024
        
        if taille_avant > 0:
            reduction = ((taille_avant - taille_apres) / taille_avant) * 100
        else:
            reduction = 0
        
        if images_traitees > 0:
            print(f"✅ PDF compressé : {taille_avant:.1f} KB → {taille_apres:.1f} KB (-{reduction:.1f}%) - {images_traitees} images")
        else:
            print(f"ℹ️ PDF optimisé : {taille_avant:.1f} KB → {taille_apres:.1f} KB (-{reduction:.1f}%) - Pas d'images à compresser")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur compression : {e}")
        try:
            import shutil
            shutil.copy(input_path, output_path)
            return True
        except:
            return False
