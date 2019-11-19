import random
import requests
import string
import time
import json

from flask import Flask
from flask import request, redirect
app = Flask(__name__)

users = {}

with open('config.json') as conf_j:
    conf = json.load(conf_j)

@app.route('/register')
def reg():
    uid = int(request.args.get('uid'))
    if not uid:
        return("""Invalid Parameters.""")
    state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    users[state] = uid
    return redirect(f"https://www.bungie.net/en/oauth/authorize?client_id=30852&response_type=code&state={state}")

@app.route('/callback')
def homepage():
    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state or state not in users:
        return """Invalid Parameters."""
    uid = users[state]
    resp = requests.post("https://www.bungie.net/platform/app/oauth/token/",
                         headers={'Content-Type': 'application/x-www-form-urlencoded'},
                         data={'grant_type': 'authorization_code',
                               'code': code,
                               'client_id': 30852,
                               'client_secret': conf['secret']})
    access = resp.json()
    with open('users.json', 'r') as users_js:
        try:
            users_db = json.load(users_js)
        except:
            users_db = {}

    if uid not in users_db:
        users_db[uid] = {}
    users_db[uid]['token'] = access['access_token']
    users_db[uid]['expires_at'] = time.time() + access['expires_in']
    users_db[uid]['refresh_token'] = access['refresh_token']
    users_db[uid]['refresh_expires_at'] = time.time() + access['refresh_expires_in']
    users_db[uid]['member_id'] = access['membership_id']

    with open('users.json', 'w') as users_js:
        json.dump(users_db, users_js)

    return """Authorized! You are registered on Randy and can safely close this window."""

def run():
    app.run()
