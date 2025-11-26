import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
from src.gestion_bdd import get_toutes_ecritures, update_ecriture, delete_ecriture, initialiser_bdd, bdd_est_disponible

# Configuration de la page
st.set_page_config(page_title="Gestion Écritures", page_icon="📊", layout="wide")

# Chargement des variables d'environnement
load_dotenv()

@st.dialog("Modifier l'écriture")
def show_edit_dialog(ecriture, db_url):
    with st.form("edit_form"):
        new_date = st.date_input("Date Facture", value=ecriture['date_facture'])
        new_fournisseur = st.text_input("Fournisseur", value=ecriture['fournisseur'])
        new_compte = st.text_input("Compte", value=ecriture['compte'])
        new_montant = st.number_input("Montant", value=float(ecriture['montant']), step=0.01)
        
        submitted = st.form_submit_button("Enregistrer")
        if submitted:
            data = {
                "date_facture": new_date,
                "fournisseur": new_fournisseur,
                "compte": new_compte,
                "montant": new_montant
            }
            if update_ecriture(ecriture['id'], data, db_url):
                st.success("Modification enregistrée !")
                st.rerun()
            else:
                st.error("Erreur lors de la modification.")

@st.dialog("Confirmer la suppression")
def show_delete_dialog(ecriture, db_url):
    st.warning(f"Êtes-vous sûr de vouloir supprimer l'écriture de **{ecriture['fournisseur']}** ({ecriture['montant']} €) ?")
    st.write("Cette action est irréversible.")
    
    col1, col2 = st.columns(2)
    if col1.button("Oui, supprimer", type="primary"):
        if delete_ecriture(ecriture['id'], db_url):
            st.success("Écriture supprimée.")
            st.rerun()
        else:
            st.error("Erreur lors de la suppression.")
    
    if col2.button("Annuler"):
        st.rerun()

