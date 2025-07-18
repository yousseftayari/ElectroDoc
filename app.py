import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text  # Importer du « texte » pour les requêtes SQL brutes

# --- Flask App Configuration ---
app = Flask(__name__)

# Configure SQLite database
# Le fichier de base de données sera stocké dans le dossier « instance »
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Désactiver le suivi des modifications pour les performances

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# --- Database Model Definition ---
# Ceci définit la structure de votre table


class Document(db.Model):
    # Optional: Explicitly name the table if you prefer something other than Flask-SQLAlchemy's default pluralization
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)  # Auto-incrementing primary key
    numero_dossier = db.Column(db.String(100), nullable=False, unique=True)
    numero_carton = db.Column(db.String(100), nullable=False)
    modele = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Document {self.numero_dossier}>' 


@app.route('/')
def index():
    """Displays all documents from the table."""
    documents = Document.query.all()
    return render_template('index.html', documents=documents)


@app.route('/add', methods=['GET', 'POST'])
def add_document():
    """Handles adding new documents to the table."""
    if request.method == 'POST':
        numero_dossier = request.form['numero_dossier']
        numero_carton = request.form['numero_carton']
        modele = request.form['modele']
        state = request.form['state']

 
        if not numero_dossier or not numero_carton or not modele or not state:
            return "Please fill in all fields!", 400

        
        existing_doc = Document.query.filter_by(numero_dossier=numero_dossier).first()
        if existing_doc:
            return "Document with this 'numero_dossier' already exists!", 409

        new_document = Document(
            numero_dossier=numero_dossier,
            numero_carton=numero_carton,
            modele=modele,
            state=state,
        )
        db.session.add(new_document)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_document.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_document(id):
    """Handles editing an existing document."""
    document = Document.query.get_or_404(id)
    if request.method == 'POST':
        document.numero_dossier = request.form['numero_dossier']
        document.numero_carton = request.form['numero_carton']
        document.modele = request.form['modele']
        document.state = request.form['state']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit_document.html', document=document)


@app.route('/delete/<int:id>', methods=['POST'])
def delete_document(id):
    """Handles deleting a document."""
    document = Document.query.get_or_404(id)
    db.session.delete(document)
    db.session.commit()
    return redirect(url_for('index'))
@app.route('/tables')
def list_tables():
    """Fetches and displays all table names in the SQLite database."""
    with db.engine.connect() as connection:
  
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        table_names = [row[0] for row in result]

if __name__ == '__main__':
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))
        print(f"Created 'instance' directory: {os.path.join(basedir, 'instance')}")

    with app.app_context():
        db.create_all()
        print("Database initialized or already exists (tables created if missing).")

        if Document.query.count() == 0:
            print("Adding sample data to the 'documents' table...")
            sample_docs = [
                Document(numero_dossier='Dossier001', numero_carton='CartonA', modele='ModelX', state='Active'),
                Document(numero_dossier='Dossier002', numero_carton='CartonB', modele='ModelY', state='Archived'),
                Document(numero_dossier='Dossier003', numero_carton='CartonC', modele='ModelZ', state='En attente'),
            ]
            db.session.bulk_save_objects(sample_docs) 
            db.session.commit()  
            print(f"Successfully added {len(sample_docs)} sample documents.")
        else:
            print("Documents table already contains data. Skipping sample data insertion.")
            app.run(debug=True)
