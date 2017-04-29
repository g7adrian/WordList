"""`main` is the top level module for your Flask application."""
from __future__ import print_function # In python 2.7
import json
import sys
from google.appengine.ext import ndb

# Import the Flask Framework
from flask import Flask, request, make_response
app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.


class GoogleUser(ndb.Model):
    """A Google Home user. The key name is the user id"""
    pass

class Word(ndb.Model):
    """A word to be learned. The key name is the word itself"""
    learned = ndb.BooleanProperty()
    definition = ndb.StringProperty(indexed=False)


@app.route('/apiai', methods=['POST'])
def apiai_webhook():
    """Processes Api.ai webhooks"""
    req = request.get_json(silent=True, force=True)

    print('Request:', file=sys.stderr)
    print(json.dumps(req, indent=4), file=sys.stderr)

    res = make_webhook_result(req)

    res = json.dumps(res, indent=4)
    print('Response:', file=sys.stderr)
    print(res, file=sys.stderr)
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r


def make_webhook_result(req):
    action = req.get('result').get('action')
    parameters = req.get('result').get('parameters')    
    speech = process_action(action, parameters)

    return {
        'speech': speech,
        'displayText': speech,
        #"data": {},
        # "contextOut": [],
        'source': 'apiai-wordlist'
    }


def process_action(action, params):
    """Processes an action with the parameters dictionary, and returns
    the speech reply to be spoken to the user."""
    if action == 'define_word':
        word = params.get('word')
        if word:
            return 'I do not understand the word %s' % word
        else:
            return 'I did not get that'
    elif action == 'count_words':
        pass
    
    return 'I did not get that'


@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def application_error(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500