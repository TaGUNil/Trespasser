#!/usr/bin/env python3

import sys
import os
import os.path
import re
import json
import binascii
import base64

import flask
import werkzeug.routing

from trespasser import application, settings


application.jinja_env.trim_blocks = True
application.jinja_env.lstrip_blocks = True


class GameConverter(werkzeug.routing.BaseConverter):
    def to_python(self, value):
        if value not in settings.GAMES:
            raise werkzeug.routing.ValidationError()
        return value

    def to_url(self, value):
        return super().to_url(value)


application.url_map.converters['game'] = GameConverter


USER = None


@application.before_request
def identify_user():
    global USER

    if 'HTTP_AUTHORIZATION' not in flask.request.environ:
        USER = 'nobody'
        return

    scheme, credentials = flask.request.environ['HTTP_AUTHORIZATION'].split()
    if scheme != 'Basic':
        USER = 'nobody'
        return

    try:
        auth_string = base64.b64decode(credentials,
                                       validate=True).decode('utf-8')
        username, password = auth_string.split(':')
    except:
        USER = 'nobody'
        return

    if re.fullmatch(r'[0-9A-Za-z\-_]+', username) is None:
        USER = 'nobody'
        return

    USER = username
    return


def make_json_response(structure):
    response = flask.make_response(json.dumps(structure))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.cache_control.no_store = True
    return response


@application.route('/')
def index():
    games = list(settings.GAMES.keys())
    games.sort()

    items = [{'caption': game,
              'href': flask.url_for('game_index', game=game)}
            for game in games]

    return flask.render_template('index.html',
                                 title='index',
                                 items=items)


@application.route('/<game:game>/')
def game_index(game):
    items = [{'caption': 'attempts',
              'href': flask.url_for('game_attempts', game=game)},
             {'caption': 'resources',
              'href': flask.url_for('game_resources', game=game)}]

    return flask.render_template('index.html',
                                 title=game,
                                 items=items)


@application.route('/<game:game>/resources/')
def game_resources(game):
    resources = list(settings.GAMES[game]['resources'].keys())
    resources.sort()

    items = [{'caption': resource,
              'href': flask.url_for('game_resource',
                                    game=game,
                                    resource=resource)}
             for resource in resources]

    return flask.render_template('index.html',
                                 title='resources',
                                 items=items)


@application.route('/<game:game>/resources/<string:resource>')
def game_resource(game, resource):
    if resource not in settings.GAMES[game]['resources']:
        flask.abort(404)

    resource_path = os.path.join(settings.GAMES[game]['base_path'],
                                 settings.GAMES[game]['resources'][resource])

    return flask.send_file(resource_path, cache_timeout=60)


def escape_template(template):
    if len(template) == 0:
        return ''

    head, separator_1, body_and_tail = template.partition('{')
    body, separator_2, tail = body_and_tail.partition('}')

    return ''.join([re.escape(head), 
                    separator_1,
                    body,
                    separator_2,
                    escape_template(tail)])
                                        

def enumerate_game_attempts(game):
    attempts = set()

    name_template = escape_template(settings.GAMES[game]['input_name_format'])
    name_pattern = name_template.format(user=re.escape(USER),
                                        attempt='([0-9]+)')
    compiled_name_pattern = re.compile(name_pattern)

    input_dir_path = os.path.join(settings.GAMES[game]['base_path'],
                                  settings.GAMES[game]['input_dir'])
    working_dir_path = os.path.join(settings.GAMES[game]['base_path'],
                                    settings.GAMES[game]['working_dir'])

    if sys.version_info >= (3, 5):
        for dir_path in [input_dir_path, working_dir_path]:
            for entry in os.scandir(dir_path):
                if entry.is_file():
                    match = compiled_name_pattern.fullmatch(entry.name)
                    if match is not None:
                        attempt = int(match.group(1))
                        attempts.add(attempt)
    else:
        for dir_path in [input_dir_path, working_dir_path]:
            for name in os.listdir(dir_path):
                match = compiled_name_pattern.fullmatch(name)
                if match is not None:
                    attempt = int(match.group(1))
                    attempts.add(attempt)

    return attempts


