import hmac
import os
import random
import requests

from flask import Flask, request, jsonify

WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
API_KEY = os.environ.get('API_KEY')

application = Flask(__name__)

with open('tests/integration/test-malicious.json') as test:
    malicious_contents = test.read().rstrip()

malicious_digest = hmac.new(API_KEY.encode('utf-8'), malicious_contents.encode('utf-8'), digestmod="sha256").hexdigest()

with open('tests/integration/test-benign.json') as test:
    benign_contents = test.read().rstrip()

benign_digest = hmac.new(API_KEY.encode('utf-8'), benign_contents.encode('utf-8'), digestmod="sha256").hexdigest()

empty_digest = hmac.new(API_KEY.encode('utf-8'), b'', digestmod='sha256').hexdigest()

@application.route("/", methods=['POST'])
def test_receiver():
    body = request.get_json()
    print(body)
    return jsonify("OK"), 200


@application.route("/test/bounty", methods=['POST'])
def test_scanner():
    session = requests.Session()
    digest, contents = random.choice([(malicious_digest, malicious_contents), (benign_digest, benign_contents)])
    headers = {
        'Content-Type': "application/json",
        'X-POLYSWARM-SIGNATURE': digest,
        'X-POLYSWARM-EVENT': 'bounty'
    }
    with session.post(WEBHOOK_URL, headers=headers, data=contents) as response:
        print('Received %s', response.content.decode('utf-8'))
        response.raise_for_status()
    return jsonify("OK"), 200


@application.route("/test/ping", methods=['POST'])
def test_ping():
    session = requests.Session()
    headers = {
        'X-POLYSWARM-SIGNATURE': empty_digest,
        'X-POLYSWARM-EVENT': 'ping'
    }
    with session.post(WEBHOOK_URL, headers=headers) as response:
        print('Received %s', response.content.decode('utf-8'))
        response.raise_for_status()
    return jsonify("OK"), 200


@application.route("/test/analyze", methods=['POST'])
def test_analyze():
    session = requests.Session()
    headers = {
        'X-POLYSWARM-SIGNATURE': empty_digest,
        'X-POLYSWARM-EVENT': 'analyze'
    }
    with session.post(WEBHOOK_URL, headers=headers) as response:
        print('Received %s', response.content.decode('utf-8'))
        response.raise_for_status()
    return jsonify("OK"), 200
