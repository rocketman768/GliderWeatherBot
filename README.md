# GliderWeatherBot

![](https://travis-ci.com/rocketman768/GliderWeatherBot.svg?branch=develop)

This is a Twitter bot that reads RASP data and tweets when it decides conditions are good for flying. The original bot is [KCVHGliderWeather](https://twitter.com/GliderKcvh).

## Copyright and License

GliderWeatherBot is copyright Philip G. Lee 2018 and licensed under the GPLv3. Please see COPYING.txt.

## Goals

It is not this project's ambition to predict _actually_ good days, but rather to look at the forecast and predict when a normal glider pilot would decide to go flying.

I want this project is to keep it as simple as possible. I don't care about deep neural networks, and with the extremely limited datasets we can make, I doubt they are useful anyway.

I would also like to tune the prediction to be a little on the optimistic side to push the recall close to 100% and to encourage more flying.

## Learning

It is necessary that before you set up the bot to run on your region that you collect training data and run the learning algorithms so that the bot can make the right decisions for you. You may use the `download-rasp.py` script to grab all the raw data from your RASP provider (please run with `--help` to see the options).

After your dataset is collected, construct a dataset `.json` file like `xc-dataset.json` or `wave-dataset.json`. Then, run `xcscore.py` or `wavescore.py` with the appropriate options (again, see their `--help`). This will provide you with the SVM weights and bias that specify the classifier.

## Setup

Please download the following packages (by `apt-get` or whatever).

 - python
 - python-future
 - python-matplotlib
 - python-tweepy
 - python-sklearn

Figure out what options you need to pass to the `twitterbot.py` script. Please run

    $ ./twitterbot.py --help

...for a list of options you can set.

Then, put these options, your twitter developer credentials, and your classifier parameters in a script like this (say `runtwitterbot.sh`):

    #!/bin/bash

    cd $(dirname /path/to/twitterbot.py)

    export WEATHERBOT_CONSUMER_KEY="asdf"
    export WEATHERBOT_CONSUMER_SECRET="jkl"
    export WEATHERBOT_ACCESS_TOKEN="asdfjkl"
    export WEATHERBOT_TOKEN_SECRET="jklasdf"
    export WEATHERBOT_WAVE_WEIGHT="1:2:3:4:5:6:7:8:9"
    export WEATHERBOT_WAVE_BIAS="42"
    export WEATHERBOT_WAVE_THRESHOLD="0"
    export WEATHERBOT_XC_WEIGHT="1:2:3"
    export WEATHERBOT_XC_BIAS="24"
    export WEATHERBOT_XC_THRESHOLD="0"

    ./twitterbot.py --wave-url 'https://...' ...

To run this on a daily basis, edit the crontab appropriately (with `$ crontab -e`) to call this script.

## Developing New Classifiers

Please see `AbstractWaveClassifier` and `AbstractXCClassifier` classes and subclass them.
