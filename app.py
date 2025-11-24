import streamlit as st
import os
import shutil
import time
import base64
import zipfile
import io
from datetime import datetime
from dotenv import load_dotenv
from src.gestion_bdd import initialiser_bdd, bdd_est_disponible, ajouter_fournisseur_db, trouver_associations_fournisseur, update_regles_fournisseur
from src.appels_ia import initialisation_client_gemini, get_infos_facture, application_regle_imputation_V2
from src.pdf_manager import ajouter_texte_definitif
from src.compression_pdf import compresser_pdf

# Configuration de la page
st.set_page_config(page_title="Comptabilité IA", page_icon="📄", layout="wide")

# Chargement des variables d'environnement
load_dotenv()

# Constantes
# DB_FILE = "Comptabilité.db" # PLUS UTILISÉ AVEC POSTGRES
TEMP_DIR = "temp_files"
READY_DIR = os.path.join(TEMP_DIR, "ready")

def cleanup_temp_files():
    """Supprime le contenu du dossier temporaire."""
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(READY_DIR, exist_ok=True)
    except PermissionError:
        # Si le dossier est verrouillé, on essaie juste de le créer s'il n'existe pas
        os.makedirs(TEMP_DIR, exist_ok=True)
    except Exception as e:
        print(f"⚠️ Erreur lors du nettoyage des fichiers temporaires : {e}")
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(READY_DIR, exist_ok=True)


