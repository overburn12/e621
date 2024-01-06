from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
import requests, json, os
import base64
import time
from dotenv import load_dotenv
from sqlalchemy.sql import text

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e621.db'
db = SQLAlchemy(app)

class ViewedList(db.Model):
    image_id = db.Column(db.Integer, primary_key=True)
    is_favorited = db.Column(db.Boolean)
    is_viewed = db.Column(db.Boolean)
    my_vote = db.Column(db.Integer)
    created_at = db.Column(db.String(50))
    tags = db.relationship('Tag', secondary='image_tag', back_populates='images')
    community_stats = db.relationship('CommunityStats', uselist=False, back_populates='viewed_image')

class Tag(db.Model):
    tag_id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String, nullable=False)
    tag_type = db.Column(db.String, nullable=False)  
    images = db.relationship('ViewedList', secondary='image_tag', back_populates='tags')

class CommunityStats(db.Model):
    image_id = db.Column(db.Integer, db.ForeignKey('viewed_list.image_id'), primary_key=True)
    rating = db.Column(db.String(1), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    fav_count = db.Column(db.Integer, nullable=False)
    up_votes = db.Column(db.Integer, nullable=False)
    down_votes = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Integer, nullable=False)
    comment_count = db.Column(db.Integer, nullable=False)
    viewed_image = db.relationship('ViewedList', back_populates='community_stats')

image_tag = db.Table('image_tag',
    db.Column('image_id', db.Integer, db.ForeignKey('viewed_list.image_id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.tag_id'), primary_key=True)
)

#-----------------------------------------------------------------------

page_size = 100

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

def get_api_response(method, endpoint, args_list):
    #time sync, wait at least 1 second between api requests
    if not hasattr(get_api_response, "last_request_time"):
        get_api_response.last_request_time = 0
    current_time = time.time()
    time_since_last_request = current_time - get_api_response.last_request_time

    #wait if it has been less than 1 second since the last request
    if time_since_last_request < 1:
        wait_time = int((1 - time_since_last_request) * 1000)
        print(f"Rate limit exceeded. Waiting {wait_time} ms.")
        time.sleep(1 - time_since_last_request)

    #generate the request url with query arguments
    request_url = endpoint
    if len(args_list) > 0:
        request_url += '?'
    for index, arg in enumerate(args_list):
        request_url += arg
        if index != len(args_list) - 1:
            request_url += '&'

    #generate the api response
    response = None
    if method.lower() == 'get':
        response = requests.get('https://e621.net/' + request_url, headers=headers)
    elif method.lower() == 'post':
        response = requests.post('https://e621.net/' + request_url, headers=headers)
    elif method.lower() == 'delete':
        response = requests.delete('https://e621.net/' + request_url, headers=headers)
    else:
        print ("Method {method} invalid at get_api_response()")
        return {"error": "Method {method} invalid"}

    #mark the time
    get_api_response.last_request_time = time.time()
    return response
    
#-----------------------------------------------------------------------
# functions
#-----------------------------------------------------------------------

def filter_results(response_json):
    for post in response_json['posts']:
        post_id = post['id']
        is_favorited = post['is_favorited']
        created_at = post['created_at']
        tags = post['tags']
        my_vote = 0 
        is_hidden = False
        viewed_image = db.session.get(ViewedList, post_id)
        if not viewed_image:
            viewed_image = ViewedList(image_id=post_id, created_at=created_at, is_favorited=is_favorited, is_viewed=False, my_vote=0)
            db.session.add(viewed_image)
        else:
            ##if no post.score.my_vote is present, then the front end assumes this has never been seen before.
            my_vote = viewed_image.my_vote
            is_hidden = viewed_image.is_viewed
            #inject some db data fields for the front end
            post['score']['my_vote'] = my_vote
            post['is_hidden'] = is_hidden
        image_stats = CommunityStats(
            image_id=post_id, 
            rating=post['rating'], 
            type=post['file']['ext'],
            fav_count=post['fav_count'], 
            up_votes=post['score']['up'], 
            down_votes=post['score']['up'], 
            total_score=post['score']['total'],
            comment_count=post['comment_count']
        )
        process_stats(image_stats)
        process_tags(tags, viewed_image)
    db.session.commit()

