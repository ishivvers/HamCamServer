"""
Pull MH timelapse videos.

TO DO:
 Re-run, check for and iterate on errors, and improve.
 Reduce the number of failed videos.
"""

import datetime
import wget
import os
import re
import urllib2
import numpy as np
import matplotlib.pyplot as plt
from glob import glob
from subprocess import Popen,PIPE
from moviepy.editor import VideoFileClip, concatenate
from time import sleep

"""
To do:

 Fix cropping issue on videos between
   ((datetime(2015,10,7) <= date)&(datetime(2015,12,12) >= date))
"""

# a custom internal error class we can call in the code
class HamCamError(Exception):
    pass
    
def pull_day( day, outdir='/media/bambam/new/', rename=True, which='allsky', subfolder=True):
    """
    Attempts to download the relevant video.
    
    which can be one of:
     allsky
     hamcam1
     hamcam2
    """
    if subfolder:
        outdir += day.strftime('%Y-%m')+'/'
    if not os.path.exists( outdir ):
        os.makedirs( outdir )

    monthfolder = day.strftime('%Y-%m')
    dayfolder = day.strftime('%d')
    url = "https://mthamilton.ucolick.org/data/%s/%s/%s/public/"%(monthfolder, dayfolder, which)
    try:
        page = urllib2.urlopen( url ).read()
    except urllib2.HTTPError:
        raise HamCamError('No page made that day.')
    if which == 'allsky':
        prefix = 'SC_'
    elif which == 'hamcam1':
        prefix = 'HC1_'
    elif which == 'hamcam2':
        prefix = 'HC2_'
    try:
        filename = re.search(prefix+'\d+\.mpg', page).group()
    except AttributeError:
        raise HamCamError('No video from that day.')
    
    url = "https://mthamilton.ucolick.org/data/%s/%s/%s/public/%s"%(monthfolder, dayfolder, which, filename)
    res = wget.download( url, outdir+filename )
    # check to see if it worked
    stats = os.stat( res )
    if stats.st_size < 300:
        os.remove( res )
        return None
    if rename:
        outname = os.path.split( res )[0] + '/%s-%s.mpg'%(which, day.strftime('%Y%m%d'))
        os.system( 'mv %s %s'%(res, outname))
        return outname
    else:
        return res

def process_allsky( invid, outvid=None, plot=False ):
    """
    Trims file to be only between dusk and dawn.
    Crops to get rid of bottom border.
    Recenters (in time) so that it starts around midnight.
    """
    clip = VideoFileClip( invid )
    clip = clip.crop(y2=470)
    ihalf = (clip.end / 2.0)*clip.fps
    vals = np.array( [np.median(f) for f in clip.iter_frames()] )
    istart, iend = None,None
    nthresh = 15 # require nthresh or more frames at magic_v
    magic_vals = [62.0, 57.0, 255.0]
    # search for last grey frame after the beginning
    for i,v in enumerate(vals):
        if i < nthresh:
            continue
        if (i >= ihalf):
            break
        for V in magic_vals:
            if np.all( vals[max(i-nthresh,0):i] == V ):
                istart = i/clip.fps
                # print i,vals[max(i-nthresh,0):i]
    # search backwards for first grey frame before the end
    ivals = vals[::-1]
    for i,v in enumerate(ivals):
        if i < nthresh:
            continue
        if (i >= ihalf):
            break
        # print i,vals[max(i-nthresh,0):i]
        for V in magic_vals:
            if np.all( ivals[max(i-nthresh,0):i] == V ):
                iend = (len(ivals) - i)/clip.fps
                # print i,ivals[max(i-nthresh,0):i]
    if plot:
        plt.figure()
        t = np.linspace( clip.start, clip.end, len(vals) )
        plt.plot(t, vals)
        ylo,yhi = plt.ylim()
        plt.vlines( [istart, iend], ylo,yhi )
        plt.xlabel('time (s)')
        plt.ylabel('value')
        plt.show()
    
    if (istart != None) & (iend != None):
        # best choice; identified both start and end
        imid = istart + (iend - istart)/2.0
        trimmedStart = clip.subclip(istart, imid)
        trimmedEnd = clip.subclip(imid, iend)
        recentered = concatenate( [trimmedEnd, trimmedStart] )
    elif (istart != None) & (iend == None):
        # have a start, but no end; just go
        recentered = clip.subclip(t_start=istart)
    elif (istart == None) & (iend != None):
        # have an end, but no start
        recentered = clip.subclip(t_end=iend)
    else:
        raise HamCamError('Failed to identify start and end of night.')
    
    if outvid == None:
        # overwrite original
        #  DEPRECIATED
        tmpfile = '/tmp/temp.mp4'
        recentered.write_videofile(tmpfile)
        Popen('mv %s %s'%(tmpfile, invid), shell=True)
        print 'overwriting',invid
    else:
        # write to new file
        if (istart != None) & (iend != None):
            try:
                recentered.write_videofile(outvid)
            except IndexError:
                custom_write_hack( trimmedEnd, trimmedStart, outvid )
        else:
            recentered.write_videofile(outvid)
        print 'writing to',outvid
    return

