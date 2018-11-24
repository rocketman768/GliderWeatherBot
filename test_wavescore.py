#!/usr/bin/env python

import wavescore

def test_classifierFactory():
    for name in wavescore.WaveClassifierFactory.allClassifierNames():
        classifier = wavescore.WaveClassifierFactory.classifier(name)
        assert classifier
