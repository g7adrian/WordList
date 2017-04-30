"""`main` is the top level module for your Flask application."""
from __future__ import print_function # In python 2.7
import json
import os
import sys
import urllib
import urllib2
from google.appengine.ext import ndb

# Import the Flask Framework
from flask import Flask, request, make_response
app = Flask(__name__)


class WordListConfig(ndb.Model):
    oxford_url_pattern = ndb.StringProperty(indexed=False)
    oxford_app_id = ndb.StringProperty(indexed=False)
    oxford_app_key = ndb.StringProperty(indexed=False)


def setup_app(app):
    """Read configuration from App Datastore. The name of the configuration
    should be provided by the CONFIG_MODEL_ID environment variable."""
    try:
        config_key = ndb.Key('WordListConfig', os.environ['CONFIG_MODEL_ID'])
        app.wordlist_config = config_key.get()
    except:
        print('Cannot load config from Datastore', file=sys.stderr)
        sys.exit(1)
setup_app(app)


class Word(ndb.Model):
    """A word to be learned. The key name is the word itself"""
    times_defined = ndb.IntegerProperty()
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
        definition = get_word_definition(word)
        if definition is None:
            return 'I do not know this word'
        else:
            return definition
    
    return 'I did not get that'


def get_word_definition(word):
    """Looks up word in the external dictionary and returns its definition.
    Returns None if the word is not found, or other errors.
    """
    if not word:
        return None
    word = word.lower()
    word_enc = word.replace('/', '_')
    word_enc = word_enc.replace(' ', '_')
    word_enc = urllib.quote(word_enc)
    
    req = urllib2.Request(app.wordlist_config.oxford_url_pattern % word_enc)
    req.add_header('app_id', app.wordlist_config.oxford_app_id)
    req.add_header('app_key', app.wordlist_config.oxford_app_key)

    try:
        res = urllib2.urlopen(req)
    except urllib2.HTTPError as e:
        print('Oxford dictionary returned with error code %s' % e.code,
              file=sys.stderr)
        return None
    
    res_json = json.load(res)
    try:
        definition = res_json['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]['definitions'][0]
    except (KeyError, TypeError):
        print('Invalid dictionary response', file=sys.stderr)
        print(json.dumps(res_json, indent=4), file=sys.stderr)
        return None
    
    try:
        audio = res_json['results'][0]['lexicalEntries'][0]['pronunciations'][0]['audioFile']
    except (KeyError, TypeError):
        audio = None

    if audio is not None:
        definition = '<audio src="%s">%s</audio>, ' % (audio, word) + definition
    else:
        definition = '%s, ' % word + definition
    
    return definition


@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def application_error(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500


if __name__ == '__main__':
    app.run()