def custom_write_hack( vidEnd, vidStart, outf, tmpdir='/media/bambam/tmp/'):
    """
    For some stupid reason MoviePy fails on some filewrites.
    This is a hackaround using ffmpeg and HandBrake directly.
    """
    print 'Hackily writing file directly using FFMPEG.'
    startDir = os.getcwd()
    os.chdir( tmpdir )
    # obnoxiously, it seems ffmpeg needs to be run from the 
    #  same location as the files.
    fEnd = 'end.mp4'
    fStart = 'start.mp4'
    fJoin = 'both.mp4'
    fHB = 'both.handbrake.mp4'
    fList = 'tmplist.txt'

    vidEnd.write_videofile( fEnd )
    vidStart.write_videofile( fStart )
    open(fList, 'w').write("file '%s'\nfile '%s'"%(fEnd,fStart))

    Popen('ffmpeg -f concat -i %s %s'%(fList, fJoin), shell=True).communicate()
    Popen( 'HandBrakeCLI -O --preset="Universal" -i %s -o %s'%(fJoin, fHB), shell=True).communicate()

    Popen('mv %s %s'%(fHB,outf), shell=True).communicate()
    Popen('rm *.mp4', shell=True).communicate()

    os.chdir(startDir)
    return outf

def process_hamcam( invid, outvid=None ):
    """
    Crops to get rid of text at top.
    Recenters (in time) so that it starts around noon.
    """
    clip = VideoFileClip( invid )
    clip = clip.crop(y1=30)
    thalf = clip.end / 2.0
    
    start = clip.subclip(0, thalf)
    end = clip.subclip(thalf, clip.end)
    recentered = concatenate( [end, start] )

    if outvid == None:
        # overwrite original
        tmpfile = '/tmp/temp.mp4'
        recentered.write_videofile(tmpfile)
        Popen('mv %s %s'%(tmpfile, invid), shell=True)
        print 'overwriting',invid
    else:
        # write to new file
        recentered.write_videofile(outvid)
        print 'writing to',outvid
    return

def pull_and_process_all( clean=False, pulllog='pullfailed.txt', proclog='procfailed.txt' ):
    start = datetime.datetime(2011, 8, 1)
    end = datetime.datetime(2016, 8, 1)
    day = start
    while day < end:
        print day
        try:
            res = pull_day( day, which='allsky' )
        except:
            open(pulllog,'a').write('allsky: %s\n'%str(day))
            res = None
        if res != None:
            outf = os.path.splitext(res)[0] + '.proc.mp4'
            try:
                process_allsky( res, outf )
            except:
                open(proclog,'a').write('%s\n'%res)
            if clean:
                os.system('rm %s'%res)

        try:
            res = pull_day( day, which='hamcam1' )
        except:
            open(pulllog,'a').write('hamcam1: %s\n'%str(day))
            res = None
        if res != None:
            outf = os.path.splitext(res)[0] + '.proc.mp4'
            try:
                process_hamcam( res, outf )
            except:
                open(proclog,'a').write('%s\n'%res)
            if clean:
                os.system('rm %s'%res)
        day += datetime.timedelta(1)

def relabel_failedprocs( inf='procfailed.txt'):
    """
    If files listed as 'failed' are full videos (more than 100kb in size)
     then simply rename them, and consider them successes.
    Note: it appears that hamcam1 videos labeled as 'procfailed'
     actually did NOT fail, but the allsky ones labeled that way did.
     Some allsky videos are empty containers (less than 100kb long) so I choose
     to let them go. The other videos tend to fail due to heavy rain, or technical
     issues. For now, I simply rename those files and leave them unprocessed
     video in the set.  Looks ok on the webpage, despite issues.
    """
    fs = open(inf,'r').readlines()
    for f in fs:
        f = f.strip()
        in_size = os.stat( f ).st_size
        outf = f.replace('.mpg','.proc.mp4')
        if os.path.exists( outf ):
            print 'Actually we got',os.path.basename(outf)
        elif in_size > 100000:
            print '%s seems big enough. Using it. (%d)'%(f,in_size)
            Popen( 'HandBrakeCLI -O --preset="Universal" -i %s -o %s'%(f, outf), shell=True).communicate()


################################
# run it
################################

if __name__ == '__main__':
    pull_and_process_all()