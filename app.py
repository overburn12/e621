from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import requests, json, os
import base64
import time
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e621.db'
db = SQLAlchemy(app)

class ViewedList(db.Model):
    image_id = db.Column(db.String, primary_key=True) 

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
    if time_since_last_request < 1:
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
    filtered_return = {'posts': []}

    for post in response_json['posts']:
        filtered_return['posts'].append(post)

    return filtered_return
        
#-----------------------------------------------------------------------
# routes
#-----------------------------------------------------------------------

@app.route('/')
def main_page():
    return redirect(url_for('search_function'))

@app.route('/search')
def search_function():
    tags = request.args.get('tags')
    return render_template('index.html', tags=tags)

@app.route('/list', methods = ['GET'])
def fetch_recent_posts():
    if request.method == 'POST':
        return jsonify({"error": "GET method required for /list"})

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

    if response.status_code == 200:
        filtered_results = filter_results(response.json())
        return jsonify(filtered_results)
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

    if request.method == 'GET':
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
    else:
        return jsonify({"error": "POST method required for favorites.json"})
    
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

#-----------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    host = os.environ.get('HOST')
    port = int(os.environ.get('PORT'))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.debug = debug
    app.run(host=host, port=port)