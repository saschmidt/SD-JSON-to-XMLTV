import json
import urllib.request
import urllib.parse
import hashlib      
import configparser
import os.path

headers = {}
headers['Content-Type'] = 'text/plain'
headers['User-Agent'] = 'SD-JSON2XMLTV/0.1'

def  getToken(url: str, username: str, sha1hexpass: str ):
    try:
        result = -1

        post_data = f'{{"username":"{username}", "password":"{sha1hexpass}"}}'.encode()
        req = urllib.request.Request(url=url + '/token', data=post_data, headers=headers)
        response = urllib.request.urlopen(req)

    except urllib.error.HTTPError as err:
        result = json.loads(err.read())

    else:
        result = json.loads(response.read())

    finally:
        return result


#password = hashlib.sha1(b'password').hexdigest()

def getStatus(url: str, token: str):
    try:
        req = urllib.request.Request(url=url + '/status', data=None, headers=headers)
        req.add_header('token',token)
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as err:
        result = json.loads(err.read())

    else:
        result = json.loads(response.read())

    finally:
        return result

def getLineupMap(url: str, token: str):
    try:
        req = urllib.request.Request(url=url, data=None, headers=headers)
        req.add_header('token',token)
        req.add_header('verboseMap', 'false')
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as err:
        result = json.loads(err.read())

    else:
        result = json.loads(response.read())

    finally:
        return result

def main():
    # Set configuration variables from .ini file
    config = configparser.ConfigParser()
    config.read(os.path.abspath('./config.ini'))
    base_url = config.get('Default', 'base_url')
    api_version = config.get('Default', 'api_version')
    username = config.get('Credentials', 'username')
    password = config.get('Credentials', 'password')

    token = getToken((base_url + '/' + api_version), username, password) 
    if token['code'] == 0:
        # Valid token was returned
        token = token['token']
    elif token['code'] == 3000:
        # 
        pass
    print (token)

    # token = ''

    status = getStatus((base_url + '/' + api_version), token)
    if status['code'] == 0:
        # System is online
        lineups = status['lineups']
        print(lineups)

    else:
        # Wait 1 hour
        print('Wait 1 hour')

    for lineup in lineups:
        lineup_map = getLineupMap((base_url + lineup['uri']), token)  

if __name__ == "__main__":
    main()
