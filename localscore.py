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
import math
import os
#import sys
from builtins import zip
from io import open

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

import datasource
import raspdata
import utilities

# NOTE: eyeballed
KCVH = (15,91)

class KCVHLocalClassifier:
    def __init__(self):
        self.weight = [0.96896464, -0.41886308, 1.04899457]
        self.bias = -0.351320757116
        self.threshold = 0.0

    def imageSummary(self, raspDataTimeSlice):
        ret = '/tmp/{0}.png'.format(utilities.randomString(8))

        try:
            with raspDataTimeSlice.open('hwcrit') as file:
                (dataHcrit, dims) = raspdata.parseData(file)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return None

        imageData = [[dataHcrit(x, y) for x in range(0, KCVH[0] + 16)] for y in reversed(range(KCVH[1] - 16, KCVH[1] + 16))]

        plt.clf()
        plt.imshow(imageData, cmap=plt.cm.get_cmap('seismic'), vmin=0, vmax=7000, interpolation='quadric')
        plt.colorbar()
        plt.plot([KCVH[0]], [16], 'ko')
        plt.text(KCVH[0], 16-1, 'KCVH', horizontalalignment='right', color='red')
        plt.axis('off')
        plt.title('Hcrit at {0} lst'.format(raspDataTimeSlice.time()))
        plt.savefig(ret, bbox_inches='tight', pad_inches=0)

        return ret

    def feature(self, raspDataTimeSlice):
        gridResolution_km = 4.0

        with raspDataTimeSlice.open('hwcrit') as file:
            (dataHcrit, dims) = raspdata.parseData(file)
        with raspDataTimeSlice.open('zsfclcldif') as file:
            (cuPot, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('zsfclcl') as file:
            (cuBase, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('sfcsunpct') as file:
            (dataSfcSun, _) = raspdata.parseData(file)

        def roi(x, y):
            distance_km = gridResolution_km * math.sqrt( (x-KCVH[0])**2 + (y - KCVH[1])**2 )
            maxDistance_km = 8000.0 / 3281.0 * 30.0
            return 1.0 if distance_km < maxDistance_km else 0.0

        def distanceFromKCVH_km(x,y):
            return gridResolution_km * math.sqrt( (x-KCVH[0])**2 + (y - KCVH[1])**2 )

        def glideRatioFromHcrit(x,y):
            hcrit_km = dataHcrit(x,y) / 3281.0
            return distanceFromKCVH_km(x,y) / hcrit_km if roi(x,y) > 0.0 else 9999.0

        def glideRatioFromCloudbase(x,y):
            return distanceFromKCVH_km(x,y) / (cuBase(x,y) / 3281.0)

        def sunnyCuPredicate(x,y):
            cuLikelihood = 1.0 if cuPot(x,y) > 300 else 0.0
            sunny = 1.0 if dataSfcSun(x,y) > 40.0 else 0.0
            return roi(x,y) * sunny * cuLikelihood
        def sunnyCuGlideRatio(x,y):
            return sunnyCuPredicate(x,y) * glideRatioFromCloudbase(x,y)
        def sunnyCuBase(x,y):
            return sunnyCuPredicate(x,y) * cuBase(x,y)

        roiArea = raspdata.area(roi, dims, lambda x: x > 0.0)
        sunnyCuArea = sum([sunnyCuPredicate(x,y) for x in range(dims[0]) for y in range(dims[1])])

        areaWhereGlideRatioIsSmall = raspdata.area(glideRatioFromHcrit, dims, lambda x: x < 30.0) / roiArea
        avgSunnyCuGlideRatio = raspdata.integral(sunnyCuGlideRatio, dims) / sunnyCuArea if sunnyCuArea > 0.0 else 60.0
        avgSunnyCuBase = raspdata.integral(sunnyCuBase, dims) / (sunnyCuArea + 0.001)

        #asdf = [[dataHcrit(x, y) for x in range(dims[0])] for y in range(dims[1])]
        #asdf = [[dataHcrit(x, y) for x in range(0, KCVH[0] + 16)] for y in reversed(range(KCVH[1] - 16, KCVH[1] + 16))]
        #asdf = [[sunnyCuPredicate(x, y) for x in range(dims[0])] for y in reversed(range(dims[1]))]
        #plt.imshow(asdf, cmap=plt.cm.get_cmap("seismic"), vmin=0, vmax=7000, interpolation='quadric')
        #plt.colorbar()
        #plt.plot([KCVH[0]], [16], 'ko')
        #plt.text(KCVH[0], 16-1, 'KCVH', horizontalalignment='right', color='red')
        #plt.axis('off')
        #plt.title('Hcrit')
        #plt.savefig('/tmp/foo.png', bbox_inches='tight', pad_inches=0)
        #plt.show()

        fRaw = [areaWhereGlideRatioIsSmall, avgSunnyCuGlideRatio, avgSunnyCuBase]
        fMean = [0.15390316205533594, 34.15506672965842, 5078.433048507441]
        fStd = [0.06218479626157944, 11.551840246133619, 1535.9700754572946]

        return [(x - m) / s for (x,m,s) in zip(fRaw, fMean, fStd)]
        #return fRaw

    def classify(self, raspDataTimeSlice):
        feature = self.feature(raspDataTimeSlice)
        score = raspdata.score(feature, self.weight, self.bias)
        classification = True if score >= self.threshold else False
        return classification, score

class LocalClassifierFactory:
    @staticmethod
    def __classFromName():
        return {'KCVH': KCVHLocalClassifier}
    @staticmethod
    def allClassifierNames():
        return LocalClassifierFactory.__classFromName().keys()
    @staticmethod
    def classifier(name):
        classFromName = {'KCVH': KCVHLocalClassifier}
        return LocalClassifierFactory.__classFromName()[name]()

def featuresAndLabelsFromDataset(pos, neg, classifier):
    features = []
    labels = []
    for item in pos:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            features.append(classifier.feature(dataTimeSlice))
            labels.append(1.0)

    for item in neg:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            features.append(classifier.feature(dataTimeSlice))
            labels.append(0.0)

    return features, labels

def evaluateDataset(pos, neg, classifier):
    nPos = sum(len(item[1]) for item in pos)
    nNeg = sum(len(item[1]) for item in neg)
    truePos = 0
    trueNeg = 0
    print('## Positives ##')
    for item in pos:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            feature = classifier.feature(dataTimeSlice)
            _, score = classifier.classify(dataTimeSlice)
            if score >= classifier.threshold:
                truePos += 1
            print(' - {0}-{1}: {2:.3f}'.format(item[0], time, score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))
    print ('## Negatives ##')
    for item in neg:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            feature = classifier.feature(dataTimeSlice)
            _, score = classifier.classify(dataTimeSlice)
            if score < classifier.threshold:
                trueNeg += 1
            print(' - {0}-{1}: {2:.3f}'.format(item[0], time, score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))

    falseNeg = nPos - truePos
    falsePos = nNeg - trueNeg
    precision = float(truePos) / (truePos + falsePos) if truePos > 0 else 0
    recall = float(truePos) / nPos if truePos > 0 else 0
    print('Precision: {0:.1f}%'.format(100 * precision))
    print('Recall: {0:.1f}%'.format(100* recall))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Learn good local days from a dataset')
    parser.add_argument('-i', '--dataset', type=str, default='data/kcvh-local.json', metavar='path', help='Dataset json file')
    parser.add_argument('-c', '--classifier', type=str, default='KCVH', metavar='name', help='Name of the classifier')
    args = parser.parse_args()

    positives = []
    negatives = []
    with open(args.dataset) as file:
        dataset = json.load(file)
        positives = dataset['positive']
        negatives = dataset['negative']

    classifier = LocalClassifierFactory.classifier(args.classifier)
    (features, labels) = featuresAndLabelsFromDataset(positives, negatives, classifier)

    (fMin, fMax, fMean, fStd) = raspdata.featureStats(features)
    print('Feature min: {0}'.format(fMin))
    print('Feature max: {0}'.format(fMax))
    print('Feature mean: {0}'.format(fMean))
    print('Feature std: {0}'.format(fStd))

    evaluateDataset(positives, negatives, classifier)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
    print('\n\n')

    (classifier.weight, classifier.bias) = raspdata.learn(features, labels)

    evaluateDataset(positives, negatives, classifier)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
