# ---------------------------------------------------------------
#  Mise à jour d'une base EXISTANTE, sans perdre les données
# ---------------------------------------------------------------
#  À lancer depuis une console Bash PythonAnywhere :
#      cd ~/mysite
#      python3 migrate_db.py
#
#  Le script peut être relancé sans risque : ce qui existe déjà
#  (colonne, table, compte) n'est pas recréé.
# ---------------------------------------------------------------

import os
import sqlite3
import sys

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

# Comptes de démonstration de l'atelier : (login, mot de passe, rôle)
COMPTES_DEMO = [
    ('admin', 'password', 'admin'),
    ('user', '12345', 'user'),
]


def executer_migration(connection, nom_fichier):
    chemin = os.path.join(BASE_DIR, 'migrations', nom_fichier)
    with open(chemin, encoding='utf-8') as f:
        connection.executescript(f.read())


def creer_comptes_demo(connection):
    for login, mot_de_passe, role in COMPTES_DEMO:
        # OR IGNORE : un compte déjà présent n'est pas modifié
        connection.execute(
            'INSERT OR IGNORE INTO utilisateurs (login, mot_de_passe_hash, role) VALUES (?, ?, ?)',
            (login, generate_password_hash(mot_de_passe), role))


def migrer():
    if not os.path.exists(DATABASE):
        sys.exit("Aucune base trouvée : lancez d'abord python3 create_db.py")

    connection = sqlite3.connect(DATABASE)

    colonnes = [ligne[1] for ligne in connection.execute('PRAGMA table_info(clients)')]
    if 'telephone' not in colonnes:
        executer_migration(connection, '001_ajout_telephone.sql')

    executer_migration(connection, '002_creation_commandes.sql')
    executer_migration(connection, '003_creation_utilisateurs.sql')
    creer_comptes_demo(connection)

    connection.commit()
    connection.close()
    print("✅ Base de données à jour : database.db")


if __name__ == '__main__':
    migrer()
