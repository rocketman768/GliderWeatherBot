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
import os

import raspdata

class AbstractWaveClassifier:
    def requiredData(self):
        raise NotImplementedError()

    def feature(self, dims, dataDict):
        raise NotImplementedError()

    def score(self, dims, dataDict):
        raise NotImplementedError()

    def classify(self, dims, dataDict):
        raise NotImplementedError()

class KCVHWaveClassifier:
    def __init__(self):
        self.weight = [-0.1, -0.1, -0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.4]
        self.bias = -1.579
        self.threshold = 0.0

        # Allow override from environment variables
        if 'WEATHERBOT_WAVE_WEIGHT' in os.environ:
            self.weight = [float(x) for x in os.environ['WEATHERBOT_WAVE_WEIGHT'].split(':')]
        if 'WEATHERBOT_WAVE_BIAS' in os.environ:
            self.bias = float(os.environ['WEATHERBOT_WAVE_BIAS'])
        if 'WEATHERBOT_WAVE_THRESHOLD' in os.environ:
            self.threshold = float(os.environ['WEATHERBOT_WAVE_THRESHOLD'])

    def requiredData(self):
        return ('press500', 'press700', 'press850', 'blcloudpct')

    def feature(self, dims, dataDict):
        data500mb = dataDict['press500']
        data700mb = dataDict['press700']
        data850mb = dataDict['press850']
        dataCloudCover = dataDict['blcloudpct']
        # NOTE: I would rather just add a separate feature for cloud cover,
        # but right now I do not have enough data to do that. The SVM ends up
        # learning the wrong weights at the moment. So, incorporate cloud cover
        # as a modulation of the lift.
        def cloudCoverFactor(x,y):
            return 1.0 - pow(dataCloudCover(x,y) / 100.0, 8.0)
        def usableLift500(x,y):
            return data500mb(x,y) * cloudCoverFactor(x,y)
        def usableLift700(x,y):
            return data700mb(x,y) * cloudCoverFactor(x,y)
        def usableLift850(x,y):
            return data850mb(x,y) * cloudCoverFactor(x,y)

        min500, max500 = raspdata.minMax(data500mb, dims)
        min700, max700 = raspdata.minMax(data700mb, dims)
        min850, max850 = raspdata.minMax(data850mb, dims)
        liftArea500 = raspdata.area(usableLift500, dims, lambda x: x >= 150)
        liftArea700 = raspdata.area(usableLift700, dims, lambda x: x >= 150)
        liftArea850 = raspdata.area(usableLift850, dims, lambda x: x >= 150)
        cloudCoverArea = raspdata.area(dataCloudCover, dims, lambda x: x >= 90)

        # NOTE: for numerical stability, it is important that the features be
        # roughly centered and of the same magnitude
        fMean = [-375.6296296296296, -513.5555555555555, -616.0370370370371, 398.0, 601.1111111111111, 676.5925925925926, 0.025068635068635065, 0.024910644910644906, 0.035129391681659704]
        fStd = [209.48245717201664, 280.6614321672517, 362.9489793224674, 293.31376197335675, 342.8986820809311, 295.1233589232939, 0.03235570269886821, 0.028779773140666973, 0.030252204765808442]
        fRaw = [min500,
                min700,
                min850,
                max500,
                max700,
                max850,
                liftArea500,
                liftArea700,
                liftArea850]
                #cloudCoverArea]

        return [(x - m) / s for (x,m,s) in zip(fRaw, fMean, fStd)]

    def score(self, dims, dataDict):
        feature = self.feature(dims, dataDict)
        return raspdata.score(feature, self.weight, self.bias)

    def classify(self, dims, dataDict):
        return True if self.score(dims, dataDict) >= self.threshold else False

class WaveClassifierFactory:
    @staticmethod
    def classifier(name):
        classFromName = {'KCVH': KCVHWaveClassifier}
        return classFromName[name]()

def featuresAndLabelsFromDataset(pos, neg, classifier):
    features = []
    labels = []
    for item in pos:
        for time in item[1]:
            (dims, dataDict) = raspdata.dataFromDirectory(item[0], classifier.requiredData(), time)
            features.append(classifier.feature(dims, dataDict))
            labels.append(1.0)

    for item in neg:
        for time in item[1]:
            (dims, dataDict) = raspdata.dataFromDirectory(item[0], classifier.requiredData(), time)
            features.append(classifier.feature(dims, dataDict))
            labels.append(0.0)

    return features, labels

def evaluateDataset(pos, neg, classifier):
    nPos = sum(len(item[1]) for item in pos)
    nNeg = sum(len(item[1]) for item in neg)
    truePos = 0
    trueNeg = 0
    print('## Positives ##')
    for item in pos:
        for time in item[1]:
            (dims, dataDict) = raspdata.dataFromDirectory(item[0], classifier.requiredData(), time)
            feature = classifier.feature(dims, dataDict)
            score = classifier.score(dims, dataDict)
            if score >= classifier.threshold:
                truePos += 1
            print(' - {0}-{1}: {2:.3f}'.format(item[0], time, score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))
    print ('## Negatives ##')
    for item in neg:
        for time in item[1]:
            (dims, dataDict) = raspdata.dataFromDirectory(item[0], classifier.requiredData(), time)
            feature = classifier.feature(dims, dataDict)
            score = classifier.score(dims, dataDict)
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
    parser = argparse.ArgumentParser(description='Learn good wave days from a dataset')
    parser.add_argument('-i', '--dataset', type=str, default='data/kcvh-wave.json', metavar='path', help='Dataset json file')
    parser.add_argument('-c', '--classifier', type=str, default='KCVH', metavar='name', help='Name of the classifier')
    args = parser.parse_args()

    positives = []
    negatives = []
    with open(args.dataset) as file:
        dataset = json.load(file)
        positives = dataset['positive']
        negatives = dataset['negative']

    classifier = WaveClassifierFactory.classifier(args.classifier)
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
