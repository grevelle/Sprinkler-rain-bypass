#!/usr/bin/env python3

import configparser
import json
import time
import datetime

import RPi.GPIO as GPIO
import requests

# Import configuration file
config = configparser.ConfigParser()
config.read('settings.ini')


# Google Maps code to determine Lat/Lon
def getLocation():
    googleKey = config['UserInput']['googlekey']
    headers = {'content-type': 'application/json'}
    url = "https://www.googleapis.com/geolocation/v1/geolocate?key=" + googleKey
    r = requests.post(url, headers=headers)
    response = json.loads(r.text)
    latitude = (response['location']['lat'])
    longitude = (response['location']['lng'])
    return (latitude, longitude)


# Get weather from visualcrossing API
def getWeather():
    # Set start and end dates in unix format
    lookbackDays = int(config['UserInput']['weatherlookback'])
    measurementDays = int(config['UserInput']['raindays'])
    today = int(time.time())
    startdate = today - (lookbackDays * 86400)
    enddate = startdate + (measurementDays * 86400)

    # Get location from Google Maps function and load in memory
    location = getLocation()

    # Get visualcrossing API key
    visualcrossingKey = config['UserInput']['visualcrossingkey']

    # Download data, convert from JSON to Python
    url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/" + str(location[0]) + "," + str(
        location[1]) + "/" + str(int(startdate)) + "/" + str(int(enddate)) + "?key=" + visualcrossingKey + "&elements=precip&include=days"
    s = requests.get(url)

    # Convert future from JSON to Python
    futuredict = json.loads(s.text)

    # Create array to hold forecast values
    datelist2 = []

    # Parse XML into array
    for x in futuredict['days']:
        datelist2.append(x['precip'])

    # Combine past and future precip lists, return [date, 24 hr rainfall] as precipamount
    precipamount = 0
    for x in datelist2:
        precipamount = precipamount + x
    return (precipamount)


# Check if calendar dates are OK to water
def dateok():
    dt1 = datetime.datetime(year=time.gmtime()[0], month=int(
        config['UserInput']['firstmonthtowater']), day=int(config['UserInput']['firstdaytowater']))
    firstdatethisyear = time.mktime(dt1.timetuple())
    dt2 = datetime.datetime(year=time.gmtime()[0], month=int(
        config['UserInput']['lastmonthtowater']), day=int(config['UserInput']['lastdaytowater']))
    lastdatethisyear = time.mktime(dt2.timetuple())
    today = int(time.time())
    if firstdatethisyear <= today <= lastdatethisyear:
        x = True
    else:
        x = False
    return (x)


def watering_required():
    # return total rainfall
    rainfall = getWeather()

    # Rain needed on the grass
    inchesrequired = float(config['UserInput']['inchesrequired'])

    if rainfall <= inchesrequired and dateok():
        watering_needed = True
    else:
        watering_needed = False
    config['ProgramModified']['rainfall'] = str(rainfall)
    return (watering_needed)


# Setup GPIO and execute main program
def runProgram():
    # Loop this forever
    while True:
        # Get number of daily weather updates
        weatherupdatesperday = float(
            config['UserInput']['weatherupdatesperday'])

        # Setup GPIO I/O Pins to output mode
        relay_GPIO = int(config['GPIO.Pins']['relayswitch'])
        watering_enabled_GPIO = int(config['GPIO.Pins']['wateringenabled'])
        watering_disabed_GPIO = int(config['GPIO.Pins']['wateringdisabled'])
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(relay_GPIO,
                   GPIO.OUT)  # This pin controls relay switch. When ON/True, watering is disabled. Default OFF
        # This pin enables green light when watering
        GPIO.setup(watering_enabled_GPIO, GPIO.OUT)
        # This pin enables red light when watering disabled
        GPIO.setup(watering_disabed_GPIO, GPIO.OUT)

        # Set GPIO I/O Pins
        if watering_required():
            # Turn off relay switch, enable watering
            GPIO.output(relay_GPIO, False)
            GPIO.output(watering_enabled_GPIO, True)  # Turn on green light
            GPIO.output(watering_disabed_GPIO, False)  # Turn off red light
            # Update config file
            config['ProgramModified']['watering_required'] = 'True'
        else:
            # Turn on relay switch, disable watering
            GPIO.output(relay_GPIO, True)
            GPIO.output(watering_enabled_GPIO, False)  # Turn off green light
            GPIO.output(watering_disabed_GPIO, True)  # Turn on red light
            # Update config file
            config['ProgramModified']['watering_required'] = 'False'

        # Update config file with timestamp of last weather update and GPIO
        config['ProgramModified']['lastweatherupdate'] = str(time.time())
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)

        # Sleep program until next check interval
        time.sleep(86400 / weatherupdatesperday)


# print(watering_required())
runProgram()
