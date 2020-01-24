import json
import urllib.request
import urllib.parse
import hashlib      
import configparser
import os.path
import sqlite3
from datetime import datetime as dt
from datetime import timedelta 
from datetime import timezone

configPath = './config.ini'
dbPath = '../lib/test.db'

headers = {}
headers['User-Agent'] = 'SD-JSON2XMLTV/0.1'
headers['Content-Type'] = 'text/plain'

def  getToken(cachedToken: str, baseUrl: str, apiVersion: str, username: str, sha1hexpass: str):
    try:
        if cachedToken == '':
            cachedToken = None
        
        else:
            cachedToken = json.loads(cachedToken)

        if cachedToken is not None \
        and cachedToken.get('code') == 0 \
        and dt.fromisoformat(cachedToken.get('datetime')[:19]).replace(tzinfo=timezone.utc) + timedelta(hours=20) > dt.now(timezone.utc):
            result = cachedToken
        
        else:
            try:
                url = baseUrl + '/' + apiVersion + '/token'
                post_data = f'{{"username":"{username}", "password":"{sha1hexpass}"}}'.encode()

                req = urllib.request.Request(url=url, data=post_data, headers=headers)
                response = urllib.request.urlopen(req)

            except urllib.error.HTTPError as err:
                result = json.loads(err.read())

            else:
                result = json.loads(response.read())
            
    finally:
        return result


#password = hashlib.sha1(b'password').hexdigest()

def getStatus(baseUrl: str, apiVersion: str, token: str):
    try:
        url = baseUrl + '/' + apiVersion + '/status'
        req = urllib.request.Request(url=url, data=None, headers=headers)
        req.add_header('token', token)
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

def updateLocalLineups(dbPath: str, baseUrl: str, token: str, lineups: list):
    try:
        conn = sqlite3.connect(dbPath)
        cur = conn.cursor()

        # Parse each lineup in the user's SchedulesDirect account  
        for lineup in lineups:
            lineupName = lineup.get('lineup')

            # Get the last modified date for this lineup from the local database
            cur.execute('SELECT modified FROM lineups WHERE lineup = ?', (lineupName,))
            lineupModified = cur.fetchone()[0]

            # Only get the new lineup map if it isn't in the local database or is newer than the one in the local database
            if (lineupModified is None or dt.fromisoformat(lineupModified[:19]) < dt.fromisoformat(lineup.get('modified')[:19])):

                lineupMap = getLineupMap(baseUrl + lineup.get('uri'), token)
                
                # Empty the lineup_maps table for this lineup and insert the new map
                conn.execute('DELETE FROM lineup_maps WHERE lineup = ?', (lineupName,))  
                for map in lineupMap.get('map'):
                    params = (lineupName, map.get('stationID'), map.get('uhfVhf'), map.get('atscMajor'), map.get('atscMinor'))
                    conn.execute('INSERT INTO lineup_maps (lineup, stationID, uhfVhf, atscMajor, atscMinor) VALUES (?,?,?,?,?)', params)
                
                # Insert or update the station details for each station in this lineup map
                for station in lineupMap.get('stations'):
                    params = (station.get('stationID'), station.get('name'), station.get('callsign'), station.get('affiliate'), json.dumps(station.get('broadcastLanguage')), json.dumps(station.get('descriptionLanguage')), json.dumps(station.get('broadcaster')), json.dumps(station.get('stationLogo')), station.get('isCommercialFree'))
                    conn.execute('INSERT INTO stations (stationID, name, callsign, affiliate, broadcastLanguage, descriptionLanguage, broadcaster, stationLogo, isCommercialFree) \
                        VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT (stationID) \
                        DO UPDATE SET name = excluded.name \
                        ,callsign = excluded.callsign \
                        ,affiliate = excluded.affiliate \
                        ,broadcastLanguage = excluded.broadcastLanguage \
                        ,descriptionLanguage = excluded.descriptionLanguage \
                        ,broadcaster = excluded.broadcaster \
                        ,stationLogo = excluded.stationLogo \
                        ,isCommercialFree = excluded.isCommercialFree', params)
                
                # Insert or update the lineups table with the current modified date
                conn.execute('INSERT INTO lineups (lineup, modified) \
                    VALUES (?,?) ON CONFLICT (lineup) \
                    DO UPDATE SET modified = excluded.modified', (lineupName, lineup.get('modified')))

        # Clean up any stations that were removed from the lineups
        conn.execute('DELETE FROM stations WHERE stationID NOT IN (SELECT stationID FROM lineup_maps)')
        conn.commit()
        cur.close()
        conn.close()

        result = 0

    except:
        result = -1

    finally:
        return result

