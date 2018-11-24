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

parser = argparse.ArgumentParser(description='Download RASP files')
parser.add_argument('-o', '--output-dir', type=str)
parser.add_argument('-u', '--url', type=str, default='https://rasp.nfshost.com/hollister')
parser.add_argument('-d', '--day', type=int, default=0, help='Offset in days from today')
parser.add_argument('-t', '--type', type=str, choices=['all', 'raw', 'images'], default='raw', help='What kind of files to download')
parser.add_argument('-b', '--binary', action='store_true', help='Write data files in binary format')
args = parser.parse_args()

baseURL = args.url
forecastOffset = args.day
outputDir = args.output_dir

raspFileList=[]
with open('rasp-files.json') as f:
    raspFileList = json.load(f)

filesToDownload = []
if args.type == 'all':
    filesToDownload = raspFileList
elif args.type == 'raw':
    filesToDownload = [x for x in raspFileList if x.count('.data') > 0]
elif args.type == 'images':
    filesToDownload = [x for x in raspFileList if x.count('.png') > 0]

def splitList(fullList, numParts):
    ret = []
    n = len(fullList)
    if numParts > n:
        raise Exception
    for part in range(numParts):
        ret.append([fullList[i] for i in range(part * n // numParts, (part+1) * n // numParts)])
    return ret

def downloadRaspFiles(filesToDownload):
    for raspFile in filesToDownload:
        print('Downloading ' + raspFile + '...')
        url = baseURL + '/OUT+' + str(forecastOffset) + '/FCST/' + raspFile
        try:
            response = urllib2.urlopen(url)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print('ERROR: resource not found on server')
            continue
        isPgz = args.binary and '.data' in raspFile
        filename = '{0}/{1}{2}'.format(outputDir, raspFile, '.pgz' if isPgz else '')
        with open(filename, 'w') as output:
            if isPgz:
                (data, dims) = raspdata.parseData(response)
                pgmfile.writePgzImage(data, dims, output)
            else:
                output.write(response.read())

NUM_THREADS = 4
filesToDownloadPerThread = splitList(filesToDownload, NUM_THREADS)
threads = []
for i in range(NUM_THREADS):
    threads.append(threading.Thread(None, target=downloadRaspFiles, args=(filesToDownloadPerThread[i],)))
    threads[i].start()
for i in range(NUM_THREADS):
    threads[i].join()
