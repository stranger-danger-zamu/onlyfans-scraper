r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

import hashlib
import json
import pathlib
import time
from urllib.parse import urlparse, urlsplit

import httpx

from .profiles import get_current_profile
from .prompts import auth_prompt, ask_make_auth_prompt
from ..constants import configPath, authFile, DC_EP, requestAuth


def read_auth():
    make_request_auth()

    profile = get_current_profile()

    p = pathlib.Path.home() / configPath / profile
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            with open(p / authFile, 'r') as f:
                auth = json.load(f)
            break
        except FileNotFoundError:
            print(
                "You don't seem to have an `auth.json` file. Please fill the following out:")
            make_auth(p)
    return auth


def edit_auth():
    profile = get_current_profile()

    p = pathlib.Path.home() / configPath / profile
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    try:
        with open(p / authFile, 'r') as f:
            auth = json.load(f)
        make_auth(p, auth)

        print('Your `auth.json` file has been edited.')
    except FileNotFoundError:
        if ask_make_auth_prompt():
            make_auth(p)


def make_auth(path, auth=None):
    if not auth:
        auth = {
            'auth': {
                'app-token': '33d57ade8c02dbc5a333db99ff9ae26a',
                'sess': '',
                'auth_id': '',
                'auth_uid_': '',
                'user_agent': '',
                'x-bc': ''
            }
        }

    auth['auth'].update(auth_prompt(auth['auth']))

    with open(path / authFile, 'w') as f:
        f.write(json.dumps(auth, indent=4))


def get_auth_id() -> str:
    auth_id = read_auth()['auth']['auth_id']
    return auth_id


def make_headers(auth):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'app-token': auth['auth']['app-token'],
        'user-id': auth['auth']['auth_id'],
        'x-bc': auth['auth']['x-bc'],
        'referer': 'https://onlyfans.com',
        'user-agent': auth['auth']['user_agent'],
    }
    return headers


def add_cookies(client):
    profile = get_current_profile()

    p = pathlib.Path.home() / configPath / profile
    with open(p / authFile, 'r') as f:
        auth = json.load(f)

    domain = 'onlyfans.com'

    auth_uid = 'auth_uid_{}'.format(auth['auth']['auth_id'])

    client.cookies.set('sess', auth['auth']['sess'], domain=domain)
    client.cookies.set('auth_id', auth['auth']['auth_id'], domain=domain)
    if auth['auth']['auth_uid_']:
        client.cookies.set(auth_uid, auth['auth']['auth_uid_'], domain=domain)


def create_sign(link, headers):
    """
    credit: DC and hippothon
    """
    content = read_request_auth()

    time2 = str(round(time.time() * 1000))

    path = urlsplit(link).path
    query = urlsplit(link).query
    path = path if not query else f"{path}?{query}"

    static_param = content['static_param']

    a = [static_param, time2, path, headers['user-id']]
    msg = "\n".join(a)

    message = msg.encode("utf-8")
    hash_object = hashlib.sha1(message)
    sha_1_sign = hash_object.hexdigest()
    sha_1_b = sha_1_sign.encode("ascii")

    checksum_indexes = content['checksum_indexes']
    checksum_constant = content['checksum_constant']
    checksum = sum(sha_1_b[i] for i in checksum_indexes) + checksum_constant

    final_sign = content['format'].format(sha_1_sign, abs(checksum))

    headers.update(
        {
            'sign': final_sign,
            'time': time2
        }
    )
    return headers


def read_request_auth() -> dict:
    profile = get_current_profile()
    p = pathlib.Path.home() / configPath / profile / requestAuth
    with open(p, 'r') as f:
        content = json.load(f)
    return content


def make_request_auth():
    request_auth = {
        'static_param': '',
        'format': '',
        'checksum_indexes': [],
        'checksum_constant': 0
    }

    # *values, = get_request_auth()
    result = get_request_auth()
    if result:
        *values, = result

        request_auth.update(zip(request_auth.keys(), values))

        profile = get_current_profile()

        p = pathlib.Path.home() / configPath / profile
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)

        with open(p / requestAuth, 'w') as f:
            f.write(json.dumps(request_auth, indent=4))


def get_request_auth():
    with httpx.Client(http2=True) as c:
        r = c.get(DC_EP)
    if not r.is_error:
        content = r.json()
        static_param = content['static_param']
        fmt = content['format']
        checksum_indexes = content['checksum_indexes']
        checksum_constant = content['checksum_constant']
        return (static_param, fmt, checksum_indexes, checksum_constant)
    else:
        return []
