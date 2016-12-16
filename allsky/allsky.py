from flask import Flask, render_template, request, url_for
from flask_paginate import Pagination
from glob import glob
from os import path
from datetime import datetime
from dateutil import parser as dateparser
import re
import forecastio

# generate the folder and name lists
ALLFOLDERS = glob('/media/bambam/HamCams/20*')
ALLFOLDERS.sort()
ALLNAMES = []
for f in ALLFOLDERS:
    date = dateparser.parse( path.split(f)[1] )
    ALLNAMES.append( date.strftime('%B %Y') )

app = Flask(__name__)
#############################
# pages
#############################
@app.route('/')
@app.route('/nights')
def nights():
    page = request.args.get('page', 1, type=int)
    month = getmonth(page-1,'allsky')
    pagination = Pagination(page=page, total=len(ALLFOLDERS), per_page=1,
        inner_window=5, outer_window=5, bs_version=3 )
    return render_template( 'allsky.html', month=month, pagination=pagination )

@app.route('/days')
def days():
    page = request.args.get('page', 1, type=int)
    month = getmonth(page-1,'hamcam1')
    pagination = Pagination(page=page, total=len(ALLFOLDERS), per_page=1,
        inner_window=5, outer_window=5, bs_version=3 )
    return render_template( 'hamcam.html', month=month, pagination=pagination )

@app.route('/video')
def video():
    vid = request.args.get('vid', 1, type=str)
    date = getday( vid )
    # include notes about image artifacts for some date ranges
    # if ('hamcam' in vid) and ((datetime(2015,10,7) <= date)&(datetime(2015,12,12) >= date)):
    #     note = '(This video may be somewhat distorted due to technical issues.)'
    if ('allsky' in vid) and ((datetime(2012,7,30) <= date)&(datetime(2012,8,16) >= date)):
        note = '(This video may be somewhat distorted due to technical issues.)'
    else:
        note = ''
    datestr = date.strftime('%A %B %-d, %Y')
    weatherstr = getweather( vid )
    return render_template( 'video.html', video=vid, note=note,
                            datestr=datestr, weatherstr=weatherstr )

@app.route('/about')
def about():
    return render_template( 'about.html', n=len(ALLFOLDERS) )

#############################
# helper functions
#############################
def getmonth(imonth=0, which='allsky'):
    """Return the rows for the requested month"""
    imonth = imonth%len(ALLFOLDERS) # if they've gone over, start looping
    name,rows = getrows(imonth, which)
    return render_template('month.html', rows=rows, name=name)

def getrows(imonth=0, which='allsky',):
    fs = glob(ALLFOLDERS[imonth]+'/%s*proc.mp4'%which)
    fs.sort()
    rows = []
    for i in range(0, len(fs), 2):
        try:
            rows.append( [fs[i].split('HamCams/')[1], fs[i+1].split('HamCams/')[1]] )
        except IndexError:
            rows.append( [fs[i].split('HamCams/')[1]] )
    name = ALLNAMES[imonth]
    return name, rows

def getday(vid):
    datestr = re.search('20\d{6}', vid).group()
    date = dateparser.parse( datestr )
    return date

summarymap = {'clear-day':'mostly clear',
              'clear-night':'mostly clear',
              'rain':'rainy',
              'snow':'snowy',
              'sleet':'rainy',
              'wind':'windy',
              'fog':'foggy',
              'cloudy':'cloudy',
              'partly-cloudy-day':'cloudy',
              'partly-cloudy-night':'cloudy'}
def moonmap( phase ):
    if (phase<0.05):
        return 'new moon'
    elif (phase>=0.05)&(phase<0.2):
        return 'waxing crescent moon'
    elif (phase>=0.2)&(phase<0.3):
        return 'crescent moon'
    elif (phase>=0.3)&(phase<0.45):
        return 'waxing gibbous moon'
    elif (phase>=0.45)&(phase<0.55):
        return 'full moon'
    elif (phase>=0.55)&(phase<0.7):
        return 'waning gibbous moon'
    elif (phase>=0.7)&(phase<0.8):
        return 'crescent moon'
    elif (phase>=0.8)&(phase<0.95):
        return 'waning crescent moon'
    elif (phase>=0.95):
        return 'new moon'
    else:
        return None

def getweather(vid):
    date = getday(vid)

    forecastioAPIKEY = '8502f1ca459c5a6de00c9995afa232c5'
    lat = 37.3418834
    lon = -121.6430017
    forecast = forecastio.load_forecast(forecastioAPIKEY, lat, lon, date)

    weathersummary = forecast.daily().data[0].icon

    weathersummary = summarymap.get( weathersummary )
    if weathersummary == None:
        weathersummary = 'variable'
    tlo = forecast.daily().data[0].temperatureMin
    thi = forecast.daily().data[0].temperatureMax
    moonsummary = moonmap( forecast.daily().data[0].moonPhase )
    if moonsummary == None:
        return 'uncertain moon'

    s = "The weather was %s, " %(weathersummary) +\
        r"with a daily high of %.0f&deg;F and an overnight low of %.0f&deg;F. " %(thi,tlo)

    if 'allsky' in vid:
        # only include moon information on overnight videos
        s += "There was a %s that night. " %(moonsummary)

    return s


#############################
# run it
#############################
if __name__ == '__main__':
    app.run(port=9000, debug=True)
