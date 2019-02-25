#!/usr/bin/env python

# This file is part of GliderWeatherBot.
#
# GliderWeatherBot is copyright Philip G. Lee, 2018.
#
# GliderWeatherBot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GliderWeatherBot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GliderWeatherBot.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import datetime
import json
import logging
import os
import re
import threading
import time
import tweepy
from builtins import range, str
from io import open

try:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError

import datasource
import raspdata
import utilities

import localscore
import wavescore
import xcscore


# Download the file with the specified url to the given path
def download(url, path):
    try:
        response = urlopen(url)
        data = response.read()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print('ERROR: resource not found on server')
        return
    with open(path, 'wb') as output:
        output.write(data)

# This function blocks for 30 minutes for each retry.
def tweet(message, retries, imgUrl=None, dryRun=False):
    # Environment variables
    consumer_key = os.environ['WEATHERBOT_CONSUMER_KEY']
    consumer_secret = os.environ['WEATHERBOT_CONSUMER_SECRET']
    access_token = os.environ['WEATHERBOT_ACCESS_TOKEN']
    access_token_secret = os.environ['WEATHERBOT_TOKEN_SECRET']

    # Set up Twitter API
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    logging.info('Tweeting: \"{0}\" {1}'.format(message, 'with image ' + imgUrl if imgUrl else ''))

    # Exit now if it is just a dry run
    if dryRun:
        return

    imagePath = None
    # Download the image if we are given one
    if imgUrl and imgUrl.startswith('http'):
        imagePath = '/tmp/{0}.png'.format(utilities.randomString(8))
        download(imgUrl, imagePath)
    elif imgUrl:
        imagePath = imgUrl

    # Do the tweet loop
    tweetSuccess = False
    while tweetSuccess == False and retries > 0:
        try:
            if imagePath:
                api.update_with_media(imagePath, status=message)
            else:
                api.update_status(message)
            tweetSuccess = True
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logging.exception('Failed to tweet. Will retry in 30 minutes.')
            retries -= 1
            # Wait half an hour
            time.sleep(30 * 60)

    # Check whether or not we got through
    if tweetSuccess is False:
        logging.error('Retries unsuccessful. Unable to tweet.')

    # Clean up
    if imagePath:
        os.remove(imagePath)

# Create a human-readable string of days from a bunch of day offsets
def daysString(dates):
    ret = ''
    first = True
    for date in sorted(dates):
        ret += '' if first else ', '
        ret += date.strftime("%A %d %b")
        first = False
    return ret

# Returns a set of good wave days and an image URL
def goodWaveDays(classifier, baseURL, times, lookahead):
    waveDays = set()
    maxWaveScore = -1000.0
    waveImageURL = None
    dataSource = datasource.WebRASPDataSource(baseURL)
    for day in range(lookahead):
        date = datetime.date.today() + datetime.timedelta(day)
        isWaveDay = False
        isHardToClassify = False
        for time in times:
            dataTimeSlice = datasource.WebRASPDataTimeSlice(dataSource, day, time)
            try:
                isWave, score = classifier.classify(dataTimeSlice)
                isWaveDay |= isWave
                isHardToClassify |= (score >= -1.0) and (score <= 1.0)
                # Pick the time with the best score to use as the image
                if score > maxWaveScore:
                    maxWaveScore = score
                    waveImageURL = '{0}/OUT+{1}/FCST/press{2}.curr.{3}lst.d2.body.png'.format(baseURL, day, 700, time)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                logging.exception('Unable to download one of the files for day {0} time {1}'.format(day, time))
                continue
            logging.info(' - {0}Wave {1}+{2}: {3:.3f}'.format('*' if isWave else '', date.isoformat(), time, score))
        if isWaveDay:
            waveDays.add(date)

    return waveDays, waveImageURL

# Detect XC days
def goodXCDays(classifier, baseURL, times, lookahead):
    xcDays = set()
    dataSource = datasource.WebRASPDataSource(baseURL)
    maxScore = -1000.0
    bestTimeSlice = None
    for day in range(lookahead):
        date = datetime.date.today() + datetime.timedelta(day)
        isXcDay = False
        isHardToClassify = False
        for time in times:
            dataTimeSlice = datasource.WebRASPDataTimeSlice(dataSource, day, time)
            try:
                isXc, score = classifier.classify(dataTimeSlice)
                isXcDay |= isXc
                isHardToClassify |= (score >= -1.0) and (score <= 1.0)
                # Pick the time with the best score to use as the image
                if score > maxScore:
                    maxScore = score
                    bestTimeSlice = dataTimeSlice
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                logging.exception('Unable to download one of the files for day {0} time {1}'.format(day, time))
                continue
            logging.info(' - {0}XC {1}+{2}: {3:.3f}'.format('*' if isXc else '', date.isoformat(), time, score))
        if isXcDay:
            xcDays.add(date)

    return (xcDays, classifier.imageSummary(bestTimeSlice))

# Detect local soaring days
def goodLocalDays(classifier, baseURL, times, lookahead):
    localDays = set()
    dataSource = datasource.WebRASPDataSource(baseURL)
    maxScore = -1000.0
    bestTimeSlice = None
    for day in range(lookahead):
        date = datetime.date.today() + datetime.timedelta(day)
        isLocalDay = False
        isHardToClassify = False
        for time in times:
            dataTimeSlice = datasource.WebRASPDataTimeSlice(dataSource, day, time)
            try:
                isLocal, score = classifier.classify(dataTimeSlice)
                isLocalDay |= isLocal
                isHardToClassify |= (score >= -1.0) and (score <= 1.0)
                # Pick the time with the best score to use as the image
                if score > maxScore:
                    maxScore = score
                    bestTimeSlice = dataTimeSlice
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                logging.exception('Unable to download one of the files for day {0} time {1}'.format(day, time))
                continue
            logging.info(' - {0}Local {1}+{2}: {3:.3f}'.format('*' if isLocal else '', date.isoformat(), time, score))
        if isLocalDay:
            localDays.add(date)

    return (localDays, classifier.imageSummary(bestTimeSlice))

