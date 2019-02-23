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
import itertools
import json
import math
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import os
from builtins import range, zip
from io import open

import datasource
import raspdata
import utilities

# Just eyeballing these locations and measuring pixels.
# NOTE: in the data, y = 0 is the south edge
RELEASE_RANCH = (19, 80)
BLACK_MOUNTAIN = (24, 56)

# The score must represent "distance" between nodes such that bigger distance
# is worse than smaller distance.
# The score must be nonnegative and symmetric. I.e.
#  score(u,v) = score(v,u) >= 0
def score(u, v, hcrit, vvert, debug):
    hval_ft = (raspdata.at(u, hcrit) + raspdata.at(v, hcrit)) / 2.0
    vval_fpm = (raspdata.at(u, vvert) + raspdata.at(v, vvert)) / 2.0
    dist = math.sqrt((u[0] - v[0]) * (u[0] - v[0]) + (u[1] - v[1]) * (u[1] - v[1]))
    # Around Hollister, I would say hcrit < 5000 ft is not XC at all, and
    # if we get to 8000ft, that is like 200fpm convergence
    equiv_fpm = vval_fpm + ((hval_ft - 6000.0) / 2000.0 * 200.0)
    distRatio = math.exp(-equiv_fpm / 500.0)
    if debug:
        print('{0}, {1}, {2}, {3}'.format(hval_ft, vval_fpm, equiv_fpm, distRatio))
    return distRatio * dist

def neighbors(u, width, height):
    ret = set()
    left = max(0,u[0]-1)
    right = min(width-1,u[0]+1)
    up = max(0,u[1]-1)
    down = min(height-1,u[1]+1)
    ret.add((left, u[1]))
    ret.add((right, u[1]))
    ret.add((u[0], up))
    ret.add((u[0], down))
    ret.add((left, up))
    ret.add((right, up))
    ret.add((left, down))
    ret.add((right, down))
    # Avoid 'u' being its own neighbor
    ret = ret - set({u})
    return ret

def allNodes(width, height):
    return itertools.product(range(width), range(height))

# Use Dijkstra's algorithm to find the best path from 'a' to 'b'
def bestPath(a, b, width, height, hcrit, vvert):
    nodes = allNodes(width, height)
    scoreFromA = {}
    prev = {}
    pushed = {}
    for node in nodes:
        scoreFromA[node] = float('inf')
        pushed[node] = False
    scoreFromA[a] = 0

    nodeQueue = [a]
    pushed[a] = True
    while len(nodeQueue) > 0:
        u = nodeQueue[0]
        nodeQueue.pop(0)
        #print('u: {0}'.format(u))
        for v in neighbors(u, width, height):
            if not pushed[v]:
                nodeQueue.append(v)
                pushed[v] = True

            altScore = scoreFromA[u] + score(u, v, hcrit, vvert, False)
            if altScore < scoreFromA[v]:
                scoreFromA[v] = altScore
                prev[v] = u
    # TODO: reuse everything computed so far for any endpoint
    reversedPath = [b]
    while reversedPath[-1] != a:
        #score(reversedPath[-1], prev[reversedPath[-1]], hcrit, vvert, True)
        reversedPath.append(prev[reversedPath[-1]])
    #print('Score: {0}'.format(scoreFromA[b]))
    #print('Path: {0}'.format([x for x in reversed(reversedPath)]))
    return [x for x in reversed(reversedPath)]

class AbstractXCClassifier:
    def feature(self, startCoordinate, endCoordinate, raspDataTimeSlice):
        raise NotImplementedError()
    def classify(self, startCoordinate, endCoordinate, raspDataTimeSlice):
        raise NotImplementedError()

