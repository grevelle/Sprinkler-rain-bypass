import configparser
import json
import time

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


# Get weather from Darksky API
def getWeather():
    # Set historical times in a list
    weatherlookback = int(config['UserInput']['weatherlookback'])
    DaysOfData = weatherlookback
    today = int(time.time())
    historicaltimes = []
    for x in range(today - DaysOfData * 86400, today, 86400):
        historicaltimes.append(x)

    # Get location from Google Maps function and load in memory
    location = getLocation()

    # Set excluded content from weather API
    exclude = "?exclude=currently,minutely,hourly,alerts,flags"

    # Get darksky API key and last weather update
    darkskyKey = config['UserInput']['darkskykey']
    lastweatherupdate = config['ProgramModified']['lastweatherupdate']

    # Download today and future data, convert from JSON to Python
    url = "https://api.darksky.net/forecast/" + darkskyKey + "/" + str(location[0]) + "," + str(location[1]) + exclude
    s = requests.get(url)

    # Convert future from JSON to Python
    futuredict = json.loads(s.text)

    # Get historical data
    datelist1 = []
    for x in historicaltimes:
        url = "https://api.darksky.net/forecast/" + darkskyKey + "/" + str(location[0]) + "," + str(
            location[1]) + "," + str(x) + exclude
        s = requests.get(url)
        pastdict = json.loads(s.text)
        for x in pastdict['daily']['data']:
            datelist1.append([x['time'], x['precipIntensity']])

    # Create array to hold forecast values
    datelist2 = []

    # Parse XML into array with only pretty date, epoch, and conditions forecast
    for x in futuredict['daily']['data']:
        datelist2.append([x['time'], x['precipIntensity']])

    # Combine past and future precip lists, return [date, 24 hr rainfall] as precipamount
    preciplist = sorted(datelist1 + datelist2)
    precipamount = []
    for x in preciplist:
        precipamount.append([x[0], x[1] * 24])
    return (precipamount)


# total rainfall over 7 day forecast period
def watering_required():
    # return list of rainfall by day
    rainarray = getWeather()

    # Rain needed per rain period (inches)
    inchesrequired = float(config['UserInput']['inchesrequired'])

    # Number of days in rain period
    measurement_days = int(config['UserInput']['raindays'])
    rainfall = 0.0
    iteration = 0
    for x, y in rainarray:
        if (iteration <= measurement_days - 1):
            rainfall += y
            iteration += 1
        else:
            break
    if rainfall <= inchesrequired:
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
        weatherupdatesperday = float(config['UserInput']['weatherupdatesperday'])

        # Setup GPIO I/O Pins to output mode
        relay_GPIO = int(config['GPIO.Pins']['relayswitch'])
        watering_enabled_GPIO = int(config['GPIO.Pins']['wateringenabled'])
        watering_disabed_GPIO = int(config['GPIO.Pins']['wateringdisabled'])
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(relay_GPIO,
                   GPIO.OUT)  # This pin controls relay switch. When ON/True, watering is disabled. Default OFF
        GPIO.setup(watering_enabled_GPIO, GPIO.OUT)  # This pin enables green light when watering
        GPIO.setup(watering_disabed_GPIO, GPIO.OUT)  # This pin enables red light when watering disabled

        # Set GPIO I/O Pins
        if watering_required():
            GPIO.output(relay_GPIO, False)  # Turn off relay switch, enable watering
            GPIO.output(watering_enabled_GPIO, True)  # Turn on green light
            GPIO.output(watering_disabed_GPIO, False)  # Turn off red light
            config['ProgramModified']['watering_required'] = 'True'  # Update config file
        else:
            GPIO.output(relay_GPIO, True)  # Turn on relay switch, disable watering
            GPIO.output(watering_enabled_GPIO, False)  # Turn off green light
            GPIO.output(watering_disabed_GPIO, True)  # Turn on red light
            config['ProgramModified']['watering_required'] = 'False'  # Update config file

        # Update config file with timestamp of last weather update and GPIO
        config['ProgramModified']['lastweatherupdate'] = str(time.time())
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)

        # Sleep program until next check interval
        time.sleep(86400 / weatherupdatesperday)


# print(watering_required())
runProgram()
