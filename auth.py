from flask import Blueprint, request, redirect, render_template, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

auth_bp = Blueprint('auth', __name__)

# Modèle utilisateur
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        if not username or not password:
            flash('Veuillez remplir tous les champs.', 'error')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('Nom d’utilisateur déjà pris.', 'error')
            return redirect(url_for('auth.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Compte créé avec succès. Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash('Nom d’utilisateur ou mot de passe incorrect.', 'error')
            return redirect(url_for('auth.login'))

        session['user_id'] = user.id
        flash('Connexion réussie.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Vous avez été déconnecté.', 'success')
    return redirect(url_for('auth.login'))
