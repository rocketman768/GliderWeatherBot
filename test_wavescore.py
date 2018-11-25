#!/usr/bin/env python

import raspdata
import wavescore

def test_classifierFactory():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        assert classifier

def test_requiredData():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        requiredData = classifier.requiredData()
        assert type(requiredData) == tuple
        for item in requiredData:
            assert type(item) == str

def test_feature():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        (dims, data) = raspdata.dataFromDirectory('test-data', classifier.requiredData(), 1400)
        feature = classifier.feature(dims, data)
        assert type(feature) == list
        assert len(feature) == len(classifier.weight)
        for item in feature:
            assert type(item) == float

def test_score():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        (dims, data) = raspdata.dataFromDirectory('test-data', classifier.requiredData(), 1400)
        score = classifier.score(dims, data)
        assert type(score) == float

def test_classify():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        (dims, data) = raspdata.dataFromDirectory('test-data', classifier.requiredData(), 1400)
        c = classifier.classify(dims, data)
        assert type(c) == bool
