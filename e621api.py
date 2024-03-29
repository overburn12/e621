import base64
import time
import requests

def e621_auth(username, api_key, e6_uri = 'https://e621.net/'):
    auth_header = base64.b64encode(f"{username}:{api_key}".encode()).decode()
    e621_api.headers = {
        'User-Agent': f"e621-Favorite-Tracker/1.0 (user: {username})",
        'Authorization': f"Basic {auth_header}"
    }
    e621_api.uri = e6_uri

def e621_api(method, endpoint, args_list, wait_time = 1):
    if not hasattr(e621_api, 'headers'):
        print('Error: Username and API Key missing')
        return {"error": "Username and API Key missing"}
    
    if not hasattr(e621_api, "last_request_time"):
        e621_api.last_request_time = 0

    # Rate limiting check
    time_since_last_request = time.time() - e621_api.last_request_time
    if time_since_last_request < wait_time:
        sleep_time = (wait_time - time_since_last_request)
        #print(f"Rate limit exceeded. Waiting {sleep_time * 1000:.0f} ms.")
        time.sleep(sleep_time)

    # Construct request URL
    request_url = e621_api.uri + endpoint
    if args_list:
        request_url += '?' + '&'.join(args_list)

    # Mapping of methods to request functions
    request_methods = {
        'get': requests.get,
        'post': requests.post,
        'delete': requests.delete
    }

    # Get the request function based on the method, or handle invalid method
    request_function = request_methods.get(method.lower())
    if not request_function:
        print(f"Method {method} invalid")
        return {"error": f"Method {method} invalid"}

    # Make the API request
    response = request_function(request_url, headers=e621_api.headers)
    e621_api.last_request_time = time.time()
    return response


