import json
import urllib.request
import urllib.parse
import hashlib      
import configparser

base_url = 'https://json.schedulesdirect.org/20141201'
headers = {}
headers['Content-Type'] = 'text/plain'

def  getToken( username: str, sha1hexpass: str ):
    try:
        result = -1

        post_data = f'{{"username":"{username}", "password":"{sha1hexpass}"}}'.encode()
        post_response = urllib.request.urlopen(url=base_url + '/token', data=post_data)

    except urllib.error.HTTPError as err:
        result = json.loads(err.read())

    else:
        result = json.loads(post_response.read())

    finally:
        return result


#password = hashlib.sha1(b'password').hexdigest()


def main():
    # Set configuration variables from .ini file
    config = configparser.ConfigParser()
    config.read('./config.ini')
    username = config.get('SD Credentials', 'username')
    password = config.get('SD Credentials', 'password')

    token = getToken( username, password ) 
    if token['code'] == 0:
        # Valid token was returned
        token = token['token']
    elif token['code'] == 3000:
        # 
        pass
    print (token)

if __name__ == "__main__":
    main()
