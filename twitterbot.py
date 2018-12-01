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
import random
import re
import string
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
import wavescore
import xcscore

# Return a random string of lowercase letters of the given length
def randomString(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

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
    if imgUrl:
        imagePath = '/tmp/{0}.png'.format(randomString(8))
        download(imgUrl, imagePath)

    # Do the tweet loop
    tweetSuccess = False
    while tweetSuccess == False and retries > 0:
        try:
            if imagePath:
                api.update_with_media(imagePath, status=message)
            else:
                api.update_status(message)
            tweetSuccess = True
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
    for date in dates:
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
                isWaveDay, score = classifier.classify(dataTimeSlice)
                isHardToClassify |= (score >= -1.0) and (score <= 1.0)
                # Pick the time with the best score to use as the image
                if score > maxWaveScore:
                    maxWaveScore = score
                    waveImageURL = '{0}/OUT+{1}/FCST/press{2}.curr.{3}lst.d2.body.png'.format(baseURL, day, 700, time)
            except:
                logging.exception('Unable to download one of the files for day {0} time {1}'.format(day, time))
                continue
            logging.info(' - {0}Wave {1}+{2}: {3:.3f}'.format('*' if isWaveDay else '', date.isoformat(), time, score))
        if isWaveDay:
            waveDays.add(date)

    return waveDays, waveImageURL

# Detect XC days
def goodXCDays(classifier, baseURL, times, lookahead, startCoordinate, endCoordinate):
    xcDays = set()
    for day in range(lookahead):
        date = datetime.date.today() + datetime.timedelta(day)
        isXcDay = False
        isHardToClassify = False
        for time in times:
            data = {}
            dims = ()
            try:
                for dataStr in classifier.requiredData():
                    url = '{0}/OUT+{1}/FCST/{2}.curr.{3}lst.d2.data'.format(baseURL, day, dataStr, time)
                    response = urlopen(url)
                    (data[dataStr], dims) = raspdata.parseData(response)
                score = classifier.score(startCoordinate, endCoordinate, dims, data)
                isXcDay = classifier.classify(startCoordinate, endCoordinate, dims, data)
                isHardToClassify |= (score >= -1.0) and (score <= 1.0)
            except:
                logging.exception('Unable to download one of the files for day {0} time {1}'.format(day, time))
                continue
            logging.info(' - {0}XC {1}+{2}: {3:.3f}'.format('*' if isXcDay else '', date.isoformat(), time, score))
        if isXcDay:
            xcDays.add(date)

    return xcDays

if __name__=='__main__':

    # Arguments
    parser = argparse.ArgumentParser(description='Tweet about good soaring forecasts')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Do not actually tweet anything.')
    parser.add_argument('-l', '--log-path', type=str, default='/home/pi', metavar='path', help='Logging path')
    parser.add_argument('-u', '--wave-url', type=str, default='https://rasp.nfshost.com/hollister', metavar='url', help='Base URL for wave RASP data')
    parser.add_argument('-v', '--xc-url', type=str, default='https://rasp.nfshost.com/norcal-coast', metavar='url', help='Base URL for XC RASP data')
    parser.add_argument('-d', '--wave-lookahead', type=int, default=3, metavar='ndays', help='How many days to look ahead for wave forecasts')
    parser.add_argument('-e', '--xc-lookahead', type=int, default=7, metavar='ndays', help='How many days to look ahead for XC forecasts')
    parser.add_argument('-t', '--wave-times', nargs='+', type=int, metavar='lst', default=[1000, 1100, 1200, 1300, 1400, 1500, 1600], help='List of local times to check for wave conditions')
    parser.add_argument('-s', '--xc-times', nargs='+', type=int, default=[1400], metavar='lst', help='List of local times to check for XC conditions')
    parser.add_argument('-a', '--xc-start-coordinate', nargs=2, type=int, default=xcscore.RELEASE_RANCH, metavar='x', help='Starting coordinate for XC classification')
    parser.add_argument('-b', '--xc-end-coordinate', nargs=2, type=int, default=xcscore.BLACK_MOUNTAIN, metavar='x', help='End coordinate for XC classification')
    parser.add_argument('-c', '--wave-classifier', type=str, default='KCVH', metavar='name', help='Name of the wave classifier')
    parser.add_argument('-f', '--xc-classifier', type=str, default='KCVH', metavar='name', help='Name of the XC classifier')
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
    state = {
        'wave-days': set(),
        'xc-days': set()
    }
    try:
        file = open('.state.json', 'r')
        state = json.load(file)
        dates = set()
        for dateStr in state['wave-days']:
            (y,m,d) = re.search('(\d+)-(\d+)-(\d+)', dateStr).groups()
            dates.add(datetime.date(int(y), int(m), int(d)))
        state['wave-days'] = dates
        dates = set()
        for dateStr in state['xc-days']:
            (y,m,d) = re.search('(\d+)-(\d+)-(\d+)', dateStr).groups()
            dates.add(datetime.date(int(y), int(m), int(d)))
        state['xc-days'] = dates
        file.close()
    except (IOError, ValueError) as err:
        logging.info('State file not opened: {0}'.format(err))

    # We spawn threads for tweeting, since we want to potentially do a long-waiting
    # retry loop in case something is temporarily-wrong with the network.
    tweetThreads = []

    waveClassifier = wavescore.WaveClassifierFactory.classifier(args.wave_classifier)
    xcClassifier = xcscore.XCClassifierFactory.classifier(args.xc_classifier)

    # Run wave day detection
    (waveDays, waveImageURL) = goodWaveDays(waveClassifier, args.wave_url, args.wave_times, args.wave_lookahead)
    # Remove any days we have already notified on
    waveDays -= state['wave-days']
    state['wave-days'] |= waveDays
    if len(waveDays) > 0:
        tweetString = 'Wave Alert! These days may have wave: ' + daysString(waveDays) + '.'
        tweetString += '\n.\n' + args.wave_url

        # Try to tweet it out
        tweetThread = threading.Thread(target=tweet, args=(tweetString, 4, waveImageURL, args.dry_run))
        tweetThreads.append(tweetThread)
        tweetThread.start()
    else:
        logging.info('I do not see wave in the forecast.')

    # Run XC day detection
    xcDays = goodXCDays(xcClassifier, args.xc_url, args.xc_times, args.xc_lookahead, tuple(args.xc_start_coordinate), tuple(args.xc_end_coordinate))
    # Remove any days we have already notified on
    xcDays -= state['xc-days']
    state['xc-days'] |= xcDays
    if len(xcDays) > 0:
        tweetString = 'XC Alert! These days may be runnable: ' + daysString(xcDays) + '.'
        tweetString += '\n.\n' + args.xc_url

        # Try to tweet it out
        tweetThread = threading.Thread(target=tweet, args=(tweetString, 4, None, args.dry_run))
        tweetThreads.append(tweetThread)
        tweetThread.start()
    else:
        logging.info('I do not see XC in the forecast.')

    # Write state back
    with open('.state.json', 'w+', encoding='utf-8') as file:
        state['wave-days'] = [date.strftime(u'%Y-%m-%d') for date in state['wave-days']]
        state['xc-days'] = [date.strftime(u'%Y-%m-%d') for date in state['xc-days']]
        #json.dump(state, file)
        # The JSON module is so damn dumb
        file.write(str(json.dumps(state)))

    # Wait for all threads to complete
    for thread in tweetThreads:
        thread.join()
