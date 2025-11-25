import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
from src.gestion_bdd import get_tous_les_fournisseurs, update_fournisseur_full, initialiser_bdd

# Configuration de la page
st.set_page_config(page_title="Gestion Fournisseurs", page_icon="👥", layout="wide")

# Chargement des variables d'environnement
load_dotenv()

def main():
    st.title("👥 Gestion des Fournisseurs")

    # Vérification BDD
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        st.error("Base de données indisponible (Vérifiez .env)")
        st.stop()

    # Chargement des données
    fournisseurs = get_tous_les_fournisseurs(db_url)
    
    if not fournisseurs:
        st.info("Aucun fournisseur trouvé dans la base de données.")
        return

    # --- VUE TABLEAU ---
    st.subheader("Liste des Fournisseurs")
    
    # Création d'un DataFrame pour l'affichage
    df = pd.DataFrame(fournisseurs)
    
    # Sélection des colonnes pertinentes pour l'aperçu
    cols_apercu = ["fournisseur", "fournisseur_associe", "mode", "compte1", "regle1"]
    st.dataframe(df[cols_apercu], use_container_width=True)

    st.markdown("---")

    # --- VUE ÉDITION ---
    st.subheader("✏️ Modifier un Fournisseur")

    # Sélecteur de fournisseur
    liste_noms = [f["fournisseur"] for f in fournisseurs]
    choix_fournisseur = st.selectbox("Sélectionnez un fournisseur à modifier", liste_noms)

    if choix_fournisseur:
        # Récupération des données du fournisseur sélectionné
        data_fournisseur = next((f for f in fournisseurs if f["fournisseur"] == choix_fournisseur), None)
        
        if data_fournisseur:
            with st.form("edit_fournisseur_form"):
                c1, c2, c3 = st.columns(3)
                
                # Champs principaux
                new_nom = c1.text_input("Nom Fournisseur", value=data_fournisseur["fournisseur"])
                new_associe = c2.text_input("Fournisseur Associé", value=data_fournisseur["fournisseur_associe"] or "")
                new_mode = c3.selectbox("Mode", ["A", "M"], index=0 if data_fournisseur["mode"] == "A" else 1, format_func=lambda x: "Automatique" if x == "A" else "Manuel")

                st.markdown("#### Comptes et Règles")
                
                # Champs dynamiques pour les 6 comptes
                new_comptes_regles = {}
                for i in range(1, 7):
                    cc1, cc2 = st.columns(2)
                    compte_key = f"compte{i}"
                    regle_key = f"regle{i}"
                    
                    val_compte = data_fournisseur.get(compte_key) or ""
                    val_regle = data_fournisseur.get(regle_key) or ""
                    
                    new_comptes_regles[compte_key] = cc1.text_input(f"Compte {i}", value=val_compte)
                    new_comptes_regles[regle_key] = cc2.text_input(f"Règle {i}", value=val_regle)

                submitted = st.form_submit_button("Enregistrer les modifications")
                
                if submitted:
                    # Préparation des données pour l'update
                    update_data = {
                        "fournisseur": new_nom,
                        "fournisseur_associe": new_associe,
                        "mode": new_mode,
                        **new_comptes_regles
                    }
                    
                    if update_fournisseur_full(choix_fournisseur, update_data, db_url):
                        st.success(f"Fournisseur '{new_nom}' mis à jour avec succès !")
                        st.rerun()
                    else:
                        st.error("Erreur lors de la mise à jour.")

if __name__ == "__main__":
    main()
