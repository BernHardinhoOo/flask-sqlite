# ---------------------------------------------------------------
#  Atelier Flask + SQLite
# ---------------------------------------------------------------
#  Ce fichier est le "cerveau" de votre application : il reçoit
#  les demandes des navigateurs, interroge la base de données
#  et fabrique les réponses.
#
#  Vous allez le compléter petit à petit, exercice après exercice.
#  Les consignes sont dans le dossier "exercices/".
# ---------------------------------------------------------------

import math
import os
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'  # Clé secrète pour signer les sessions (à cacher par la suite)

# Chemin ABSOLU vers la base de données.
# Sur PythonAnywhere, le serveur ne démarre pas forcément dans le dossier
# du projet : un simple 'database.db' créerait une base vide ailleurs !
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')


def get_db():
    """Ouvre une connexion à la base de données SQLite."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # pour écrire row['nom'] au lieu de row[2]
    conn.execute('PRAGMA foreign_keys = ON')  # faire respecter les clés étrangères
    return conn


# ---------------------------------------------------------------
#  Contrôle d'accès (exercice 8)
# ---------------------------------------------------------------

# Fonction pour savoir si l'utilisateur s'est authentifié
def est_authentifie():
    return session.get('authentifie')


def a_le_role(*roles):
    """Renvoie True si l'utilisateur connecté a l'un des rôles indiqués."""
    return session.get('role') in roles


ACCES_REFUSE = "<h2>Accès refusé : réservé aux administrateurs</h2>"


@app.route('/')
def hello_world():
    return render_template('hello.html')


@app.route('/lecture')
def lecture():
    if not est_authentifie():
        # Rediriger vers la page d'authentification si l'utilisateur n'est pas authentifié
        return redirect(url_for('authentification'))

    # Si l'utilisateur est authentifié
    return '<h2>Bravo, vous êtes authentifié</h2><p><a href="/">Retour à l\'accueil</a></p>'


@app.route('/authentification', methods=['GET', 'POST'])
def authentification():
    if request.method == 'POST':
        login = request.form.get('username', '')
        mot_de_passe = request.form.get('password', '')

        # Les comptes sont dans la base, avec un mot de passe haché
        conn = get_db()
        compte = conn.execute('SELECT * FROM utilisateurs WHERE login = ?', (login,)).fetchone()
        conn.close()

        if compte and check_password_hash(compte['mot_de_passe_hash'], mot_de_passe):
            session.clear()
            session['authentifie'] = True
            session['utilisateur'] = compte['login']
            session['role'] = compte['role']
            # Rediriger vers la route lecture après une authentification réussie
            return redirect(url_for('lecture'))

        # Afficher un message d'erreur si les identifiants sont incorrects
        return render_template('formulaire_authentification.html', error=True)

    return render_template('formulaire_authentification.html', error=False)


@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect('/')


# ---------------------------------------------------------------
#  Lire et rechercher (exercices 2 et 3)
# ---------------------------------------------------------------

@app.route('/fiche_client/<int:post_id>')
def Readfiche(post_id):
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (post_id,)).fetchone()
    commandes = conn.execute(
        'SELECT * FROM commandes WHERE client_id = ? ORDER BY date_commande DESC', (post_id,)
    ).fetchall()
    conn.close()

    if client is None:
        return "<h2>Client introuvable</h2>", 404

    # Rendre le template HTML et transmettre les données
    return render_template('fiche_client.html', client=client, commandes=commandes)


@app.route('/consultation/')
def ReadBDD():
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients ORDER BY nom;')
    data = cursor.fetchall()
    conn.close()
    return render_template('read_data.html', data=data)


@app.route('/fiche_nom/<nom>')
def fiche_nom(nom):
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients WHERE nom = ?', (nom,))
    data = cursor.fetchall()
    conn.close()
    return render_template('read_data.html', data=data)


# Colonnes autorisées pour le tri (liste blanche)
TRIS_AUTORISES = {
    'nom': 'nom',
    'prenom': 'prenom',
    'created': 'created',
}


@app.route('/recherche')
def recherche():
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    q = request.args.get('q', '').strip()
    tri = request.args.get('tri', 'nom')
    if tri not in TRIS_AUTORISES:
        tri = 'nom'

    data = []
    if q:
        conn = get_db()
        cursor = conn.cursor()
        motif = '%' + q + '%'
        # On ne peut pas utiliser "?" pour un nom de colonne : seule une valeur
        # issue de la liste blanche est insérée dans la requête.
        requete = ('SELECT * FROM clients WHERE nom LIKE ? OR prenom LIKE ? '
                   'ORDER BY ' + TRIS_AUTORISES[tri])
        cursor.execute(requete, (motif, motif))
        data = cursor.fetchall()
        conn.close()
    return render_template('recherche.html', q=q, tri=tri, data=data)


# ---------------------------------------------------------------
#  Enregistrer, modifier, supprimer (exercices 4, 5 et 6)
# ---------------------------------------------------------------

def lire_formulaire_client():
    """Récupère et nettoie les champs du formulaire client."""
    nom = request.form.get('nom', '').strip().upper()
    prenom = request.form.get('prenom', '').strip()
    adresse = request.form.get('adresse', '').strip()
    telephone = request.form.get('telephone', '').strip() or None  # facultatif
    return nom, prenom, adresse, telephone


@app.route('/enregistrer_client', methods=['GET'])
def formulaire_client():
    if not a_le_role('admin'):
        return ACCES_REFUSE, 403

    return render_template('formulaire.html')  # afficher le formulaire


@app.route('/enregistrer_client', methods=['POST'])
def enregistrer_client():
    if not a_le_role('admin'):
        return ACCES_REFUSE, 403

    nom, prenom, adresse, telephone = lire_formulaire_client()

    if not nom or not prenom or not adresse:
        return render_template('formulaire.html',
                               erreur="Le nom, le prénom et l'adresse sont obligatoires."), 400

    # Connexion à la base de données
    conn = get_db()
    cursor = conn.cursor()

    # Exécution de la requête SQL pour insérer un nouveau client
    cursor.execute('INSERT INTO clients (nom, prenom, adresse, telephone) VALUES (?, ?, ?, ?)',
                   (nom, prenom, adresse, telephone))
    conn.commit()
    nouvel_id = cursor.lastrowid
    conn.close()
    return redirect(url_for('Readfiche', post_id=nouvel_id))


@app.route('/modifier_client/<int:id>', methods=['GET', 'POST'])
def modifier_client(id):
    if not a_le_role('admin'):
        return ACCES_REFUSE, 403

    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (id,)).fetchone()

    if client is None:
        conn.close()
        return "<h2>Client introuvable</h2>", 404

    if request.method == 'POST':
        nom, prenom, adresse, telephone = lire_formulaire_client()

        if not nom or not prenom or not adresse:
            conn.close()
            return render_template('modifier_client.html', client=client,
                                   erreur="Le nom, le prénom et l'adresse sont obligatoires."), 400

        conn.execute('UPDATE clients SET nom = ?, prenom = ?, adresse = ?, telephone = ? WHERE id = ?',
                     (nom, prenom, adresse, telephone, id))
        conn.commit()
        conn.close()
        return redirect('/consultation/')

    conn.close()
    return render_template('modifier_client.html', client=client)


@app.route('/supprimer_client/<int:id>', methods=['POST'])
def supprimer_client(id):
    if not a_le_role('admin'):
        return ACCES_REFUSE, 403

    conn = get_db()
    try:
        conn.execute('DELETE FROM clients WHERE id = ?', (id,))
        conn.commit()
    except sqlite3.IntegrityError:
        nb = conn.execute('SELECT COUNT(*) FROM commandes WHERE client_id = ?', (id,)).fetchone()[0]
        return (f'<h2>Impossible : ce client a {nb} commande(s).</h2>'
                f'<p><a href="/fiche_client/{id}">Voir sa fiche</a></p>'), 409
    finally:
        conn.close()  # exécuté dans TOUS les cas, même après le return
    return redirect('/consultation/')


# ---------------------------------------------------------------
#  Commandes et statistiques (exercice 7)
# ---------------------------------------------------------------

@app.route('/commandes/')
def liste_commandes():
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    conn = get_db()
    commandes = conn.execute('''
        SELECT commandes.id, commandes.client_id, clients.nom, clients.prenom,
               commandes.produit, commandes.montant, commandes.date_commande
        FROM commandes
        JOIN clients ON commandes.client_id = clients.id
        ORDER BY commandes.date_commande DESC, commandes.id DESC
    ''').fetchall()
    conn.close()
    return render_template('commandes.html', commandes=commandes)


@app.route('/statistiques/')
def statistiques():
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    conn = get_db()
    # LEFT JOIN : les clients sans commande apparaissent aussi
    # COALESCE : affiche 0 au lieu de NULL quand il n'y a aucune commande
    lignes = conn.execute('''
        SELECT clients.id, clients.nom, clients.prenom,
               COUNT(commandes.id) AS nb_commandes,
               COALESCE(SUM(commandes.montant), 0) AS total
        FROM clients
        LEFT JOIN commandes ON commandes.client_id = clients.id
        GROUP BY clients.id
        ORDER BY total DESC, clients.nom
    ''').fetchall()
    conn.close()
    return render_template('statistiques.html', lignes=lignes)


@app.route('/fiche_client/<int:post_id>/commande', methods=['POST'])
def ajouter_commande(post_id):
    if not a_le_role('admin'):
        return ACCES_REFUSE, 403

    produit = request.form.get('produit', '').strip()
    try:
        montant = float(request.form.get('montant', '').replace(',', '.'))
    except ValueError:
        montant = 0

    if not produit or not math.isfinite(montant) or montant <= 0:
        return (f'<h2>Indiquez un produit et un montant supérieur à 0.</h2>'
                f'<p><a href="/fiche_client/{post_id}">Retour à la fiche</a></p>'), 400

    conn = get_db()
    try:
        conn.execute('INSERT INTO commandes (client_id, produit, montant) VALUES (?, ?, ?)',
                     (post_id, produit, montant))
        conn.commit()
    except sqlite3.IntegrityError:
        return "<h2>Client introuvable</h2>", 404
    finally:
        conn.close()
    return redirect(url_for('Readfiche', post_id=post_id))


# ---------------------------------------------------------------
#  API JSON (exercice 9)
# ---------------------------------------------------------------

@app.get('/api/clients')
def api_liste_clients():
    if not a_le_role('user', 'admin'):
        return jsonify({'erreur': 'Authentification requise'}), 401

    q = request.args.get('q', '').strip()
    conn = get_db()
    if q:
        motif = '%' + q + '%'
        rows = conn.execute('SELECT * FROM clients WHERE nom LIKE ? OR prenom LIKE ? ORDER BY nom',
                            (motif, motif)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM clients ORDER BY nom').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.get('/api/clients/<int:id>')
def api_un_client(id):
    if not a_le_role('user', 'admin'):
        return jsonify({'erreur': 'Authentification requise'}), 401

    conn = get_db()
    row = conn.execute('SELECT * FROM clients WHERE id = ?', (id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({'erreur': 'Client introuvable'}), 404
    return jsonify(dict(row))


@app.post('/api/clients')
def api_creer_client():
    if not a_le_role('admin'):
        return jsonify({'erreur': 'Authentification administrateur requise'}), 401

    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        donnees = {}

    def champ(cle):
        return str(donnees.get(cle) or '').strip()

    nom = champ('nom').upper()
    prenom = champ('prenom')
    adresse = champ('adresse')
    telephone = champ('telephone') or None

    if not nom or not prenom or not adresse:
        return jsonify({'erreur': 'Les champs nom, prenom et adresse sont obligatoires'}), 400

    conn = get_db()
    cursor = conn.execute('INSERT INTO clients (nom, prenom, adresse, telephone) VALUES (?, ?, ?, ?)',
                          (nom, prenom, adresse, telephone))
    conn.commit()
    nouvel_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': nouvel_id, 'nom': nom, 'prenom': prenom,
                    'adresse': adresse, 'telephone': telephone}), 201


@app.delete('/api/clients/<int:id>')
def api_supprimer_client(id):
    if not a_le_role('admin'):
        return jsonify({'erreur': 'Authentification administrateur requise'}), 401

    conn = get_db()
    try:
        cursor = conn.execute('DELETE FROM clients WHERE id = ?', (id,))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'erreur': 'Ce client a des commandes'}), 409
    finally:
        conn.close()

    if cursor.rowcount == 0:
        return jsonify({'erreur': 'Client introuvable'}), 404
    return jsonify({'message': 'Client supprimé', 'id': id})


@app.route('/clients_js')
def clients_js():
    if not a_le_role('user', 'admin'):
        return redirect(url_for('authentification'))

    return render_template('clients_js.html')


# ---------------------------------------------------------------
#  Ne pas modifier : utile seulement pour lancer le site
#  sur votre propre ordinateur (python flask_app.py)
# ---------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
