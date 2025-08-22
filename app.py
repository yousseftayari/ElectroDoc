import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from sqlalchemy import text, or_, func
from extensions import db
from auth import auth_bp

ALL_ETATS = ['REP', 'HS', 'SWA', 'BRK']

# Initialize Flask app
app = Flask(__name__)

# Configuration must come before db.init_app
basedir = os.path.abspath(os.path.dirname(__file__))
app.config.update(
    SECRET_KEY='your-secret-key-here',
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(basedir, 'instance', 'database.db'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
app.register_blueprint(auth_bp)


# ------------------------
# Models
# ------------------------
class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    numero_dossier = db.Column(db.String(100), nullable=False, unique=True)
    numero_carton = db.Column(db.String(100), nullable=False)
    modele = db.Column(db.String(100), nullable=False)

    # lazy='dynamic' for querying states if needed
    states = db.relationship('DocumentState', backref='document', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Document {self.numero_dossier}>'

    # Optional: helper to get list of states (non-dynamic)
    def get_states(self):
        return self.states.all()


class DocumentState(db.Model):
    __tablename__ = 'document_states'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    state_type = db.Column(db.String(50), nullable=False)
    sub_state = db.Column(db.String(200))
    quantity = db.Column(db.Integer, nullable=True)

    def get_sub_states(self):
        return self.sub_state.split(',') if self.sub_state else []


# ------------------------
# Routes
# ------------------------

def is_logged_in():
    return 'user_id' in session


@app.route('/')
def home():
    return redirect(url_for('auth.login'))


@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        flash('Veuillez vous connecter pour accéder au tableau de bord.', 'error')
        return redirect(url_for('auth.login'))

    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Document.query
    if search:
        query = query.filter(
            or_(
                Document.numero_dossier.contains(search),
                Document.numero_carton.contains(search),
                Document.modele.contains(search)
            )
        )

    documents = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('index.html', documents=documents, search=search)


@app.route('/add', methods=['GET', 'POST'])
def add_document():
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        numero_dossier = request.form['numero_dossier'].strip()
        numero_carton = request.form['numero_carton'].strip()
        modele = request.form['modele'].strip()

        if not numero_dossier or not numero_carton or not modele:
            flash('Veuillez remplir tous les champs obligatoires!', 'error')
            return redirect(url_for('add_document'))

        if Document.query.filter_by(numero_dossier=numero_dossier).first():
            flash('Un document avec ce numéro de dossier existe déjà!', 'error')
            return redirect(url_for('add_document'))

        new_document = Document(numero_dossier=numero_dossier, numero_carton=numero_carton, modele=modele)
        db.session.add(new_document)
        db.session.flush()

        states = request.form.getlist('etats')
        quantities = request.form.getlist('quantities')

        for i, state_type in enumerate(states):
            quantity = int(quantities[i]) if i < len(quantities) and quantities[i].isdigit() else 1
            sub_states = request.form.getlist(f'sub_states_{i}') if state_type == 'BRK' else []
            sub_state_str = ",".join(sub_states) if sub_states else None

            db.session.add(DocumentState(
                document_id=new_document.id,
                state_type=state_type,
                sub_state=sub_state_str,
                quantity=quantity
            ))

        db.session.commit()
        flash('Document ajouté avec succès!', 'success')
        return redirect(url_for('dashboard'))

    etats = [{'id': etat, 'nom': etat} for etat in ALL_ETATS]
    return render_template('add_document.html', etats=etats)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_document(id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    document = Document.query.get_or_404(id)

    if request.method == 'POST':
        document.numero_dossier = request.form['numero_dossier'].strip()
        document.numero_carton = request.form['numero_carton'].strip()
        document.modele = request.form['modele'].strip()

        DocumentState.query.filter_by(document_id=id).delete()

        states = request.form.getlist('etats')
        quantities = request.form.getlist('quantities')

        for i, state_type in enumerate(states):
            quantity = int(quantities[i]) if i < len(quantities) and quantities[i].isdigit() else 1
            sub_states = request.form.getlist(f'sub_states_{i}') if state_type == 'BRK' else []
            sub_state_str = ",".join(sub_states) if sub_states else None

            db.session.add(DocumentState(
                document_id=id,
                state_type=state_type,
                sub_state=sub_state_str,
                quantity=quantity
            ))

        db.session.commit()
        flash('Document modifié avec succès!', 'success')
        return redirect(url_for('dashboard'))

    etats = [{'id': etat, 'nom': etat} for etat in ALL_ETATS]
    selected_etats = [state.state_type for state in document.states]

    return render_template('edit_document.html', document=document, etats=etats, selected_etats=selected_etats)


@app.route('/delete/<int:id>', methods=['POST'])
def delete_document(id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    document = Document.query.get_or_404(id)
    db.session.delete(document)
    db.session.commit()
    flash('Document supprimé avec succès!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/document/<int:doc_id>/add_state', methods=['POST'])
def add_document_state(doc_id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    data = request.get_json()
    Document.query.get_or_404(doc_id)

    new_state = DocumentState(
        document_id=doc_id,
        state_type=data.get('state_type'),
        sub_state=data.get('sub_state'),
        quantity=data.get('quantity', 1)
    )

    db.session.add(new_state)
    db.session.commit()
    return jsonify({'success': True, 'message': 'État ajouté avec succès'})


@app.route('/state/<int:state_id>/delete', methods=['POST'])
def delete_document_state(state_id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    state = DocumentState.query.get_or_404(state_id)
    db.session.delete(state)
    db.session.commit()
    return jsonify({'success': True, 'message': 'État supprimé avec succès'})


@app.route('/tables')
def list_tables():
    with db.engine.connect() as connection:
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        table_names = [row[0] for row in result]
    return f"Tables dans la base de données: {', '.join(table_names)}"


@app.route('/stats')
def stats():
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    total_documents = Document.query.count()
    total_states = DocumentState.query.count()
    documents_by_dossier = db.session.query(
        Document.numero_dossier, func.count(Document.id)
    ).group_by(Document.numero_dossier).all()

    return render_template('stats.html',
                           total_documents=total_documents,
                           total_states=total_states,
                           documents_by_dossier=documents_by_dossier)


# ------------------------
# Initialize & add sample data
# ------------------------
if __name__ == '__main__':
    instance_path = os.path.join(basedir, 'instance')
    os.makedirs(instance_path, exist_ok=True)

    with app.app_context():
        db.create_all()

        if Document.query.count() == 0:
            sample_docs = [
                Document(numero_dossier='Dossier001', numero_carton='CartonA', modele='ModelX'),
                Document(numero_dossier='Dossier002', numero_carton='CartonB', modele='ModelY'),
                Document(numero_dossier='Dossier003', numero_carton='CartonC', modele='ModelZ'),
            ]
            db.session.bulk_save_objects(sample_docs)
            db.session.commit()

            sample_states = [
                DocumentState(document_id=1, state_type='REP', quantity=5),
                DocumentState(document_id=1, state_type='HS', quantity=2),
                DocumentState(document_id=2, state_type='SWA', quantity=4),
                DocumentState(document_id=3, state_type='BRK', sub_state='KC', quantity=1),
                DocumentState(document_id=3, state_type='BRK', sub_state='Ill', quantity=1),
            ]
            db.session.bulk_save_objects(sample_states)
            db.session.commit()

    app.run(debug=True)
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from sqlalchemy import text, or_, func
from flask_cors import CORS
from extensions import db
from auth import auth_bp

ALL_ETATS = ['REP', 'HS', 'SWA', 'BRK']

# Initialize Flask app
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Configuration must come before db.init_app
basedir = os.path.abspath(os.path.dirname(__file__))
app.config.update(
    SECRET_KEY='your-secret-key-here',
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(basedir, 'instance', 'database.db'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
app.register_blueprint(auth_bp)


# ------------------------
# Models
# ------------------------
class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    numero_dossier = db.Column(db.String(100), nullable=False, unique=True)
    numero_carton = db.Column(db.String(100), nullable=False)
    modele = db.Column(db.String(100), nullable=False)

    states = db.relationship('DocumentState', backref='document', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Document {self.numero_dossier}>'

    def to_dict(self):
        return {
            'id': self.id,
            'numero_dossier': self.numero_dossier,
            'numero_carton': self.numero_carton,
            'modele': self.modele,
            'states': [state.to_dict() for state in self.states]
        }


class DocumentState(db.Model):
    __tablename__ = 'document_states'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    state_type = db.Column(db.String(50), nullable=False)
    sub_state = db.Column(db.String(200))
    quantity = db.Column(db.Integer, nullable=True)

    def get_sub_states(self):
        return self.sub_state.split(',') if self.sub_state else []
    
    def to_dict(self):
        return {
            'id': self.id,
            'state_type': self.state_type,
            'sub_state': self.sub_state,
            'quantity': self.quantity
        }


# ------------------------
# Traditional Flask Routes (for server-side rendering, if needed)
# ------------------------
def is_logged_in():
    return 'user_id' in session

@app.route('/')
def home():
    return redirect(url_for('auth.login'))

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        flash('Veuillez vous connecter pour accéder au tableau de bord.', 'error')
        return redirect(url_for('auth.login'))

    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Document.query
    if search:
        query = query.filter(
            or_(
                Document.numero_dossier.contains(search),
                Document.numero_carton.contains(search),
                Document.modele.contains(search)
            )
        )

    documents = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('index.html', documents=documents, search=search)

@app.route('/add', methods=['GET', 'POST'])
def add_document():
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        numero_dossier = request.form['numero_dossier'].strip()
        numero_carton = request.form['numero_carton'].strip()
        modele = request.form['modele'].strip()

        if not numero_dossier or not numero_carton or not modele:
            flash('Veuillez remplir tous les champs obligatoires!', 'error')
            return redirect(url_for('add_document'))

        if Document.query.filter_by(numero_dossier=numero_dossier).first():
            flash('Un document avec ce numéro de dossier existe déjà!', 'error')
            return redirect(url_for('add_document'))

        new_document = Document(numero_dossier=numero_dossier, numero_carton=numero_carton, modele=modele)
        db.session.add(new_document)
        db.session.flush()

        states = request.form.getlist('etats')
        quantities = request.form.getlist('quantities')

        for i, state_type in enumerate(states):
            quantity = int(quantities[i]) if i < len(quantities) and quantities[i].isdigit() else 1
            sub_states = request.form.getlist(f'sub_states_{i}') if state_type == 'BRK' else []
            sub_state_str = ",".join(sub_states) if sub_states else None

            db.session.add(DocumentState(
                document_id=new_document.id,
                state_type=state_type,
                sub_state=sub_state_str,
                quantity=quantity
            ))

        db.session.commit()
        flash('Document ajouté avec succès!', 'success')
        return redirect(url_for('dashboard'))

    etats = [{'id': etat, 'nom': etat} for etat in ALL_ETATS]
    return render_template('add_document.html', etats=etats)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_document(id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    document = Document.query.get_or_404(id)

    if request.method == 'POST':
        document.numero_dossier = request.form['numero_dossier'].strip()
        document.numero_carton = request.form['numero_carton'].strip()
        document.modele = request.form['modele'].strip()

        DocumentState.query.filter_by(document_id=id).delete()

        states = request.form.getlist('etats')
        quantities = request.form.getlist('quantities')

        for i, state_type in enumerate(states):
            quantity = int(quantities[i]) if i < len(quantities) and quantities[i].isdigit() else 1
            sub_states = request.form.getlist(f'sub_states_{i}') if state_type == 'BRK' else []
            sub_state_str = ",".join(sub_states) if sub_states else None

            db.session.add(DocumentState(
                document_id=id,
                state_type=state_type,
                sub_state=sub_state_str,
                quantity=quantity
            ))

        db.session.commit()
        flash('Document modifié avec succès!', 'success')
        return redirect(url_for('dashboard'))

    etats = [{'id': etat, 'nom': etat} for etat in ALL_ETATS]
    selected_etats = [state.state_type for state in document.states]

    return render_template('edit_document.html', document=document, etats=etats, selected_etats=selected_etats)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_document(id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    document = Document.query.get_or_404(id)
    db.session.delete(document)
    db.session.commit()
    flash('Document supprimé avec succès!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/document/<int:doc_id>/add_state', methods=['POST'])
def add_document_state(doc_id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    data = request.get_json()
    Document.query.get_or_404(doc_id)

    new_state = DocumentState(
        document_id=doc_id,
        state_type=data.get('state_type'),
        sub_state=data.get('sub_state'),
        quantity=data.get('quantity', 1)
    )

    db.session.add(new_state)
    db.session.commit()
    return jsonify({'success': True, 'message': 'État ajouté avec succès'})


@app.route('/state/<int:state_id>/delete', methods=['POST'])
def delete_document_state(state_id):
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    state = DocumentState.query.get_or_404(state_id)
    db.session.delete(state)
    db.session.commit()
    return jsonify({'success': True, 'message': 'État supprimé avec succès'})


@app.route('/tables')
def list_tables():
    with db.engine.connect() as connection:
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        table_names = [row[0] for row in result]
    return f"Tables dans la base de données: {', '.join(table_names)}"

@app.route('/stats')
def stats():
    if not is_logged_in():
        return redirect(url_for('auth.login'))

    total_documents = Document.query.count()
    total_states = DocumentState.query.count()
    documents_by_dossier = db.session.query(
        Document.numero_dossier, func.count(Document.id)
    ).group_by(Document.numero_dossier).all()

    return render_template('stats.html',
                            total_documents=total_documents,
                            total_states=total_states,
                            documents_by_dossier=documents_by_dossier)


# ------------------------
# API Routes for Angular
# ------------------------
@app.route('/api/documents', methods=['GET'])
def get_documents():
    query = Document.query
    search = request.args.get('search', '').strip()
    
    if search:
        query = query.filter(
            or_(
                Document.numero_dossier.contains(search),
                Document.numero_carton.contains(search),
                Document.modele.contains(search)
            )
        )
    
    documents = query.all()
    
    # Use list comprehension to serialize documents using the to_dict method
    documents_list = [doc.to_dict() for doc in documents]
        
    return jsonify(documents_list)


# ------------------------
# Initialize & add sample data
# ------------------------
if __name__ == '__main__':
    instance_path = os.path.join(basedir, 'instance')
    os.makedirs(instance_path, exist_ok=True)

    with app.app_context():
        db.create_all()

        if Document.query.count() == 0:
            sample_docs = [
                Document(numero_dossier='Dossier001', numero_carton='CartonA', modele='ModelX'),
                Document(numero_dossier='Dossier002', numero_carton='CartonB', modele='ModelY'),
                Document(numero_dossier='Dossier003', numero_carton='CartonC', modele='ModelZ'),
            ]
            db.session.bulk_save_objects(sample_docs)
            db.session.commit()

            sample_states = [
                DocumentState(document_id=1, state_type='REP', quantity=5),
                DocumentState(document_id=1, state_type='HS', quantity=2),
                DocumentState(document_id=2, state_type='SWA', quantity=4),
                DocumentState(document_id=3, state_type='BRK', sub_state='KC', quantity=1),
                DocumentState(document_id=3, state_type='BRK', sub_state='Ill', quantity=1),
            ]
            db.session.bulk_save_objects(sample_states)
            db.session.commit()

    app.run(debug=True)