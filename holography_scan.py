#!/usr/bin/python
# Perform holography scan on specified target(s). Mostly used for beam pattern mapping using holography.

# The *with* keyword is standard in Python 2.6, but has to be explicitly imported in Python 2.5
from __future__ import with_statement

import katuilib
from katuilib import CaptureSession

import optparse
import sys
import uuid

# Parse command-line options that allow the defaults to be overridden
# Default KAT configuration is *local*, to prevent inadvertent use of the real hardware
parser = optparse.OptionParser(usage="%prog [options] <'target 1'> [<'target 2'> ...]\n\n"+
                                     "Perform holography scan across one or more sources. Some\n"+
                                     "options are **required.")
# Generic options
parser.add_option('-i', '--ini_file', dest='ini_file', type="string", default="cfg-local.ini", metavar='INI',
                  help='Telescope configuration file to use in conf directory (default="%default")')
parser.add_option('-s', '--selected_config', dest='selected_config', type="string", default="local_ff", metavar='SELECTED',
                  help='Selected configuration to use (default="%default")')
parser.add_option('-u', '--experiment_id', dest='experiment_id', type="string",
                  help='Experiment ID used to link various parts of experiment together (UUID generated by default)')
parser.add_option('-o', '--observer', dest='observer', type="string", help='Name of person doing the observation (**required)')
parser.add_option('-d', '--description', dest='description', type="string", default="Raster scan",
                  help='Description of observation (default="%default")')
parser.add_option('-a', '--ants', dest='ants', type="string", metavar='ANTS',
                  help="Comma-separated list of *all* antennas involved in observation (e.g. 'ant1,ant2')," +
                       " or 'all' for all antennas (**required - safety reasons)")
parser.add_option('-f', '--centre_freq', dest='centre_freq', type="float", default=1822.0,
                  help='Centre frequency, in MHz (default="%default")')
# Experiment-specific options
parser.add_option('-x', '--scan_ants', dest='scan_ants', type="string", metavar='SCAN_ANTS',
                  help="Comma-separated list of *subset* of antennas that will scan across the source (e.g. 'ant1')" +
                       " (**required - safety reasons)")
(opts, args) = parser.parse_args()

if len(args) == 0:
    print "Please specify at least one target argument (via name, e.g. 'Cygnus A' or description, e.g. 'azel, 20, 30')"
    sys.exit(1)
# Various non-optional options...
if opts.ants is None:
    print 'Please specify the full list of antennas to use via -a option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.scan_ants is None:
    print 'Please specify the list of scanning antennas to use via -x option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.observer is None:
    print 'Please specify the observer name via -o option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.experiment_id is None:
    # Generate unique string via RFC 4122 version 1
    opts.experiment_id = str(uuid.uuid1())

# Build KAT configuration, as specified in user-facing config file
# This connects to all the proxies and devices and queries their commands and sensors
kat = katuilib.tbuild(opts.ini_file, opts.selected_config)

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
with CaptureSession(kat, opts.experiment_id, opts.observer, opts.description, opts.ants, opts.centre_freq) as session:
    for target in targets:
        # Do raster scan on target, designed to have equal spacing in azimuth and elevation, for a "classic" look
        session.holography_scan(opts.scan_ants, target, num_scans=17, scan_duration=16, scan_extent=2, scan_spacing=0.125)
        # Fire noise diode, to allow gain calibration
        session.fire_noise_diode('coupler')

# WORKAROUND BEWARE
# Don't disconnect for IPython, but disconnect when run via standard Python
# Without this disconnect, the script currently hangs here when run from the command line
try:
    import IPython
    if IPython.ipapi.get() is None:
        kat.disconnect()
except ImportError:
    kat.disconnect()
