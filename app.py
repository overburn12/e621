from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file
from sqlalchemy.sql import text
import json, os
from dotenv import load_dotenv

#modules
from database import init_db, filter_results, set_vote, set_favorite, raw_query
from e621api import e621_api, e621_auth

app = Flask(__name__)
load_dotenv()
username = os.environ.get('USER_NAME')
api_key = os.environ.get('API_KEY')
use_db = os.environ.get('USE_DB', True).lower() == 'true'
e621_auth(username, api_key)
    
page_size = 250

if use_db:
    init_db(app)

#-----------------------------------------------------------------------
# routes
#-----------------------------------------------------------------------

@app.route('/')
def main_page():
    return redirect(url_for('search_function'))

@app.route('/artists')
def artists_page():
    return render_template("artists.html")

@app.route('/search')
def search_function():
    tags = request.args.get('tags')
    return render_template('index.html', tags=tags)

@app.route('/list', methods=['GET'])
def fetch_recent_posts():
    args_list = []
    page_num = request.args.get('page')
    search_tags = request.args.get('tags')
    limit = request.args.get('limit')

    if page_num:
        args_list.append(f'page={page_num}')
    if search_tags:
        args_list.append(f'tags={search_tags}')
    if limit:
        args_list.append(f'limit={limit}')
    else:
        if page_size:
            args_list.append(f'limit={page_size}')

    response = e621_api('GET', 'posts.json', args_list)
    response_json = response.json()
    
    if response.status_code == 200:
        if use_db:
            filter_results(response_json)
        return jsonify(response_json)
    else:
        return jsonify({
            'error': 'Failed to fetch data',
            'status_code': response.status_code,
            'response': response.text
        }), response.status_code
    
@app.route('/fav')
def set_fav():
    if not use_db:
        return jsonify({"error": "db not used"})
    
    post_id = request.args.get('post_id')
    edit_type = request.args.get('type')

    if not post_id: 
        return jsonify({"error": "post_id argument missing"})
    if not edit_type:
        return jsonify({"error": "type argument missing"})
    
    if edit_type == 'add':
        args_list = [f'post_id={post_id}']
        response = e621_api('POST', 'favorites.json', args_list)
        set_favorite(post_id, True)
        return "key_facts"
    elif edit_type == 'delete':
        response = e621_api('DELETE', f'favorites/{post_id}.json', [''])
        if not response.content:
            set_favorite(post_id, False)
            return "key_facts"
        else:
            return jsonify(response.json())
    else:
        jsonify({"error": "type argument invalid"})
    
@app.route('/vote')
def vote_route():
    if not use_db:
        return jsonify({"error": "db not used"})
    
    score_id = request.args.get('score')
    no_unvote = request.args.get('no_unvote')
    post_id = request.args.get('post_id')
    args_list = [f'score={score_id}']
    if no_unvote:
        args_list.append(f'no_unvote={no_unvote}')

    response = e621_api('POST', f'posts/{post_id}/votes.json', args_list)

    if response.status_code == 200:
        response_json = response.json()
        required_keys = ['up', 'down', 'score', 'our_score']
        if all(key in response_json for key in required_keys):
            our_score = response_json['our_score']
            set_vote(post_id, our_score)
            return jsonify(response_json)
        else:
            return jsonify({'error': 'Response JSON is missing one or more required keys'}), 500
    else:
        error_message = f'Error: Received status code {response.status_code}'
        print(error_message)
        return jsonify({'error': error_message}), response.status_code
        
@app.route('/favicon.ico')
def favicon():
    return send_file('static/favicon.ico', mimetype='image/vnd.microsoft.icon')

ARTIST_FILE = 'data/artists.json'

@app.route('/artists_list', methods=['GET'])
def get_artists():
    try:
        with open(ARTIST_FILE, 'r') as file:
            artist_list = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        artist_list = []
    return jsonify(artist_list)

@app.route('/artists_list', methods=['PUT'])
def update_artists():
    artist_list = request.get_json()
    if not isinstance(artist_list, list):
        return "Invalid data format", 400

    try:
        with open(ARTIST_FILE, 'w') as file:
            json.dump(artist_list, file)
    except IOError:
        return "Error writing to file", 500

    return "Artist list updated", 200

@app.route('/sql', methods=['GET'])
def sql_page():
    if not use_db:
        return jsonify({"error": "db not used"})
    return render_template("sql.html")

@app.route('/sql', methods=['POST'])
def execute_query():
    if not use_db:
        return jsonify({"error": "db not used"})
    query_data = request.get_json()
    query = text(query_data['query'])
    result = raw_query(query)
    return jsonify(result)

#-----------------------------------------------------------------------

if __name__ == '__main__':
    host = os.environ.get('HOST')
    port = int(os.environ.get('PORT'))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.debug = debug
    app.run(host=host, port=port)