class KCVHXCClassifier(AbstractXCClassifier):
    def __init__(self):
        self.weight = [0.60975023, 0.51193634, 0.43192924]
        self.bias = -1.06425298269
        self.threshold = 0.0

        if 'WEATHERBOT_XC_WEIGHT' in os.environ:
            self.weight = [float(x) for x in os.environ['WEATHERBOT_XC_WEIGHT'].split(':')]
        if 'WEATHERBOT_XC_BIAS' in os.environ:
            self.bias = float(os.environ['WEATHERBOT_XC_BIAS'])
        if 'WEATHERBOT_XC_THRESHOLD' in os.environ:
            self.threshold = float(os.environ['WEATHERBOT_XC_THRESHOLD'])

    def imageSummary(self, raspDataTimeSlice):
        ret = '/tmp/{0}.png'.format(utilities.randomString(8))

        try:
            with raspDataTimeSlice.open('hwcrit') as file:
                (dataHcrit, dims) = raspdata.parseData(file)
            with raspDataTimeSlice.open('wblmaxmin') as f:
                wblmaxmin, _ = raspdata.parseData(f)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return None

        path = bestPath(RELEASE_RANCH, BLACK_MOUNTAIN, dims[0], dims[1], dataHcrit, wblmaxmin)
        # Flip the path upside down
        path = [(x, dims[1] - y) for (x,y) in path]

        cropOrigin = (0, 135)
        cropSize = (40, 40)

        imageData = [[dataHcrit(x, y) for x in range(dims[0])] for y in reversed(range(dims[1]))]
        # Flip the image upside down
        imageData = [[imageData[y][x] for x in range(cropOrigin[0], cropOrigin[0] + cropSize[0])] for y in range(cropOrigin[1], cropOrigin[1] + cropSize[1])]

        plt.clf()
        plt.imshow(imageData, cmap=plt.cm.get_cmap('seismic'), vmin=1000, vmax=11000, interpolation='quadric')
        plt.plot([x - cropOrigin[0] for (x,y) in path], [y - cropOrigin[1] for (x,y) in path], 'g-')
        plt.colorbar()
        plt.plot([RELEASE_RANCH[0] - cropOrigin[0]], [dims[1] - RELEASE_RANCH[1] - cropOrigin[1]], 'ko')
        plt.plot([BLACK_MOUNTAIN[0] - cropOrigin[0]], [dims[1] - BLACK_MOUNTAIN[1] - cropOrigin[1]], 'ko')
        plt.text(RELEASE_RANCH[0] - cropOrigin[0], dims[1] - RELEASE_RANCH[1] - cropOrigin[1] - 1, 'Rel. Ranch', horizontalalignment='right', color='black')
        plt.text(BLACK_MOUNTAIN[0], dims[1] - BLACK_MOUNTAIN[1] - cropOrigin[1] - 1, 'Black Mt.', horizontalalignment='right', color='black')
        plt.axis('off')
        plt.title('Hcrit and Best Path')
        plt.savefig(ret, bbox_inches='tight', pad_inches=0)
        #plt.show()

        return ret

    def feature(self, startCoordinate, endCoordinate, raspDataTimeSlice):
        with raspDataTimeSlice.open('hwcrit') as f:
            hwcrit, dims = raspdata.parseData(f)
        with raspDataTimeSlice.open('wblmaxmin') as f:
            wblmaxmin, _ = raspdata.parseData(f)

        height = dims[1]
        width = dims[0]

        path = bestPath(startCoordinate, endCoordinate, width, height, hwcrit, wblmaxmin)

        #plt.imshow([[hwcrit(x, y) for x in range(dims[0])] for y in range(dims[1])])
        #plt.plot([x for (x,y) in path],[y for (x,y) in path])
        #plt.show()
        #plt.axis('off')
        #plt.savefig('/tmp/foo.png', bbox_inches='tight', pad_inches=0)

        maxH = max([raspdata.at(u, hwcrit) for u in path])
        avgH = sum([raspdata.at(u, hwcrit) for u in path]) / len(path)
        minH = min([raspdata.at(u, hwcrit) for u in path])
        #maxV = max([raspdata.at(u, dataDict['wblmaxmin']) for u in path])
        #avgV = sum([raspdata.at(u, dataDict['wblmaxmin']) for u in path]) / len(path)

        # NOTE: normalizing the data is absolutely necessary.
        return [(maxH - 6579.0) / 2280.0, (avgH - 5689.0) / 2206.0, (minH - 4711.0) / 2154.0]

    def classify(self, startCoordinate, endCoordinate, raspDataTimeSlice):
        f = self.feature(startCoordinate, endCoordinate, raspDataTimeSlice)
        s = raspdata.score(f, self.weight, self.bias)
        classification = True if s > self.threshold else False
        return classification, s

