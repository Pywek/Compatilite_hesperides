import os
import psycopg2
from psycopg2 import sql

def get_db_connection(db_url=None):
    """
    Etablit une connexion à la base de données PostgreSQL.
    Si db_url n'est pas fourni, cherche la variable d'environnement DATABASE_URL.
    """
    if not db_url:
        db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise ValueError("Aucune URL de base de données trouvée (DATABASE_URL manquante).")
        
    return psycopg2.connect(db_url)

def initialiser_bdd(db_url: str):
    """
    Initialise la base de données en créant la table nécessaire si elle n'existe pas.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS fournisseurs_comptes_associes (
        id SERIAL PRIMARY KEY,
        fournisseur TEXT UNIQUE NOT NULL,
        fournisseur_associe TEXT,
        mode TEXT,
        compte1 TEXT, regle1 TEXT,
        compte2 TEXT, regle2 TEXT,
        compte3 TEXT, regle3 TEXT,
        compte4 TEXT, regle4 TEXT,
        compte5 TEXT, regle5 TEXT,
        compte6 TEXT, regle6 TEXT
    );
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        
        # Création de la table des écritures comptables
        create_ecritures_sql = """
        CREATE TABLE IF NOT EXISTS ecritures_comptables (
            id SERIAL PRIMARY KEY,
            compte TEXT,
            date_facture DATE,
            fournisseur TEXT,
            montant NUMERIC,
            nom_fichier TEXT
        );
        """
        cursor.execute(create_ecritures_sql)
        
        # Ajout de la colonne date_ajout si elle n'existe pas
        try:
            cursor.execute("ALTER TABLE ecritures_comptables ADD COLUMN IF NOT EXISTS date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception as e:
            print(f"⚠️ Note: Erreur lors de l'ajout de date_ajout (peut-être déjà existante): {e}")
            conn.rollback()
        
        conn.commit()
        print(f"✅ Base de données initialisée (PostgreSQL)")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la BDD : {e}")
        return False
    finally:
        if conn:
            conn.close()


def bdd_est_disponible(db_url: str):
    """
    Vérifie si la base de données PostgreSQL est accessible.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        # Simple ping
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        print(f"✅ La BDD est disponible.")
        return True
    except Exception as e:
        print(f"❌ La BDD n'est pas disponible : {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_fournisseur_info(fournisseur_id, db_url: str):
    """
    Vérifie si un fournisseur existe et retourne son mode de saisie.
    """
    if not fournisseur_id:
        return None
    
    fournisseur_id_upper = fournisseur_id.upper().strip() 
        
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        sql_query = """
            SELECT mode 
            FROM fournisseurs_comptes_associes 
            WHERE UPPER(fournisseur) = %s 
        """
        cursor.execute(sql_query, (fournisseur_id_upper,))
        result = cursor.fetchone()
        
        if result:
            return result[0] # Retourne le mode ('A' ou 'M')
        else:
            return None # Fournisseur non trouvé

    except Exception as e:
        print(f"Erreur BDD : {e}")
        return None
    finally:
        if conn:
            conn.close()

def trouver_associations_fournisseur(nom_fournisseur: str, db_url: str):
    """
    Recherche les associations (compte, règle) pour un fournisseur donné.
    Retourne une liste de tuples [(compte, regle), ...].
    """
    if not nom_fournisseur:
        return []

    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        # Recherche insensible à la casse
        sql_query = """
        SELECT compte1, regle1, compte2, regle2, compte3, regle3, 
               compte4, regle4, compte5, regle5, compte6, regle6
        FROM fournisseurs_comptes_associes
        WHERE UPPER(fournisseur) = UPPER(%s)
        """
        cursor.execute(sql_query, (nom_fournisseur,))
        row = cursor.fetchone()
        
        associations = []
        if row:
            for i in range(0, len(row), 2):
                compte = row[i]
                regle = row[i+1]
                if compte: # On ne garde que si un compte est défini
                    associations.append((compte, regle))
        
        return associations
    except Exception as e:
        print(f"Erreur BDD (recherche) : {e}")
        return []
    finally:
        if conn:
            conn.close()

def ajouter_fournisseur_db(nom_fournisseur, fournisseur_associe, mode, comptes_regles, db_url):
    """
    Ajoute un nouveau fournisseur et ses règles dans la BDD.
    comptes_regles est une liste de tuples [(compte, regle), ...]
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        # Préparation des colonnes dynamiques (jusqu'à 6 comptes)
        colonnes = ["fournisseur", "fournisseur_associe", "mode"]
        valeurs = [nom_fournisseur, fournisseur_associe, mode]
        placeholders = ["%s", "%s", "%s"]
        
        for i, (compte, regle) in enumerate(comptes_regles):
            if i >= 6: break # Limite de 6 comptes
            colonnes.extend([f"compte{i+1}", f"regle{i+1}"])
            valeurs.extend([compte, regle])
            placeholders.extend(["%s", "%s"])
            
        # Construction sécurisée de la requête
        query = sql.SQL("INSERT INTO fournisseurs_comptes_associes ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, colonnes)),
            sql.SQL(', ').join(map(sql.Literal, valeurs)) # Note: psycopg2 handles quoting, but placeholders are better for values. 
        )
        # Correction: Using standard placeholders for values is safer and cleaner with psycopg2
        # Let's rewrite using standard string formatting for columns and %s for values
        
        col_names = ", ".join(colonnes)
        val_placeholders = ", ".join(placeholders)
        
        sql_query = f"INSERT INTO fournisseurs_comptes_associes ({col_names}) VALUES ({val_placeholders})"
        
        cursor.execute(sql_query, valeurs)
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur BDD (ajout) : {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_regles_fournisseur(nom_fournisseur: str, comptes_regles: list, db_url: str):
    """
    Met à jour les règles (comptes) pour un fournisseur existant.
    Écrase les anciennes règles.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        # On remet à NULL tous les comptes/règles d'abord
        reset_sql = """
        UPDATE fournisseurs_comptes_associes
        SET compte1=NULL, regle1=NULL, compte2=NULL, regle2=NULL,
            compte3=NULL, regle3=NULL, compte4=NULL, regle4=NULL,
            compte5=NULL, regle5=NULL, compte6=NULL, regle6=NULL
        WHERE UPPER(fournisseur) = UPPER(%s)
        """
        cursor.execute(reset_sql, (nom_fournisseur,))
        
        # Construction de la requête de mise à jour dynamique
        set_clauses = []
        valeurs = []
        
        for i, (compte, regle) in enumerate(comptes_regles):
            if i >= 6: break
            set_clauses.append(f"compte{i+1} = %s")
            set_clauses.append(f"regle{i+1} = %s")
            valeurs.extend([compte, regle])
            
        if set_clauses:
            update_sql = f"""
            UPDATE fournisseurs_comptes_associes
            SET {', '.join(set_clauses)}
            WHERE UPPER(fournisseur) = UPPER(%s)
            """
            valeurs.append(nom_fournisseur)
            cursor.execute(update_sql, valeurs)
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur BDD (update) : {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_tous_les_fournisseurs(db_url: str):
    """
    Récupère la liste complète des fournisseurs et de leurs configurations.
    Retourne une liste de tuples ou de dictionnaires.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        sql_query = """
        SELECT id, fournisseur, fournisseur_associe, mode,
               compte1, regle1, compte2, regle2, compte3, regle3,
               compte4, regle4, compte5, regle5, compte6, regle6
        FROM fournisseurs_comptes_associes
        ORDER BY fournisseur ASC
        """
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        # On peut retourner une liste de dictionnaires pour plus de facilité
        fournisseurs = []
        colonnes = [desc[0] for desc in cursor.description]
        
        for row in rows:
            fournisseurs.append(dict(zip(colonnes, row)))
            
        return fournisseurs
    except Exception as e:
        print(f"Erreur BDD (get_all) : {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_fournisseur_full(old_nom_fournisseur: str, new_data: dict, db_url: str):
    """
    Met à jour toutes les informations d'un fournisseur.
    Gère aussi le changement de nom (clé unique).
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        # Liste des champs à mettre à jour
        fields = [
            "fournisseur", "fournisseur_associe", "mode",
            "compte1", "regle1", "compte2", "regle2", "compte3", "regle3",
            "compte4", "regle4", "compte5", "regle5", "compte6", "regle6"
        ]
        
        set_clauses = [f"{field} = %s" for field in fields]
        values = [new_data.get(field) for field in fields]
        
        # Ajout de l'ancien nom pour le WHERE
        values.append(old_nom_fournisseur)
        
        sql_query = f"""
        UPDATE fournisseurs_comptes_associes
        SET {', '.join(set_clauses)}
        WHERE fournisseur = %s
        """
        
        cursor.execute(sql_query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur BDD (update full) : {e}")
        return False
    finally:
        if conn:
            conn.close()

def ajouter_ecriture_comptable(compte, date_facture, fournisseur, montant, nom_fichier, db_url):
    """
    Ajoute une écriture comptable dans la base de données.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        # On force l'insertion de la date d'ajout
        sql_query = """
        INSERT INTO ecritures_comptables (compte, date_facture, fournisseur, montant, nom_fichier, date_ajout)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(sql_query, (compte, date_facture, fournisseur, montant, nom_fichier))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur BDD (ajout écriture) : {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_toutes_ecritures(db_url):
    """
    Récupère toutes les écritures comptables triées par date décroissante.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        sql_query = """
        SELECT id, date_facture, fournisseur, compte, montant, nom_fichier, date_ajout
        FROM ecritures_comptables
        ORDER BY date_facture DESC, id DESC
        """
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        # Conversion en liste de dictionnaires
        ecritures = []
        colonnes = [desc[0] for desc in cursor.description]
        
        for row in rows:
            ecritures.append(dict(zip(colonnes, row)))
            
        return ecritures
    except Exception as e:
        print(f"Erreur BDD (get_all_ecritures) : {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_ecriture(id_ecriture, data, db_url):
    """
    Met à jour une écriture comptable.
    data est un dictionnaire contenant les champs à modifier.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        # Champs autorisés à la modification
        allowed_fields = ["date_facture", "fournisseur", "compte", "montant", "nom_fichier"]
        
        set_clauses = []
        values = []
        
        for field in allowed_fields:
            if field in data:
                set_clauses.append(f"{field} = %s")
                values.append(data[field])
        
        if not set_clauses:
            return False
            
        values.append(id_ecriture)
        
        sql_query = f"""
        UPDATE ecritures_comptables
        SET {', '.join(set_clauses)}
        WHERE id = %s
        """
        
        cursor.execute(sql_query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur BDD (update_ecriture) : {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_ecriture(id_ecriture, db_url):
    """
    Supprime une écriture comptable.
    """
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        
        sql_query = "DELETE FROM ecritures_comptables WHERE id = %s"
        cursor.execute(sql_query, (id_ecriture,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur BDD (delete_ecriture) : {e}")
        return False
    finally:
        if conn:
            conn.close()