def process_stats(image_stats):
    existing_entry = CommunityStats.query.get(image_stats.image_id)
    if existing_entry:
        existing_entry.rating = image_stats.rating
        existing_entry.type = image_stats.type
        existing_entry.fav_count = image_stats.fav_count
        existing_entry.up_votes = image_stats.up_votes
        existing_entry.down_votes = image_stats.down_votes
        existing_entry.total_score = image_stats.total_score
        existing_entry.comment_count = image_stats.comment_count
    else:
        db.session.add(image_stats)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"process_stats: Error: {e}")
          
def process_tags(tags, viewed_image):
    # Convert the current tags to a set for easier comparison
    current_tags = set((tag.tag_name, tag.tag_type) for tag in viewed_image.tags)
    # Convert the new tags to a set
    new_tags = set()
    for tag_type, tag_list in tags.items():
        for tag_name in tag_list:
            new_tags.add((tag_name, tag_type))
    tags_to_add = new_tags - current_tags
    tags_to_remove = current_tags - new_tags
    # Process removals
    for tag_name, tag_type in tags_to_remove:
        tag = Tag.query.filter_by(tag_name=tag_name, tag_type=tag_type).first()
        if tag:
            viewed_image.tags.remove(tag)
    # Process additions
    for tag_name, tag_type in tags_to_add:
        tag = Tag.query.filter_by(tag_name=tag_name, tag_type=tag_type).first()
        if not tag:
            tag = Tag(tag_name=tag_name, tag_type=tag_type)
            db.session.add(tag)
        viewed_image.tags.append(tag)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"proccess_tags: Error: {e}")

def set_vote(image_id, vote_score):
    try:
        entry = db.session.query(ViewedList).filter_by(image_id=image_id).first()
        if entry:
            entry.my_vote = vote_score
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"set_vote: Error: {e}")

def set_hidden(image_id, is_hidden):
    entry = db.session.query(ViewedList).filter_by(image_id=image_id).first()
    if entry:
        entry.is_viewed = is_hidden
        db.session.commit()
        return True
    else:
        return False
    
def get_community_stats_entry(image_id):
    entry = CommunityStats.query.get(image_id)
    if entry:
        return entry
    else:
        return f"No entry found for image_id {image_id}"

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

    if page_num:
        args_list.append(f'page={page_num}')
    if search_tags:
        args_list.append(f'tags={search_tags}')
    if page_size:
        args_list.append(f'limit={page_size}')

    response = get_api_response('GET', 'posts.json', args_list)
    response_json = response.json()
    
    if response.status_code == 200:
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
    post_id = request.args.get('post_id')
    edit_type = request.args.get('type')

    if not post_id: 
        return jsonify({"error": "post_id argument missing"})
    if not edit_type:
        return jsonify({"error": "type argument missing"})
    
    if edit_type == 'add':
        args_list = [f'post_id={post_id}']
        response = get_api_response('POST', 'favorites.json', args_list)
        return "key_facts"
    elif edit_type == 'delete':
        response = get_api_response('DELETE', f'favorites/{post_id}.json', [''])
        if not response.content:
            return "key_facts"
        else:
            return jsonify(response.json())
    else:
        jsonify({"error": "type argument invalid"})
    
@app.route('/vote')
def vote_route():
    score_id = request.args.get('score')
    no_unvote = request.args.get('no_unvote')
    post_id = request.args.get('post_id')
    args_list = [f'score={score_id}']
    if no_unvote:
        args_list.append(f'no_unvote={no_unvote}')

    response = get_api_response('POST', f'posts/{post_id}/votes.json', args_list)

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
    
@app.route('/hide')
def set_hidden_route():
    post_id = request.args.get('post_id')
    is_hidden = request.args.get('is_hidden', type=bool)

    if post_id is None or is_hidden is None:
        return jsonify({"error": "Missing post_id or is_hidden parameter"}), 400

    success = set_hidden(post_id, is_hidden)
    return jsonify({"success": success})
    
@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

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
    return render_template("sql.html")

@app.route('/sql', methods=['POST'])
def execute_query():
    query_data = request.get_json()
    query = text(query_data['query'])

    try:
        with db.engine.connect() as connection:
            result_data = connection.execute(query)
            rows = result_data.fetchall()
            columns = list(result_data.keys())

        result = {
            'columns': columns,
            'rows': [dict(zip(columns, row)) for row in rows]
        }

    except Exception as e:
        # Rolling back in case of error
        db.session.rollback()
        result = {'error': str(e)}

    return jsonify(result)

#-----------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    host = os.environ.get('HOST')
    port = int(os.environ.get('PORT'))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.debug = debug
    app.run(host=host, port=port)