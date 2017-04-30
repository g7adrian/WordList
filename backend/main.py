"""`main` is the top level module for your Flask application."""
from __future__ import print_function # In python 2.7
import json
import os
import random
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
    word = ndb.StringProperty(indexed=False)
    definition = ndb.StringProperty(indexed=False)
    practice_count = ndb.IntegerProperty()
    learned = ndb.BooleanProperty()


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


def normalize_word(word):
    word = word.lower()
    word = word.replace('/', '_')
    word = word.replace(' ', '_')
    word = urllib.quote(word)
    return word


def process_action(action, params):
    """Processes an action with the parameters dictionary, and returns
    the speech reply to be spoken to the user."""
    if action == 'define_word':
        word = params.get('word')
        if word is None:
            return 'I do not know this word'
        word_id = normalize_word(word)
        word_model = ndb.Key('Word', word_id).get()
        if word_model is not None:
            word_model.practice_count += 1
            word_model.put()
            return '%s, %s' % (word, word_model.definition)
        
        word_model = Word()
        word_model.learned = False
        word_model.word = word
        word_model.key = ndb.Key('Word', word_id)
        if not get_word_definition(word_model):
            return 'I do not know this word'
        else:
            word_model.practice_count = 1
            word_model.put()
            return '%s, %s' % (word, word_model.definition)
    
    elif action == 'practice':
        keys = Word.query().filter(Word.learned == False).fetch(keys_only=True)
        selected_word_key = random.sample(keys, 1)[0]
        return 'How about the word %s?' % selected_word_key.get().word
        
    return 'I did not get that'


def get_word_definition(word_model):
    """Looks up word in the external dictionary and returns its definition.
    Returns False if the word is not found, or other errors.
    """
    word_id = word_model.key.string_id()
    req = urllib2.Request(app.wordlist_config.oxford_url_pattern % word_id)
    req.add_header('app_id', app.wordlist_config.oxford_app_id)
    req.add_header('app_key', app.wordlist_config.oxford_app_key)

    try:
        res = urllib2.urlopen(req)
    except urllib2.HTTPError as e:
        print('Oxford dictionary returned with error code %s' % e.code,
              file=sys.stderr)
        return False
    
    res_json = json.load(res)
    try:
        word_model.definition = \
            res_json['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]['definitions'][0]
    except (KeyError, TypeError):
        print('Invalid dictionary response', file=sys.stderr)
        print(json.dumps(res_json, indent=4), file=sys.stderr)
        return False
    
    try:
        word_model.audio = \
            res_json['results'][0]['lexicalEntries'][0]['pronunciations'][0]['audioFile']
    except (KeyError, TypeError):
        word_model.audio = None

    return True


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