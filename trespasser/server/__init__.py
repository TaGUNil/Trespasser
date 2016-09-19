#!/usr/bin/env python3

from flask import Flask

application = Flask(__name__)

from trespasser.server import main