def create_input_file_path(game, attempt):
    file_name_template = settings.GAMES[game]['input_name_format']
    file_name = file_name_template.format(user=USER, attempt=attempt)
    file_path = os.path.join(settings.GAMES[game]['base_path'],
                             settings.GAMES[game]['input_dir'],
                             file_name)
    return file_path


def create_working_file_path(game, attempt):
    file_name_template = settings.GAMES[game]['input_name_format']
    file_name = file_name_template.format(user=USER, attempt=attempt)
    file_path = os.path.join(settings.GAMES[game]['base_path'],
                             settings.GAMES[game]['working_dir'],
                             file_name)
    return file_path


def create_output_file_path(game, attempt):
    file_name_template = settings.GAMES[game]['output_name_format']
    file_name = file_name_template.format(user=USER, attempt=attempt)
    file_path = os.path.join(settings.GAMES[game]['base_path'],
                             settings.GAMES[game]['output_dir'],
                             file_name)
    return file_path


@application.route('/<game:game>/attempts/', methods=['GET', 'POST'])
def game_attempts(game):
    attempts = enumerate_game_attempts(game)

    if flask.request.method == 'POST':
        if len(attempts) > 0:
            attempt = max(attempts) + 1
        else:
            attempt = 1

        if 'attempt' not in flask.request.files:
            flask.abort(400)

        input_file_path = create_input_file_path(game, attempt)

        flask.request.files['attempt'].save(input_file_path)

        location = flask.url_for('game_attempt', game=game, attempt=attempt)

        items = [{'caption': attempt,
                  'href': location}]

        content = flask.render_template('index.html',
                                        title='new attempt',
                                        items=items)
        response = flask.make_response(content, 201)
        response.headers['Location'] = location

        return response

    ordered_attempts = list(attempts)
    ordered_attempts.sort()

    items = [{'caption': attempt,
              'href': flask.url_for('game_attempt',
                                    game=game,
                                    attempt=attempt)}
             for attempt in ordered_attempts]

    return flask.render_template('attempts.html',
                                 title='attempts',
                                 items=items)


@application.route('/<game:game>/attempts/<int:attempt>/')
def game_attempt(game, attempt):
    attempts = enumerate_game_attempts(game)
    if attempt not in attempts:
        flask.abort(404)

    items = [{'caption': 'status',
              'href': flask.url_for('game_attempt_status',
                                    game=game,
                                    attempt=attempt)}]

    output_file_path = create_output_file_path(game, attempt)
    if os.path.exists(output_file_path):
        items.append({'caption': 'results',
                      'href': flask.url_for('game_attempt_results',
                                            game=game,
                                            attempt=attempt)})

    return flask.render_template('index.html',
                                 title=attempt,
                                 items=items)


@application.route('/<game:game>/attempts/<int:attempt>/status')
def game_attempt_status(game, attempt):
    attempts = enumerate_game_attempts(game)
    if attempt not in attempts:
        flask.abort(404)

    input_file_path = create_input_file_path(game, attempt)
    working_file_path = create_working_file_path(game, attempt)
    output_file_path = create_output_file_path(game, attempt)
    
    if not os.path.exists(working_file_path):
        if os.path.exists(input_file_path):
            return make_json_response('waiting')
        else:
            flask.abort(404)

    if not os.path.exists(output_file_path):
        return make_json_response('processing')
    else:
        return make_json_response('finished')


@application.route('/<game:game>/attempts/<int:attempt>/results')
def game_attempt_results(game, attempt):
    attempts = enumerate_game_attempts(game)
    if attempt not in attempts:
        flask.abort(404)

    output_file_path = create_output_file_path(game, attempt)
    if not os.path.exists(output_file_path):
        flask.abort(404)

    return flask.send_file(output_file_path)
