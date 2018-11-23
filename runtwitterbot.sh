#!/bin/bash

# To install, use `crontab -e` to run this script once each morning
# after all the rasp files become available

# Make the directory of this script the working directory
cd $(dirname $0)

# Set these keys before deployment
export WEATHERBOT_CONSUMER_KEY=
export WEATHERBOT_CONSUMER_SECRET=
export WEATHERBOT_ACCESS_TOKEN=
export WEATHERBOT_TOKEN_SECRET=

# Execute the bot
./twitterbot.py
