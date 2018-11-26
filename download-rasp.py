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
import json
import urllib2
import threading

import pgzfile
import raspdata

def splitList(fullList, numParts):
    ret = []
    n = len(fullList)
    if numParts > n:
        raise Exception
    for part in range(numParts):
        ret.append([fullList[i] for i in range(part * n // numParts, (part+1) * n // numParts)])
    return ret

def downloadRaspFiles(filesToDownload, baseURL, forecastOffset, outputDir):
    for raspFile in filesToDownload:
        print('Downloading ' + raspFile + '...')
        url = baseURL + '/OUT+' + str(forecastOffset) + '/FCST/' + raspFile
        try:
            response = urllib2.urlopen(url)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print('ERROR: resource not found on server: {0}'.format(raspFile))
            continue
        isPgz = args.binary and '.data' in raspFile
        filename = '{0}/{1}{2}'.format(outputDir, raspFile, '.pgz' if isPgz else '')
        with open(filename, 'w') as output:
            if isPgz:
                (data, dims) = raspdata.parseData(response)
                pgzfile.writePgzImage(data, dims, output)
            else:
                output.write(response.read())

if __name__=='__main__':

    parser = argparse.ArgumentParser(description='Download RASP files')
    parser.add_argument('-o', '--output-dir', type=str)
    parser.add_argument('-u', '--url', type=str, default='https://rasp.nfshost.com/hollister')
    parser.add_argument('-d', '--day', type=int, default=0, help='Offset in days from today')
    parser.add_argument('-t', '--type', type=str, choices=['all', 'raw', 'images'], default='raw', help='What kind of files to download')
    parser.add_argument('-b', '--binary', action='store_true', help='Write data files in binary format')
    parser.add_argument('-c', '--times', nargs='+', type=int, default=[1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800], metavar='lst', help='What times to download data for')
    args = parser.parse_args()

    dataNames = (
        'blcloudpct',
        'blcwbase',
        'bltopvariab',
        'bltopwinddir',
        'bltopwindspd',
        'blwinddir',
        'blwindshear',
        'blwindspd',
        'bsratio',
        'cape',
        'dbl',
        'dwcrit',
        'hbl',
        'hglider',
        'hwcrit',
        'press500',
        'press500wdir',
        'press500wspd',
        'press700',
        'press700wdir',
        'press700wspd',
        'press850',
        'press850wdir',
        'press850wspd',
        'sfcdewpt',
        'sfcshf',
        'sfcsunpct',
        'sfctemp',
        'sfcwinddir',
        'sfcwindspd',
        'wblmaxmin',
        'wstar',
        'zblcl',
        'zblcldif',
        'zsfclcl',
        'zsfclcldif',
        'zwblmaxmin'
    )

    pngTypes = ('foot', 'head', 'side', 'body')

    filesToDownload = []
    dataFiles = ['{0}.curr.{1}lst.d2.data'.format(dataStr, time) for dataStr in dataNames for time in args.times]
    imageFiles = ['{0}.curr.{1}lst.d2.{2}.png'.format(dataStr, time, type) for dataStr in dataNames for time in args.times for type in pngTypes]
    if args.type == 'all':
        filesToDownload = dataFiles + imageFiles
    elif args.type == 'raw':
        filesToDownload = dataFiles
    elif args.type == 'images':
        filesToDownload = imageFiles

    NUM_THREADS = 4
    filesToDownloadPerThread = splitList(filesToDownload, NUM_THREADS)
    threads = []
    for i in range(NUM_THREADS):
        threads.append(threading.Thread(None, target=downloadRaspFiles, args=(filesToDownloadPerThread[i], args.url, args.day, args.output_dir)))
        threads[i].start()
    for i in range(NUM_THREADS):
        threads[i].join()
