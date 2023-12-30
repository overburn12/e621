from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests, json, os
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e621.db'
db = SQLAlchemy(app)

#generic place-holder structure for now
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text)

#generate the header for api requests
api_key = os.environ.get('API_KEY')
username = os.environ.get('USER_NAME')
auth_header = base64.b64encode(f"{username}:{api_key}".encode()).decode()
headers = {
    'User-Agent': 'e621-Favorite-Tracker/1.0 (user: overburn12)',
    'Authorization': f"Basic {auth_header}"
}

#-----------------------------------------------------------------------
# routes
#-----------------------------------------------------------------------

@app.route('/')
def main_page():
    return render_template('index.html')

@app.route('/get_new')
def fetch_recent_posts():
    url = 'https://e621.net/posts.json?limit=20'

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return jsonify(response.json())
    else:
        # Return more detailed error information
        return jsonify({
            'error': 'Failed to fetch data',
            'status_code': response.status_code,
            'response': response.text
        }), response.status_code

#-----------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    host = os.environ.get('HOST')
    port = int(os.environ.get('PORT'))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.debug = debug
    app.run(host=host, port=port)