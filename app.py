from flask import Flask, render_template, jsonify, request
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

#-----------------------------------------------------------------------
# API header
#-----------------------------------------------------------------------

api_key = os.environ.get('API_KEY')
username = os.environ.get('USER_NAME')
auth_header = base64.b64encode(f"{username}:{api_key}".encode()).decode()
headers = {
    'User-Agent': f"e621-Favorite-Tracker/1.0 (user: {username})",
    'Authorization': f"Basic {auth_header}"
}

#-----------------------------------------------------------------------
# API timer
#-----------------------------------------------------------------------

import time

def get_api_response(request_url):
    if not hasattr(get_api_response, "last_request_time"):
        get_api_response.last_request_time = 0

    current_time = time.time()
    time_since_last_request = current_time - get_api_response.last_request_time

    if time_since_last_request < 1:
        time.sleep(1 - time_since_last_request)

    response = requests.get('https://e621.net/' + request_url, headers=headers)
    get_api_response.last_request_time = time.time()

    return response
    
#-----------------------------------------------------------------------
# functions
#-----------------------------------------------------------------------

def filter_results(response_json):
    filtered_return = {'posts': []}

    for post in response_json['posts']:
        filtered_return['posts'].append(post)

    return filtered_return
#-----------------------------------------------------------------------
# routes
#-----------------------------------------------------------------------

@app.route('/')
def main_page():
    return render_template('index.html')

@app.route('/get_new')
def fetch_recent_posts():
    before_id = request.args.get('before')
    page_size = 300
    request_url = f'posts.json?limit={page_size}'

    if before_id:
        request_url += f'&page=b{before_id}'


    response = get_api_response(request_url)
    response_json = response.json()

    if response.status_code == 200:
        filtered_results = filter_results(response_json)
        return jsonify(filtered_results)
    else:
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