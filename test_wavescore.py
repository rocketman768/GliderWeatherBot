#!/usr/bin/env python

import datasource
import raspdata
import wavescore

def test_classifierFactory():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        assert classifier

def test_feature():
    dataSlice = datasource.ArchivedRASPDataTimeSlice(
        datasource.ArchivedRASPDataSource('test-data'),
        1400
    )
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        feature = classifier.feature(dataSlice)
        assert type(feature) == list
        assert len(feature) == len(classifier.weight)
        for item in feature:
            assert type(item) == float

def test_classify():
    dataSlice = datasource.ArchivedRASPDataTimeSlice(
        datasource.ArchivedRASPDataSource('test-data'),
        1400
    )
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        c, score = classifier.classify(dataSlice)
        assert type(c) == bool
        assert type(score) == float
