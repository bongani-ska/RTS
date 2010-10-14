#!/usr/bin/python

# IMPORTANT: update TLE's before doing this!
#
# Scans through EUTELSAT W2M, with dwells on-target between each scan for 5s.
# Expects an az and el offset provided by the calling script, determined by first peaking
# up on the target. This can be done as follows:
#   kat.ant1.req.target(kat.sources["EUTELSAT W2M"])
#   t_az,t_el=kat.ant1.sensor.pos_actual_scan_azim.get_value(),kat.ant1.sensor.pos_actual_scan_elev.get_value()
#   az=0.0;el=0.0; kat.ant1.req.target_azel(t_az+az,t_el+el);
# Now iterate\ively increase az, el to maximize the magnitude
#   kat.dh.sd.plot_time_series('mag', products=[(1,2,'HH')], start_channel=377,stop_channel=378)

# The *with* keyword is standard in Python 2.6, but has to be explicitly imported in Python 2.5
from __future__ import with_statement

import optparse
import sys
import uuid
import time
import katuilib
import katpoint
import numpy as np

# Parse command-line options that allow the defaults to be overridden
parser = optparse.OptionParser(usage="%prog [options]",
                               description="Perform mini (Zorro) raster scans across the holography sources \
                                            Some options are **required**.")

# Generic options
parser.add_option('-i', '--ini_file', dest='ini_file', type="string", metavar='INI', help='Telescope configuration ' +
                  'file to use in conf directory (default reuses existing connection, or falls back to cfg-local.ini)')
parser.add_option('-s', '--selected_config', dest='selected_config', type="string", metavar='SELECTED',
                  help='Selected configuration to use (default reuses existing connection, or falls back to local_ff)')
parser.add_option('-u', '--experiment_id', dest='experiment_id', type="string",
                  help='Experiment ID used to link various parts of experiment together (UUID generated by default)')
parser.add_option('-o', '--observer', dest='observer', type="string",
                  help='Name of person doing the observation (**required**)')
parser.add_option('-d', '--description', dest='description', type="string", default="Point source scan",
                  help='Description of observation (default="%default")')
parser.add_option('-a', '--ants', dest='ants', type="string", metavar='ANTS',
                  help="Comma-separated list of antennas to include in scan (e.g. 'ant1,ant2')," +
                       " or 'all' for all antennas (**required** - safety reasons)")
parser.add_option('-w', '--discard_slews', dest='record_slews', action="store_false", default=True,
                  help='Do not record all the time, i.e. pause while antennas are slewing to the next target')
# Experiment-specific options
parser.add_option('-e', '--scan_in_elevation', dest='scan_in_elevation', action="store_true", default=False,
                  help="Scan in elevation rather than in azimuth, (default=%default)")
parser.add_option('-X', '--extent', dest='extent_deg', type="float", default=1.5,
                  help="Angular extent of the scan (same for X & Y), in degrees (default=%default)")
parser.add_option('-x', '--step', dest='step_deg', type="float", default=0.075,
                  help="Angular spacing of scans (in az or el, depnding on scan direction), in degrees (default=%default)")
(opts, args) = parser.parse_args()

# Various non-optional options...
if opts.ants is None:
    print 'Please specify the antennas to use via -a option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.observer is None:
    print 'Please specify the observer name via -o option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.experiment_id is None:
    # Generate unique string via RFC 4122 version 1
    opts.experiment_id = str(uuid.uuid1())

# Try to build the given KAT configuration (which might be None, in which case try to reuse latest active connection)
# This connects to all the proxies and devices and queries their commands and sensors
try:
    kat = katuilib.tbuild(opts.ini_file, opts.selected_config)
# Fall back to *local* configuration to prevent inadvertent use of the real hardware
except ValueError:
    kat = katuilib.tbuild('cfg-local.ini', 'local_ff')
print "\nUsing KAT connection with configuration: %s\n" % (kat.get_config(),)

# Source to scan across
tgt = kat.sources['EUTELSAT W2M']
try:
    kat.ant1.req.antenna_rotation(-27) # XDM-only, "shallow" optimal value
except:
    pass

# The real experiment: Create a data capturing session with the selected sub-array of antennas
with katuilib.CaptureSession(kat, opts.experiment_id, opts.observer, opts.description,
                             opts.ants, opts.record_slews) as session:
    kat.dbe.req.capture_setup()
    kat.dbe.req.capture_start()
    kat.dbe.req.k7w_new_scan('slew')
    kat.ant1.req.target(tgt.description)
    kat.ant1.req.mode("POINT")
    kat.ant1.wait("lock",1,300)
     # wait for lock on boresight target
    #t_az = kat.ant1.sensor.pos_actual_scan_azim.get_value()
    #t_el = kat.ant1.sensor.pos_actual_scan_elev.get_value()
    #if az is not None:
    #    print "Adding azimuth offset of:",az
    #    t_az += az
    #if el is not None:
    #    print "Adding elevation offset of:",el
    #    t_el += el
   # kat.ant1.req.target_azel(t_az,t_el)
    kat.ant1.req.target(tgt.description)
    kat.ant1.req.offset_fixed(az,el,'stereographic')
    kat.ant1.wait("lock",1,300)
    kat.dbe.req.k7w_new_scan('cal')
    time.sleep(5)
    kat.dbe.req.k7w_new_scan('slew')
    degrees=opts.extent_deg
    step=opts.step_deg
    nrsteps=degrees/(2.0*step)
    for x in np.arange(-nrsteps,nrsteps,1):
        offset = x * step
        print "Scan %i: (%.2f,%.2f,%.2f,%.2f)" % (x, -0.5*degrees, offset, 0.5*degrees,offset)
        if opts.scan_in_elevation:
            kat.ant1.req.scan_asym(offset, -0.5*degrees, offset, 0.5*degrees, 25*degrees, "stereographic")
        else:
            kat.ant1.req.scan_asym(-0.5*degrees, offset, 0.5*degrees, offset, 25*degrees, "stereographic")
        kat.ant1.wait("lock",1,300)
         # wait for lock at start of scan
        kat.dbe.req.k7w_new_scan('scan')
        kat.ant1.req.mode("SCAN")
        time.sleep(25*degrees)
        kat.ant1.wait('scan_status', 'after', 300)
         # wait for scan to finish
        sys.stdout.flush()
        print "Finished scan. Doing cal..."
        kat.ant1.req.mode("POINT")
        kat.dbe.req.k7w_new_scan('slew')
        #kat.ant1.req.target_azel(t_az,t_el)
        kat.ant1.req.target(tgt.description)
        kat.ant1.req.offset_fixed(az,el,'stereographic')
        kat.ant1.wait("lock",1,300)
        kat.dbe.req.k7w_new_scan('cal')
        time.sleep(5)
         # wait for 5seconds on cal
        kat.dbe.req.k7w_new_scan('slew')
        sys.stdout.flush()
print "Done..."

