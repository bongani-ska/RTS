#!/usr/bin/python
# Perform large raster scan on specified target(s). Mostly used for beam pattern mapping.

# The *with* keyword is standard in Python 2.6, but has to be explicitly imported in Python 2.5
from __future__ import with_statement

import optparse
import sys
import uuid

import katuilib

# Parse command-line options that allow the defaults to be overridden
parser = optparse.OptionParser(usage="%prog [options] <'target 1'> [<'target 2'> ...]",
                               description="Perform large raster scan across one or more sources. Mostly used for \
                                            beam pattern mapping and on-the-fly mapping. Some options are \
                                            **required**.")
# Generic options
parser.add_option('-i', '--ini_file', dest='ini_file', type="string", metavar='INI', help='Telescope configuration ' +
                  'file to use in conf directory (default reuses existing connection, or falls back to cfg-local.ini)')
parser.add_option('-s', '--selected_config', dest='selected_config', type="string", metavar='SELECTED',
                  help='Selected configuration to use (default reuses existing connection, or falls back to local_ff)')
parser.add_option('-u', '--experiment_id', dest='experiment_id', type="string",
                  help='Experiment ID used to link various parts of experiment together (UUID generated by default)')
parser.add_option('-o', '--observer', dest='observer', type="string",
                  help='Name of person doing the observation (**required**)')
parser.add_option('-d', '--description', dest='description', type="string", default="Raster scan",
                  help='Description of observation (default="%default")')
parser.add_option('-a', '--ants', dest='ants', type="string", metavar='ANTS',
                  help="Comma-separated list of antennas to include in scan (e.g. 'ant1,ant2')," +
                       " or 'all' for all antennas (**required** - safety reasons)")
parser.add_option('-f', '--centre_freq', dest='centre_freq', type="float", default=1822.0,
                  help='Centre frequency, in MHz (default="%default")')
parser.add_option('-w', '--discard_slews', dest='record_slews', action="store_false", default=True,
                  help='Do not record all the time, i.e. pause while antennas are slewing to the next target')
parser.add_option('-p', '--scan_spacing', dest='scan_spacing', type="float", default=0.125,
                  help='Separation between scans, in degrees (default="%default")')
parser.add_option('-x', '--scan_extent', dest='scan_extent', type="int", default=2,
                  help='Length of each scan, in degrees (default="%default")')

(opts, args) = parser.parse_args()

if len(args) == 0:
    print "Please specify at least one target argument (via name, e.g. 'Cygnus A' or description, e.g. 'azel, 20, 30')"
    sys.exit(1)
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

# Look up target names in catalogue, and keep target description strings as is
targets = []
for arg in args:
    # With no comma in the target string, assume it's the name of a target to be looked up in the standard catalogue
    if arg.find(',') < 0:
        target = kat.sources[arg]
        if target is None:
            print "Unknown source '%s', skipping it" % (arg,)
        else:
            targets.append(target)
    else:
        # Assume the argument is a target description string
        targets.append(arg)
if len(targets) == 0:
    print "No known targets found"
    sys.exit(1)

# Create a data capturing session with the selected sub-array of antennas
with katuilib.CaptureSession(kat, opts.experiment_id, opts.observer, opts.description,
                             opts.ants, opts.centre_freq, record_slews=opts.record_slews) as session:
    for target in targets:
        # Do raster scan on target, designed to have equal spacing in azimuth and elevation, for a "classic" look
        scan_extent = opts.scan_extent
        scan_spacing = opts.scan_spacing
        scan_duration = int(scan_extent/scan_spacing)
        num_scans = scan_duration + 1

        session.raster_scan(target, num_scans=num_scans, scan_duration=scan_duration,
                            scan_extent=scan_extent, scan_spacing=scan_spacing, drive_strategy='longest-track')
        # Fire noise diode, to allow gain calibration
        session.fire_noise_diode('coupler')
