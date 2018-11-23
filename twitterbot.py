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
import logging
import os
import random
import string
import threading
import time
import tweepy
import urllib2

import raspdata
import wavescore
import xcscore

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

# Environment variables
consumer_key = os.environ['WEATHERBOT_CONSUMER_KEY']
consumer_secret = os.environ['WEATHERBOT_CONSUMER_SECRET']
access_token = os.environ['WEATHERBOT_ACCESS_TOKEN']
access_token_secret = os.environ['WEATHERBOT_TOKEN_SECRET']

# Set up Twitter API
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Set up logging
logging.basicConfig(
    filename=None if args.dry_run else '{0}/gliderweatherbot.log'.format(args.log_path),
    level=logging.DEBUG,
    format='%(asctime)s %(message)s'
)

# Return a random string of lowercase letters of the given length
def randomString(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

# Download the file with the specified url to the given path
def download(url, path):
    try:
        response = urllib2.urlopen(url)
        data = response.read()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print('ERROR: resource not found on server')
        return
    with open(path, 'w') as output:
        output.write(data)

# This function blocks for 30 minutes for each retry.
def tweet(message, retries, imgUrl=None, dryRun=False):
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
def daysString(dayOffsets):
    ret = ''
    first = True
    for day in dayOffsets:
        date = datetime.date.today() + datetime.timedelta(day)
        ret += '' if first else ', '
        ret += date.strftime("%A %d %b")
        first = False
    return ret

# Returns a set of good wave days and an image URL
def goodWaveDays(classifier):
    waveDays = set()
    maxWaveScore = -1000.0
    waveImageURL = None
    baseURL = args.wave_url
    times=args.wave_times
    for day in range(args.wave_lookahead):
        date = datetime.date.today() + datetime.timedelta(day)
        isWaveDay = False
        isHardToClassify = False
        for time in times:
            data = {}
            dims = ()
            try:
                for dataStr in classifier.requiredData():
                    url = '{0}/OUT+{1}/FCST/{2}.curr.{3}lst.d2.data'.format(baseURL, day, dataStr, time)
                    response = urllib2.urlopen(url)
                    (data[dataStr], dims) = raspdata.parseData(response)
                score = classifier.score(dims, data)
                isWaveDay = classifier.classify(dims, data)
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
            waveDays.add(day)

    return waveDays, waveImageURL

# Detect XC days
def goodXCDays(classifier):
    xcDays = set()
    baseURL = args.xc_url
    times = args.xc_times
    startCoordinate = tuple(args.xc_start_coordinate)
    endCoordinate = tuple(args.xc_end_coordinate)
    for day in range(args.xc_lookahead):
        date = datetime.date.today() + datetime.timedelta(day)
        isXcDay = False
        isHardToClassify = False
        for time in times:
            data = {}
            dims = ()
            try:
                for dataStr in classifier.requiredData():
                    url = '{0}/OUT+{1}/FCST/{2}.curr.{3}lst.d2.data'.format(baseURL, day, dataStr, time)
                    response = urllib2.urlopen(url)
                    (data[dataStr], dims) = raspdata.parseData(response)
                score = classifier.score(startCoordinate, endCoordinate, dims, data)
                isXcDay = classifier.classify(startCoordinate, endCoordinate, dims, data)
                isHardToClassify |= (score >= -1.0) and (score <= 1.0)
            except:
                logging.exception('Unable to download one of the files for day {0} time {1}'.format(day, time))
                continue
            logging.info(' - {0}XC {1}+{2}: {3:.3f}'.format('*' if isXcDay else '', date.isoformat(), time, score))
        if isXcDay:
            xcDays.add(day)

    return xcDays

with open('version.txt') as vFile:
    logging.info('Version {0}'.format(vFile.readline()))

# We spawn threads for tweeting, since we want to potentially do a long-waiting
# retry loop in case something is temporarily-wrong with the network.
tweetThreads = []

waveClassifier = wavescore.WaveClassifierFactory.classifier(args.wave_classifier)
xcClassifier = xcscore.XCClassifierFactory.classifier(args.xc_classifier)

# Run wave day detection
(waveDays, waveImageURL) = goodWaveDays(waveClassifier)
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
xcDays = goodXCDays(xcClassifier)
if len(xcDays) > 0:
    tweetString = 'XC Alert! These days may be runnable: ' + daysString(xcDays) + '.'
    tweetString += '\n.\n' + args.xc_url

    # Try to tweet it out
    tweetThread = threading.Thread(target=tweet, args=(tweetString, 4, None, args.dry_run))
    tweetThreads.append(tweetThread)
    tweetThread.start()
else:
    logging.info('I do not see XC in the forecast.')

# Wait for all threads to complete
for thread in tweetThreads:
    thread.join()
