# The *with* keyword is standard in Python 2.6, but has to be explicitly imported in Python 2.5
from __future__ import with_statement

import ffuilib
from ffuilib import CaptureSession

import optparse
import sys
import uuid

# Parse command-line options that allow the defaults to be overridden
# Default FF configuration is *local*, to prevent inadvertent use of the real hardware
parser = optparse.OptionParser(usage="usage: %prog [options]")
# Generic options
parser.add_option('-i', '--ini_file', dest='ini_file', type="string", default="cfg-local.ini", metavar='INI',
                  help='Telescope configuration file to use in conf directory (default="%default")')
parser.add_option('-s', '--selected_config', dest='selected_config', type="string", default="local_ff", metavar='SELECTED',
                  help='Selected configuration to use (default="%default")')
parser.add_option('-u', '--experiment_id', dest='experiment_id', type="string",
                  help='Experiment ID used to link various parts of experiment together (randomly generated UUID by default)')
parser.add_option('-o', '--observer', dest='observer', type="string", help='Name of person doing the observation')
parser.add_option('-d', '--description', dest='description', type="string", default="Point source scan",
                  help='Description of observation (default="%default")')
parser.add_option('-a', '--ants', dest='ants', type="string", metavar='ANTS',
                  help="Comma-separated list of antennas to include in scan (e.g. 'ant1,ant2')," +
                       " or 'all' for all antennas - this MUST be specified (safety reasons)")
parser.add_option('-f', '--centre_freq', dest='centre_freq', type="float", default=1822.0,
                  help='Centre frequency, in MHz (default="%default")')
(opts, args) = parser.parse_args()

# Various non-optional options...
if opts.ants is None:
    print 'Please specify the antennas to use via -a option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.observer is None:
    print 'Please specify the observer name via -o option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.experiment_id is None:
    # Generate unique random string via RFC 4122 version 4
    opts.experiment_id = str(uuid.uuid4())

# Build Fringe Finder configuration, as specified in user-facing config file
# This connects to all the proxies and devices and queries their commands and sensors
ff = ffuilib.tbuild(opts.ini_file, opts.selected_config)

# Specify pointing calibrator catalogue (currently picks all radec sources from the standard list)
pointing_sources = ff.sources.filter(tags='radec')

# Create a data capturing session with the selected sub-array of antennas
with CaptureSession(ff, opts.experiment_id, opts.observer, opts.description, opts.ants, opts.centre_freq) as session:
    # Iterate through source list, picking the next one that is up
    for target in pointing_sources.iterfilter(el_limit_deg=5):
        # Do standard raster scan on target
        session.raster_scan(target)
        # Fire noise diode, to allow gain calibration
        session.fire_noise_diode('coupler')
