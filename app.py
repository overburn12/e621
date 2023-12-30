from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import requests, json, os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e621.db'
db = SQLAlchemy(app)

class Entry(db.Model):
    #generic place-holder structure for now
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text)

@app.route('/')
def main_page():
    return render_template('index.html')

def get_api_response(url):
    # Send an API request to the server and get the JSON object in return
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    host = os.environ.get('HOST')
    port = int(os.environ.get('PORT'))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.debug = debug
    app.run(host=host, port=port)