#!/usr/bin/env python3

import requests


class GenericClientError(Exception):
    pass


class ConnectionError(GenericClientError):
    pass


class AuthenticationError(GenericClientError):
    pass


class GameNotFoundError(GenericClientError):
    pass


class ResourceNotFoundError(GenericClientError):
    pass


class AttemptNotFoundError(GenericClientError):
    pass


class Client(object):
    def __init__(self, host, port=443, cert=None, verify=True):
        host = str(host)
        port = int(port)

        self.session = requests.Session()

        port_string = ':{:d}'.format(port) if port != 443 else ''
        self.uri_base = 'https://{}{}'.format(host, port_string)

        self.session.cert = cert
        self.session.verify = verify

    def game_exists(self, game):
        game = str(game)

        try:
            response = self.session.get(self.uri_base + '/' + game)
        except requests.exceptions.SSLError:
            raise AuthenticationError
        except requests.exceptions.ConnectionError:
            raise ConnectionError

        if response.status_code == requests.codes.ok:
            return True
        elif response.status_code == requests.codes.not_found:
            return False
        elif response.status_code == requests.codes.forbidden:
            raise AuthenticationError
        else:
            raise GenericClientError

    def get_game_resource(self, game, resource):
        game = str(game)
        resource = str(resource)

        if not self.game_exists(game):
            raise GameNotFoundError

        try:
            response = self.session.get(self.uri_base + '/' + game +
                                        '/resources/' + resource)
        except requests.exceptions.SSLError:
            raise AuthenticationError
        except requests.exceptions.ConnectionError:
            raise ConnectionError

        if response.status_code == requests.codes.ok:
            return response.text
        elif response.status_code == requests.codes.not_found:
            raise ResourceNotFoundError
        elif response.status_code == requests.codes.forbidden:
            raise AuthenticationError
        else:
            raise GenericClientError

    def post_game_attempt(self, game, data):
        game = str(game)

        if not self.game_exists(game):
            raise GameNotFoundError

        files = {'attempt': ('attempt', data)}
        try:
            response = self.session.post(self.uri_base + '/' + game +
                                         '/attempts/',
                                         files=files)
        except requests.exceptions.SSLError:
            raise AuthenticationError
        except requests.exceptions.ConnectionError:
            raise ConnectionError

        if response.status_code == requests.codes.created:
            location = response.headers['Location']
            location_parts = list(filter(lambda s: len(s) != 0,
                                         location.split('/')))
            attempt = int(location_parts[-1])
            return attempt
        elif response.status_code == requests.codes.forbidden:
            raise AuthenticationError
        else:
            raise GenericClientError

    def game_attempt_exists(self, game, attempt):
        game = str(game)
        attempt = int(attempt)

        try:
            response = self.session.get(self.uri_base + '/' + game +
                                        '/attempts/' + str(attempt))
        except requests.exceptions.SSLError:
            raise AuthenticationError
        except requests.exceptions.ConnectionError:
            raise ConnectionError

        if response.status_code == requests.codes.ok:
            return True
        elif response.status_code == requests.codes.not_found:
            return False
        elif response.status_code == requests.codes.forbidden:
            raise AuthenticationError
        else:
            raise GenericClientError

    def get_game_attempt_status(self, game, attempt):
        game = str(game)
        attempt = int(attempt)

        if not self.game_exists(game):
            raise GameNotFoundError

        if not self.game_attempt_exists(game, attempt):
            raise AttemptNotFoundError

        try:
            response = self.session.get(self.uri_base + '/' + game +
                                        '/attempts/' + str(attempt) +
                                        '/status')
        except requests.exceptions.SSLError:
            raise AuthenticationError
        except requests.exceptions.ConnectionError:
            raise ConnectionError

        if response.status_code == requests.codes.ok:
            return response.json()
        elif response.status_code == requests.codes.forbidden:
            raise AuthenticationError
        else:
            raise GenericClientError

    def get_game_attempt_results(self, game, attempt):
        game = str(game)
        attempt = int(attempt)

        if self.get_game_attempt_status(game, attempt) != 'finished':
            return None

        try:
            response = self.session.get(self.uri_base + '/' + game +
                                        '/attempts/' + str(attempt) +
                                        '/results')
        except requests.exceptions.SSLError:
            raise AuthenticationError
        except requests.exceptions.ConnectionError:
            raise ConnectionError

        if response.status_code == requests.codes.ok:
            return response.content
        elif response.status_code == requests.codes.not_found:
            return None
        elif response.status_code == requests.codes.forbidden:
            raise AuthenticationError
        else:
            raise GenericClientError