class XCClassifierFactory:
    @staticmethod
    def __classFromName():
        return {'KCVH': KCVHXCClassifier}
    @staticmethod
    def allClassifierNames():
        return XCClassifierFactory.__classFromName().keys()
    @staticmethod
    def classifier(name):
        return XCClassifierFactory.__classFromName()[name]()

# -- Just for learning --

def featuresAndLabelsFromDataset(pos, neg, classifier, startCoordinate, endCoordinate):
    features = []
    labels = []
    for item in pos:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            features.append(classifier.feature(startCoordinate, endCoordinate, dataTimeSlice))
            labels.append(1.0)

    for item in neg:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            features.append(classifier.feature(startCoordinate, endCoordinate, dataTimeSlice))
            labels.append(0.0)

    return features, labels

def evaluateDataset(pos, neg, classifier, startCoordinate, endCoordinate):
    nPos = sum(len(item[1]) for item in pos)
    nNeg = sum(len(item[1]) for item in neg)
    truePos = 0
    trueNeg = 0
    print('## Positives ##')
    for item in pos:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            feature = classifier.feature(startCoordinate, endCoordinate, dataTimeSlice)
            _, score = classifier.classify(startCoordinate, endCoordinate, dataTimeSlice)
            if score >= classifier.threshold:
                truePos += 1
            print(' - {0}: {1:.3f}'.format(item[0], score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))
    print('## Negatives ##')
    for item in neg:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            feature = classifier.feature(startCoordinate, endCoordinate, dataTimeSlice)
            _, score = classifier.classify(startCoordinate, endCoordinate, dataTimeSlice)
            if score < classifier.threshold:
                trueNeg += 1
            print(' - {0}: {1:.3f}'.format(item[0], score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))

    falseNeg = nPos - truePos
    falsePos = nNeg - trueNeg
    precision = float(truePos) / (truePos + falsePos) if truePos > 0 else 0
    recall = float(truePos) / nPos if truePos > 0 else 0
    print('Precision: {0:.1f}%'.format(100 * precision))
    print('Recall: {0:.1f}%'.format(100* recall))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Learn good XC days from a dataset')
    parser.add_argument('-i', '--dataset', type=str, default='data/kcvh-xc.json', metavar='path', help='Dataset json file')
    parser.add_argument('-a', '--xc-start-coordinate', nargs=2, type=int, default=RELEASE_RANCH, metavar='x', help='Starting coordinate for XC classification')
    parser.add_argument('-b', '--xc-end-coordinate', nargs=2, type=int, default=BLACK_MOUNTAIN, metavar='x', help='End coordinate for XC classification')
    parser.add_argument('-c', '--classifier', type=str, default='KCVH', metavar='name', help='Name of the classifier')
    args = parser.parse_args()

    positives = []
    negatives = []
    with open(args.dataset) as file:
        dataset = json.load(file)
        positives = dataset['positive']
        negatives = dataset['negative']

    classifier = XCClassifierFactory.classifier(args.classifier)
    startCoordinate = tuple(args.xc_start_coordinate)
    endCoordinate = tuple(args.xc_end_coordinate)

    (features, labels) = featuresAndLabelsFromDataset(positives, negatives, classifier, startCoordinate, endCoordinate)

    (fMin, fMax, fMean, fStd) = raspdata.featureStats(features)
    print('Feature min: {0}'.format(fMin))
    print('Feature max: {0}'.format(fMax))
    print('Feature mean: {0}'.format(fMean))
    print('Feature std: {0}'.format(fStd))

    evaluateDataset(positives, negatives, classifier, startCoordinate, endCoordinate)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
    print('\n\n')

    (classifier.weight, classifier.bias) = raspdata.learn(features, labels)

    evaluateDataset(positives, negatives, classifier, startCoordinate, endCoordinate)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
