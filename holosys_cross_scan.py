#!/usr/bin/python
# Perform mini (Zorro) raster scans across the holography system's satellite of choice, EUTELSAT W2M.

# The *with* keyword is standard in Python 2.6, but has to be explicitly imported in Python 2.5
from __future__ import with_statement

import optparse
import sys
import uuid

import katuilib
import katpoint

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
parser.add_option('-m', '--min_time', dest='min_time', type="float", default=-1.0,
                  help="Minimum duration to run experiment, in seconds (default=one loop through sources)")
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
pointing_sources = [kat.sources['EUTELSAT W2M']]

start_time = katpoint.Timestamp()
targets_observed = []

# The real experiment: Create a data capturing session with the selected sub-array of antennas
with katuilib.BasicCaptureSession(kat, opts.experiment_id, opts.observer, opts.description,
                                  opts.ants, opts.record_slews) as session:
    # Keep going until the time is up
    keep_going = True
    while keep_going:
        # Iterate through source list, picking the next one that is up
        for target in pointing_sources:
            session.raster_scan(target, num_scans=7, scan_duration=10, scan_extent=0.5,
                                scan_spacing=0.1, scan_in_azimuth=not opts.scan_in_elevation)
            targets_observed.append(target.name)
            # The default is to do only one iteration through source list
            if opts.min_time <= 0.0:
                keep_going = False
            # If the time is up, stop immediately
            elif katpoint.Timestamp() - start_time >= opts.min_time:
                keep_going = False
                break

print "Targets observed : %d (%d unique)" % (len(targets_observed), len(set(targets_observed)))