def main():
    st.title("📊 Gestion des Écritures Comptables")

    # Vérification BDD
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not bdd_est_disponible(db_url):
        st.error("Base de données indisponible.")
        st.stop()

    # Chargement des données
    ecritures = get_toutes_ecritures(db_url)
    
    if not ecritures:
        st.info("Aucune écriture comptable trouvée.")
        return

    # --- Filtres et Recherche ---
    st.markdown("### 🔍 Recherche et Filtres")
    col_search, col_sort = st.columns([2, 2])
    
    with col_search:
        search_term = st.text_input("Rechercher (Fournisseur, Compte, Fichier, Date)", placeholder="Tapez pour rechercher...")
    
    with col_sort:
        sort_option = st.selectbox(
            "Trier par",
            options=[
                "Date Facture (Récent -> Ancien)", 
                "Date Facture (Ancien -> Récent)", 
                "Montant (Décroissant)", 
                "Montant (Croissant)", 
                "Fournisseur (A-Z)",
                "Compte (A-Z)",
                "Compte (Z-A)"
            ]
        )

    # Application des filtres
    filtered_ecritures = ecritures
    
    # 1. Recherche
    if search_term:
        term = search_term.lower()
        filtered_ecritures = []
        for e in ecritures:
            # Formatage de la date pour la recherche (DD/MM/YYYY)
            date_str = e['date_facture'].strftime("%d/%m/%Y") if e['date_facture'] else ""
            
            if (term in (e['fournisseur'] or "").lower() or
                term in (e['compte'] or "").lower() or
                term in (e['nom_fichier'] or "").lower() or
                term in date_str):
                filtered_ecritures.append(e)
        
    # 3. Tri
    def normalize_compte_sort(compte_str):
        """
        Normalise le numéro de compte pour le tri.
        Transforme "X/Y" en "XX/00Y" pour un tri alphanumérique correct.
        Ex: "1/25" -> "01/025"
            "1/144" -> "01/144"
        Ainsi "01/025" < "01/144"
        """
        if not compte_str:
            return ""
        try:
            parts = compte_str.split('/')
            if len(parts) == 2:
                # On suppose X/Y
                part1 = int(parts[0])
                part2 = int(parts[1])
                return f"{part1:02d}/{part2:03d}"
            return compte_str
        except:
            return compte_str

    if sort_option == "Date Facture (Récent -> Ancien)":
        filtered_ecritures.sort(key=lambda x: x['date_facture'] or datetime.min, reverse=True)
    elif sort_option == "Date Facture (Ancien -> Récent)":
        filtered_ecritures.sort(key=lambda x: x['date_facture'] or datetime.min)
    elif sort_option == "Montant (Décroissant)":
        filtered_ecritures.sort(key=lambda x: float(x['montant'] or 0), reverse=True)
    elif sort_option == "Montant (Croissant)":
        filtered_ecritures.sort(key=lambda x: float(x['montant'] or 0))
    elif sort_option == "Fournisseur (A-Z)":
        filtered_ecritures.sort(key=lambda x: (x['fournisseur'] or "").lower())
    elif sort_option == "Compte (A-Z)":
        filtered_ecritures.sort(key=lambda x: normalize_compte_sort(x['compte']))
    elif sort_option == "Compte (Z-A)":
        filtered_ecritures.sort(key=lambda x: normalize_compte_sort(x['compte']), reverse=True)

    st.markdown(f"*Nombre d'écritures affichées : {len(filtered_ecritures)}*")
    st.markdown("---")

    # En-têtes du tableau
    # Colonnes : Date | Fournisseur | Compte | Montant | Fichier | Date Ajout | Actions
    headers = st.columns([1.5, 3, 1.5, 1.5, 3, 2, 1.5])
    headers[0].markdown("**Date Facture**")
    headers[1].markdown("**Fournisseur**")
    headers[2].markdown("**Compte**")
    headers[3].markdown("<div style='text-align: right; padding-right: 40px;'><b>Montant</b></div>", unsafe_allow_html=True)
    headers[4].markdown("**Fichier**")
    headers[5].markdown("**Date Ajout**")
    headers[6].markdown("**Actions**")
    
    st.markdown("---")

    def format_montant(val):
        try:
            # Format: 1 234,56 €
            return "{:,.2f}".format(float(val)).replace(",", " ").replace(".", ",") + " €"
        except:
            return f"{val} €"

    # Affichage des lignes
    for ecriture in filtered_ecritures:
        cols = st.columns([1.5, 3, 1.5, 1.5, 3, 2, 1.5])
        
        # Formatage des dates
        date_facture_str = ecriture['date_facture'].strftime("%d/%m/%Y") if ecriture['date_facture'] else ""
        
        date_ajout_str = ""
        if ecriture.get('date_ajout'):
            # Gestion du format timestamp qui peut varier selon le driver
            try:
                date_ajout_str = ecriture['date_ajout'].strftime("%d/%m/%Y %H:%M")
            except:
                date_ajout_str = str(ecriture['date_ajout'])
        else:
            date_ajout_str = "-"

        cols[0].write(date_facture_str)
        cols[1].write(ecriture['fournisseur'])
        cols[2].write(ecriture['compte'])
        cols[3].markdown(f"<div style='text-align: right; padding-right: 40px;'>{format_montant(ecriture['montant'])}</div>", unsafe_allow_html=True)
        cols[4].write(ecriture['nom_fichier'])
        cols[5].write(date_ajout_str)
        
        # Actions
        with cols[6]:
            c1, c2 = st.columns([1, 1])
            # On utilise des clés uniques pour chaque bouton
            if c1.button("✏️", key=f"edit_{ecriture['id']}", help="Modifier"):
                show_edit_dialog(ecriture, db_url)
            
            if c2.button("🗑️", key=f"del_{ecriture['id']}", help="Supprimer"):
                show_delete_dialog(ecriture, db_url)
        
        st.markdown("<hr style='margin: 0.5em 0; opacity: 0.2;'>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