def main():
    st.title("📄 Assistant Comptabilité IA")

    # Nettoyage au démarrage (une seule fois par session)
    if "startup_cleanup_done" not in st.session_state:
        cleanup_temp_files()
        st.session_state["startup_cleanup_done"] = True

    # Sidebar : État du système
    with st.sidebar:
        st.header("État du Système")
        
        # Vérification API Key
        if os.getenv("GENAI_KEY"):
            st.success("Clé API Gemini détectée")
        else:
            st.error("Clé API Gemini manquante (.env)")
            st.stop()

        # Vérification BDD
        db_url = os.getenv("DATABASE_URL")
        if db_url and initialiser_bdd(db_url) and bdd_est_disponible(db_url):
            st.success("Base de données connectée (PostgreSQL)")
        else:
            st.error("Base de données indisponible (Vérifiez .env)")
            st.stop()

        # Initialisation Client Gemini
        client = initialisation_client_gemini()
        if client:
            st.success("Client Gemini prêt")
        else:
            st.error("Erreur client Gemini")
            st.stop()

    # Initialisation de la clé du uploader pour permettre le reset
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    # Message de succès global après traitement du lot
    # Message de succès global après traitement du lot
    if st.session_state.get("batch_finished"):
        st.success("✅ Toutes les factures ont été traitées. Vous pouvez télécharger le résultat ci-dessous.")
        
        # Affichage du bouton de téléchargement ZIP
        if "processed_files" in st.session_state and st.session_state["processed_files"]:
            # Création du ZIP en mémoire
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in st.session_state["processed_files"]:
                    file_name = os.path.basename(file_path)
                    if os.path.exists(file_path):
                        zip_file.write(file_path, file_name)
            
            st.download_button(
                label="📥 Télécharger toutes les factures (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Factures_Traitees.zip",
                mime="application/zip"
            )
            
            st.markdown("---")
            
        if st.button("Nouvelle série"):
            # Nettoyage complet
            keys_to_delete = ["current_index", "files_to_process", "last_upload_names", "fournisseur", "date_facture", "imputations", "pdf_processed", "creation_mode", "current_file", "batch_finished", "processed_files"]
            for k in keys_to_delete:
                if k in st.session_state:
                    del st.session_state[k]
            # Nettoyage des fichiers temporaires
            cleanup_temp_files()
            st.rerun()
            
        # On arrête l'exécution ici pour ne pas afficher l'uploader en dessous si on a fini
        st.stop()

    # Zone d'upload (Multiple files)
    uploaded_files_obj = st.file_uploader(
        "Déposez vos factures (PDF)", 
        type="pdf", 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state['uploader_key']}"
    )

    if uploaded_files_obj:
        # Nouvelle série : on nettoie le message de succès précédent
        if "batch_finished" in st.session_state:
            del st.session_state["batch_finished"]

        # --- PRÉ-TRAITEMENT : Détection et Découpage des Factures Multiples ---
        # On vérifie si la liste des fichiers uploadés a changé pour relancer le découpage
        current_upload_names = [f.name for f in uploaded_files_obj]
        
        if "files_to_process" not in st.session_state or \
           "last_upload_names" not in st.session_state or \
           st.session_state["last_upload_names"] != current_upload_names:
            
            st.session_state["last_upload_names"] = current_upload_names
            st.session_state["files_to_process"] = [] # Liste des chemins de fichiers finaux à traiter
            st.session_state["processed_files"] = [] # Liste des fichiers traités prêts pour le ZIP
            
            # On s'assure que le dossier temp existe
            os.makedirs(TEMP_DIR, exist_ok=True)
            os.makedirs(READY_DIR, exist_ok=True)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, uploaded_file in enumerate(uploaded_files_obj):
                status_text.text(f"Analyse du fichier {idx+1}/{len(uploaded_files_obj)} : {uploaded_file.name}...")
                progress_bar.progress((idx) / len(uploaded_files_obj))
                
                # 1. Sauvegarde temporaire du fichier uploadé
                temp_path = os.path.join(TEMP_DIR, f"upload_{uploaded_file.name}")
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 2. Vérification du nombre de pages
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(temp_path)
                    num_pages = len(reader.pages)
                except Exception as e:
                    st.error(f"Erreur lecture PDF {uploaded_file.name}: {e}")
                    num_pages = 1 # Fallback
                
                fichiers_a_ajouter = [temp_path] # Par défaut, on garde le fichier tel quel
                
                # 3. Si > 1 page, on demande à l'IA s'il y a plusieurs factures
                if num_pages > 1:
                    status_text.text(f"Analyse IA multi-factures pour : {uploaded_file.name}...")
                    from src.appels_ia import analyser_et_separer_factures
                    from src.pdf_manager import extraire_factures_pdf
                    
                    # Appel IA pour détecter les factures
                    infos_factures = analyser_et_separer_factures(temp_path, client)
                    
                    if infos_factures and len(infos_factures) > 1:
                        status_text.text(f"Découpage de {len(infos_factures)} factures détectées dans {uploaded_file.name}...")
                        # Découpage physique
                        chemins_split = extraire_factures_pdf(temp_path, infos_factures, dossier_sortie=TEMP_DIR)
                        if chemins_split:
                            fichiers_a_ajouter = chemins_split
                            # On supprime le fichier original "upload_" car il est remplacé par les splits
                            # os.remove(temp_path) # Optionnel : garder pour debug ou supprimer
                        else:
                            st.warning(f"Échec du découpage pour {uploaded_file.name}, traitement du fichier entier.")
                
                # Ajout des fichiers (splités ou original) à la liste de traitement
                st.session_state["files_to_process"].extend(fichiers_a_ajouter)
            
            progress_bar.empty()
            status_text.empty()
            
            # Reset des index de traitement
            st.session_state["current_index"] = 0
            keys_to_reset = ["fournisseur", "date_facture", "imputations", "pdf_processed", "creation_mode", "current_file"]
            for k in keys_to_reset:
                if k in st.session_state: del st.session_state[k]

        # --- FIN PRÉ-TRAITEMENT ---

        # Récupération de la liste des fichiers à traiter (chemins absolus ou relatifs)
        files_to_process = st.session_state["files_to_process"]
        
        if not files_to_process:
            st.warning("Aucun fichier à traiter.")
            st.stop()

        # Initialisation de l'index de traitement (sécurité)
        if "current_index" not in st.session_state:
            st.session_state["current_index"] = 0
        
        # Sélection du fichier courant (Chemin fichier)
        current_file_path = files_to_process[st.session_state["current_index"]]
        current_file_name = os.path.basename(current_file_path)
        
        # Affichage de la progression
        progress_val = (st.session_state["current_index"]) / len(files_to_process)
        st.progress(progress_val)
        st.write(f"Traitement de la facture **{st.session_state['current_index'] + 1} / {len(files_to_process)}** : `{current_file_name}`")

        # Définition des chemins de travail
        # Note: current_file_path est déjà dans TEMP_DIR normalement (soit upload_... soit split_...)
        # On crée un fichier "temp_" spécifique pour le traitement en cours pour ne pas toucher au fichier source de la liste
        temp_working_path = os.path.join(TEMP_DIR, f"working_{current_file_name}")
        preview_path = os.path.join(TEMP_DIR, f"preview_{current_file_name}")

        # Sauvegarde initiale / Copie pour le traitement
        if "current_file" not in st.session_state or st.session_state["current_file"] != current_file_name:
            # On copie le fichier de la liste vers le fichier de travail
            shutil.copy(current_file_path, temp_working_path)
            
            # On crée une copie pour la preview initiale
            shutil.copy(temp_working_path, preview_path)
            
            st.session_state["current_file"] = current_file_name
            
            # Reset des états spécifiques au fichier
            keys_to_reset = ["fournisseur", "date_facture", "imputations", "imputations_file", "pdf_processed", "creation_mode"]
            for k in keys_to_reset:
                if k in st.session_state: del st.session_state[k]
            
            # Supprimer TOUTES les clés de widgets de l'ancien fichier pour forcer un reset complet
            keys_to_delete = []
            for key in st.session_state.keys():
                if isinstance(key, str) and (
                    key.startswith("input_") or 
                    key.startswith("man_compte_") or 
                    key.startswith("man_montant_") or
                    key.startswith("manual_mode_") or
                    key.startswith("paiement_radio_") or
                    key.startswith("num_cheque_") or
                    key.startswith("comm_libre_")
                ):
                    keys_to_delete.append(key)
            
            for k in keys_to_delete:
                del st.session_state[k]
            
            # Force un rerun pour recréer les widgets avec les nouvelles clés
            st.rerun()


        # Étape 1 : Identification (Nom + Date)
        if "fournisseur" not in st.session_state:
            with st.spinner("Analyse de la facture (Fournisseur & Date)..."):
                # On utilise temp_working_path qui est la copie de travail
                nom_fournisseur, date_str = get_infos_facture(temp_working_path, client)
                
                # Fallback si erreur
                if not nom_fournisseur: nom_fournisseur = "Inconnu"
                
                # Parsing date
                date_obj = datetime.now().date()
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, "%d/%m/%Y").date()
                    except:
                        pass # On garde la date du jour par défaut

                st.session_state["fournisseur"] = nom_fournisseur
                st.session_state["date_facture"] = date_obj

        nom_fournisseur = st.session_state["fournisseur"]
        date_facture_init = st.session_state["date_facture"]

        st.subheader(f"Fournisseur : {nom_fournisseur}")

        # Étape 2 : Recherche en BDD
        associations = trouver_associations_fournisseur(nom_fournisseur, db_url)

        if not associations and "creation_mode" not in st.session_state:
            st.warning(f"Fournisseur inconnu : {nom_fournisseur}")
            if st.button("Créer ce fournisseur"):
                st.session_state["creation_mode"] = True
                st.rerun()

        # Formulaire de création (inchangé)
        if st.session_state.get("creation_mode"):
            with st.form("creation_fournisseur"):
                st.write(f"Création pour : **{nom_fournisseur}**")
                fournisseur_associe = st.text_input("Fournisseur associé (optionnel)")
                mode = st.selectbox("Mode", ["A", "M"], format_func=lambda x: "Automatique" if x == "A" else "Manuel")
                
                comptes_regles = []
                for i in range(1, 7):
                    c1, c2 = st.columns(2)
                    compte = c1.text_input(f"Compte {i}")
                    regle = c2.text_input(f"Règle {i}")
                    if compte:
                        comptes_regles.append((compte, regle))
                
                submitted = st.form_submit_button("Enregistrer")
                if submitted:
                    if ajouter_fournisseur_db(nom_fournisseur, fournisseur_associe, mode, comptes_regles, db_url):
                        st.success("Fournisseur créé !")
                        del st.session_state["creation_mode"]
                        st.rerun()
                    else:
                        st.error("Erreur lors de la création.")

        # Étape 3 : Extraction et Validation (Live Preview)
        elif associations:
            # Extraction IA si pas faite
            if "imputations" not in st.session_state:
                with st.spinner("Extraction des données..."):
                    regles_pour_ia = [assoc for assoc in associations if len(assoc) > 1 and assoc[1]]
                    if regles_pour_ia:
                        try:
                            resultats_ia = application_regle_imputation_V2(temp_working_path, client, regles_pour_ia)
                            st.session_state["imputations"] = resultats_ia
                        except Exception as e:
                            st.error(f"Erreur IA : {e}")
                            st.session_state["imputations"] = tuple(["Erreur"] * len(regles_pour_ia))
                    else:
                        st.session_state["imputations"] = tuple()

            st.subheader("Validation & Prévisualisation")
            
            col1, col2 = st.columns([1, 1])
            
            # --- COLONNE GAUCHE : INPUTS (Sans st.form pour interactivité) ---
            with col1:
                st.markdown("### Données")
                
                # Mode Saisie Manuelle
                mode_manuel = st.toggle("✏️ Saisie Manuelle", key=f"manual_mode_{current_file_name}")

                # Nom du fournisseur modifiable
                nom_fournisseur_final = st.text_input("Nom du fournisseur", value=nom_fournisseur)
                
                # Date (pré-remplie par IA)
                new_date = st.date_input("Date de la facture", value=date_facture_init, format="DD/MM/YYYY")
                
                # Construction du texte rouge (Fournisseur + Comptes/Montants)
                lignes_rouge = [f" {nom_fournisseur_final.upper()}"]
                
                if mode_manuel:
                    st.markdown("#### Saisie des comptes")
                    comptes_manuels_pour_db = []
                    for i in range(6):
                        c_acc, c_mnt = st.columns([1, 1])
                        compte_man = c_acc.text_input(f"Compte {i+1}", key=f"man_compte_{i}_{current_file_name}")
                        montant_man = c_mnt.text_input(f"Montant {i+1}", key=f"man_montant_{i}_{current_file_name}")
                        
                        if compte_man and montant_man:
                            lignes_rouge.append(f" - {compte_man} : {montant_man}")
                            comptes_manuels_pour_db.append((compte_man, "")) # Pas de mot clé pour le manuel
                    
                    update_db = st.checkbox("Mettre à jour les règles par défaut pour ce fournisseur avec ces comptes ?")

                else:
                    idx_ia = 0
                    for i, assoc in enumerate(associations):
                        compte = assoc[0]
                        valeur_defaut = ""
                        if len(assoc) > 1 and assoc[1]:
                             if idx_ia < len(st.session_state["imputations"]):
                                 valeur_defaut = str(st.session_state["imputations"][idx_ia])
                                 idx_ia += 1
                        
                        # On utilise key pour garder l'état entre les reruns, mais unique par fichier
                        valeur_modifiee = st.text_input(f"Montant pour {compte}", value=valeur_defaut, key=f"input_{i}_{current_file_name}")
                        if valeur_modifiee:
                            lignes_rouge.append(f" - {compte} : {valeur_modifiee}")
                
                # -------------------------------------------------
                # Ajout des options de paiement (DÉPLACÉ ICI)
                st.markdown("---")
                st.markdown("### Paiement")
                choix_paiement = st.radio(
                    "Moyen de paiement",
                    ["BAP", "Prélèvement", "CB", "Chèque", "Commentaire libre"],
                    key=f"paiement_radio_{current_file_name}"
                )

                # Texte noir selon le choix
                texte_noir = ""
                if choix_paiement == "BAP":
                    texte_noir = " -> BAP"
                elif choix_paiement == "Prélèvement":
                    texte_noir = " -> Prélèvement"
                elif choix_paiement == "CB":
                    texte_noir = " -> CB"
                elif choix_paiement == "Chèque":
                    num_cheque = st.text_input("Numéro de chèque", key=f"num_cheque_{current_file_name}")
                    texte_noir = f" -> Chèque n° : {num_cheque}"
                elif choix_paiement == "Commentaire libre":
                    commentaire = st.text_input("Commentaire", key=f"comm_libre_{current_file_name}")
                    texte_noir = f" -> {commentaire}"
                # -------------------------------------------------
                
                texte_rouge_genere = "\n".join(lignes_rouge)
                
                # --- MISE À JOUR DE LA PREVIEW ---
                shutil.copy(temp_working_path, preview_path)
                ajouter_texte_definitif(preview_path, texte_rouge_genere, texte_noir)
                
                st.markdown("---")
                st.markdown("---")
                # Bouton de validation modifié pour le flux ZIP
                if st.button("Valider et Suivant"):
                    # 0. Mise à jour BDD si demandé
                    if mode_manuel and update_db and comptes_manuels_pour_db:
                        if update_regles_fournisseur(nom_fournisseur_final, comptes_manuels_pour_db, db_url):
                            st.success("Règles fournisseur mises à jour !")
                        else:
                            st.warning("Impossible de mettre à jour les règles (Fournisseur inconnu ou erreur).")

                        keys_to_reset = ["fournisseur", "date_facture", "imputations", "pdf_processed", "creation_mode", "current_file"]
                        for k in keys_to_reset:
                            if k in st.session_state: del st.session_state[k]
                        st.rerun()

                    # 1. Préparer le nom final
                    try:
                        new_date_obj = new_date
                    except:
                        new_date_obj = datetime.now()

                    # 1.5 Appliquer définitivement le texte sur le fichier de travail
                    ajouter_texte_definitif(temp_working_path, texte_rouge_genere, texte_noir)

                    # 2. Sauvegarder dans le dossier READY (pas d'archivage serveur)
                    date_str = new_date.strftime("%d-%m-%Y")
                    nom_clean = "".join(c for c in nom_fournisseur_final if c.isalnum() or c in (' ', '_', '-')).strip()
                    nom_fichier_final = f"{nom_clean}_{date_str}.pdf"
                    chemin_final = os.path.join(READY_DIR, nom_fichier_final)

                    # Compression du PDF vers le dossier READY
                    with st.spinner("Traitement et compression..."):
                        compresser_pdf(temp_working_path, chemin_final)
                    
                    # Ajout à la liste des fichiers traités
                    if "processed_files" not in st.session_state:
                        st.session_state["processed_files"] = []
                    st.session_state["processed_files"].append(chemin_final)

                    st.success(f"✅ Facture traitée : {nom_fichier_final}")
                    time.sleep(0.5)

                    # 3. Gestion de la suite (Suivant ou Fin)
                    if st.session_state["current_index"] + 1 >= len(files_to_process):
                        # C'était le dernier fichier
                        st.session_state["batch_finished"] = True
                        st.session_state["uploader_key"] += 1 # Reset du uploader
                        st.rerun()
                    else:
                        # Passage au fichier suivant
                        st.session_state["current_index"] += 1
                        # Reset des états pour le prochain
                        keys_to_reset = ["fournisseur", "date_facture", "imputations", "pdf_processed", "creation_mode", "current_file"]
                        for k in keys_to_reset:
                            if k in st.session_state: del st.session_state[k]
                        st.rerun()

            # --- COLONNE DROITE : PREVIEW ---
            with col2:
                # Affichage du PDF de preview
                with open(preview_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