def getSchedules(dbPath: str, baseUrl: str, apiVersion: str, token: str):
    try:
        conn = sqlite3.connect(dbPath)
        cur = conn.cursor()
        cur.execute('SELECT stationID FROM stations WHERE enabled = 1')
        stationIds = []
        stationId = cur.fetchone()
        while stationId is not None:
            stationIds.append({"stationID": "{0}".format(stationId[0])})
            stationId = cur.fetchone()
        
        cur.close()
        url = baseUrl + '/' + apiVersion + '/schedules/md5'
        req = urllib.request.Request(url=url, data=json.dumps(stationIds).encode(), headers=headers)
        req.add_header('token', token)
        response = urllib.request.urlopen(req)
        
        scheduleMd5s = json.loads(response.read())

        conn.execute('DELETE FROM scheduleMD5s WHERE source = 0')

        for stationId, stationSchedules in scheduleMd5s.items():
            for scheduleDate, scheduleData in stationSchedules.items():
                params = (0, stationId, scheduleDate, scheduleData['code'], scheduleData['message'], scheduleData['lastModified'], scheduleData['md5'])
                conn.execute('INSERT INTO scheduleMD5s VALUES (?,?,?,?,?,?,?)', params)
        conn.commit()
        
        cur = conn.cursor()
        cur.execute('SELECT new.stationID, new.date FROM scheduleMD5s new \
                    LEFT JOIN scheduleMD5s cache ON new.stationId = cache.stationId AND new.date = cache.date AND new.md5 = cache.md5 AND cache.source = 1 \
                    WHERE new.source = 0 and cache.md5 IS NULL ORDER BY new.stationID, new.date')
        
        stationIds = []
        stationIdDate = cur.fetchone()
        while stationIdDate is not None:
            stationId = stationIdDate[0]
            dates = []
            while stationIdDate is not None and stationId == stationIdDate[0]:
                dates.append(stationIdDate[1])
                stationIdDate = cur.fetchone()
            
            stationIds.append({"stationID": "{0}".format(stationId), "date": dates})
            
        if len(stationIds) == 0:
            return 0

        cur.close()
        url = baseUrl + '/' + apiVersion + '/schedules'
        req = urllib.request.Request(url=url, data=json.dumps(stationIds).encode(), headers=headers)
        req.add_header('token', token)
        response = urllib.request.urlopen(req)
        
        stationDates = json.loads(response.read())
        for stationDate in stationDates:
            stationId = stationDate.get('stationID')
            programs = stationDate.get('programs')
            metadata = stationDate.get('metadata')
            for program in programs:
                programId = program.get('programID')
                params = (stationId, programId, program.get('airDateTime'), program.get('duration'), program.get('md5'), program.get('new'), json.dumps(program.get('audioProperties')), json.dumps(program.get('videoProperties')))

                conn.execute('INSERT INTO programs (stationId, programId, airDateTime, duration, md5, new, audioProperties, videoProperties) \
                    VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (stationId, programId) \
                    DO UPDATE SET airDateTime = excluded.airDateTime \
                    ,duration = excluded.duration \
                    ,md5 = excluded.md5 \
                    ,new = excluded.new \
                    ,audioProperties = excluded.audioProperties \
                    ,videoProperties = excluded.videoProperties', params)

        conn.commit()
        cur.close()
        
        conn.close()

    except urllib.error.HTTPError as err:
        print (json.loads(err.read()))
        return -1


    return None



def main():
    # Set up the configparser object
    config = configparser.ConfigParser()
    config.read(configPath)

    waitUntil = config.get('Run Control', 'wait_until')
    if waitUntil == '':
        waitUntil = None

    # Don't proceed if we need to wait until later
    if waitUntil is not None and dt.fromisoformat(waitUntil).replace(tzinfo=timezone.utc) > dt.now(timezone.utc):
        return None

    # Get configuration variables from .ini file
    cachedToken = config.get('Credentials', 'token')
    baseUrl = config.get('Default', 'base_url')
    apiVersion = config.get('Default', 'api_version')
    username = config.get('Credentials', 'username')
    sha1hexpass = config.get('Credentials', 'sha1hexpass')

    # Obtain the token for this session
    token = getToken(cachedToken, baseUrl, apiVersion, username, sha1hexpass) 
    config.set('Credentials', 'token', json.dumps(token))
    if token.get('code') == 0:
        # Valid token was returned
        token = token.get('token')
        config.set('Run Control', 'wait_until', '')
    
    elif token.get('code') == 3000:
        # System unavailable
        # Per the API wiki: If the service is offline you should disconnect and retry in 30 minutes.
        config.set('Run Control', 'wait_until', (dt.now(timezone.utc) + timedelta(minutes=30)).isoformat()[:19])
        with open(configPath, 'w') as configfile:
            config.write(configfile)

        print (token.get('response'))
        return None

    else:
        print (token)
        return None

    # Update the config file with changes
    with open(configPath, 'w') as configfile:
        config.write(configfile)

    # Obtain the current status
    status = getStatus(baseUrl, apiVersion, token)
    if status.get('code') == 0:
        lineups = status.get('lineups')

    elif status.get('code') == 3000:
        # Per the API wiki: If the system status is "Offline" then disconnect; all further processing will be rejected at the server. A client should not attempt to reconnect for 1 hour.
        config.set('Run Control', 'wait_until', (dt.now(timezone.utc) + timedelta(minutes=60)).isoformat()[:19])
        with open(configPath, 'w') as configfile:
                config.write(configfile)

        print (token.get('response'))
        return None

    else:
        print(token)
        return None

    # Download the lineup to the local database
    result = updateLocalLineups(dbPath, baseUrl, token, lineups)
    if result != 0:
        print('Error in updateLocalLineups')
        return None

    # Send a request for the schedules for enabled stationID's to the server
    getSchedules(dbPath, baseUrl, apiVersion, token)

    
    

if __name__ == "__main__":
    main()