def readState(filename):
    state = {
        'local-days': set(),
        'wave-days': set(),
        'xc-days': set()
    }
    try:
        file = open(filename, 'r')
        fileState = json.load(file)
        file.close()
        for daysKey in state:
            if daysKey not in fileState:
                continue
            dates = set()
            for dateStr in fileState[daysKey]:
                (y,m,d) = re.search('(\d+)-(\d+)-(\d+)', dateStr).groups()
                dates.add(datetime.date(int(y), int(m), int(d)))
            state[daysKey] = dates
    except (IOError, ValueError) as err:
        logging.info('State file not opened: {0}'.format(err))

    return state

def writeState(state, filename):
    with open(filename, 'w+', encoding='utf-8') as file:
        jsonState = {}
        for daysKey in state:
            jsonState[daysKey] = [date.strftime(u'%Y-%m-%d') for date in state[daysKey]]
        #json.dump(state, file)
        # The JSON module is so damn dumb
        file.write(str(json.dumps(jsonState)))

if __name__=='__main__':

    # Arguments
    parser = argparse.ArgumentParser(description='Tweet about good soaring forecasts')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Do not actually tweet anything.')
    parser.add_argument('-l', '--log-path', type=str, default='/home/pi', metavar='path', help='Logging path')
    parser.add_argument('--local-url', type=str, default='https://rasp.nfshost.com/norcal-coast', metavar='url', help='Base URL for local RASP data')
    parser.add_argument('--wave-url', type=str, default='https://rasp.nfshost.com/hollister', metavar='url', help='Base URL for wave RASP data')
    parser.add_argument('--xc-url', type=str, default='https://rasp.nfshost.com/norcal-coast', metavar='url', help='Base URL for XC RASP data')
    parser.add_argument('--local-lookahead', type=int, default=7, metavar='ndays', help='How many days to look ahead for local forecasts')
    parser.add_argument('--wave-lookahead', type=int, default=3, metavar='ndays', help='How many days to look ahead for wave forecasts')
    parser.add_argument('--xc-lookahead', type=int, default=7, metavar='ndays', help='How many days to look ahead for XC forecasts')
    parser.add_argument('--local-times', nargs='+', type=int, metavar='lst', default=[1000, 1100, 1200, 1300, 1400, 1500, 1600], help='List of local times to check for local conditions')
    parser.add_argument('--wave-times', nargs='+', type=int, metavar='lst', default=[1000, 1100, 1200, 1300, 1400, 1500, 1600], help='List of local times to check for wave conditions')
    parser.add_argument('--xc-times', nargs='+', type=int, default=[1400], metavar='lst', help='List of local times to check for XC conditions')
    parser.add_argument('--local-classifier', type=str, default='KCVH', metavar='name', help='Name of the local classifier')
    parser.add_argument('--wave-classifier', type=str, default='KCVH', metavar='name', help='Name of the wave classifier')
    parser.add_argument('--xc-classifier', type=str, default='KCVH', metavar='name', help='Name of the XC classifier')
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        filename=None if args.dry_run else '{0}/gliderweatherbot.log'.format(args.log_path),
        level=logging.DEBUG,
        format='%(asctime)s %(message)s'
    )

    with open('version.txt') as vFile:
        logging.info('Version {0}'.format(vFile.readline()))

    # Load the state
    state = readState('.state.json')

    # We spawn threads for tweeting, since we want to potentially do a long-waiting
    # retry loop in case something is temporarily-wrong with the network.
    tweetThreads = []

    def tweetAlert(alertString, days, imageURL, raspURL):
        if len(days) > 0:
            tweetString = alertString + daysString(days) + '.'
            tweetString += '\n.\n' + raspURL

            # Try to tweet it out
            tweetThread = threading.Thread(target=tweet, args=(tweetString, 4, imageURL, args.dry_run))
            tweetThreads.append(tweetThread)
            tweetThread.start()

    localClassifier = localscore.LocalClassifierFactory.classifier(args.local_classifier)
    waveClassifier = wavescore.WaveClassifierFactory.classifier(args.wave_classifier)
    xcClassifier = xcscore.XCClassifierFactory.classifier(args.xc_classifier)

    # Run local soaring day detection
    (localDays, localImageURL) = goodLocalDays(localClassifier, args.local_url, args.local_times, args.local_lookahead)
    # Remove any days we have already notified on
    localDays -= state['local-days']
    state['local-days'] |= localDays
    tweetAlert('Local Soaring Alert! These days may be good for local soaring: ', localDays, localImageURL, args.local_url)

    # Run wave day detection
    (waveDays, waveImageURL) = goodWaveDays(waveClassifier, args.wave_url, args.wave_times, args.wave_lookahead)
    # Remove any days we have already notified on
    waveDays -= state['wave-days']
    state['wave-days'] |= waveDays
    tweetAlert('Wave Alert! These days may have wave: ', waveDays, waveImageURL, args.wave_url)

    # Run XC day detection
    (xcDays, xcImageURL) = goodXCDays(xcClassifier, args.xc_url, args.xc_times, args.xc_lookahead)
    # Remove any days we have already notified on
    xcDays -= state['xc-days']
    state['xc-days'] |= xcDays
    tweetAlert('XC Alert! These days may be runnable: ', xcDays, xcImageURL, args.xc_url)

    # Write state back
    writeState(state, '.state.json')

    # Wait for all threads to complete
    for thread in tweetThreads:
        thread.join()
