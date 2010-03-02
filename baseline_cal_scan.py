#!/usr/bin/python
# Track various point sources as specified in a catalogue for the purpose of baseline calibration.

# The *with* keyword is standard in Python 2.6, but has to be explicitly imported in Python 2.5
from __future__ import with_statement

import katpoint
import katuilib
from katuilib import CaptureSession

import uuid
from optparse import OptionParser
import sys

# Parse command-line options that allow the defaults to be overridden
# Default KAT configuration is *local*, to prevent inadvertent use of the real hardware
parser = OptionParser(usage="%prog [options] [<catalogue files>]\n\n" +
                            "Track various point sources from the specified catalogue file(s), or use the default catalogue\n" +
                            "if none is specified. This is useful for baseline (antenna location) calibration. Remember to\n" +
                            "specify the observer and antenna options, as these are **required.")
# Generic options
parser.add_option('-i', '--ini_file', dest='ini_file', type="string", default="cfg-local.ini", metavar='INI',
                  help='Telescope configuration file to use in conf directory (default="%default")')
parser.add_option('-s', '--selected_config', dest='selected_config', type="string", default="local_ff", metavar='SELECTED',
                  help='Selected configuration to use (default="%default")')
parser.add_option('-u', '--experiment_id', dest='experiment_id', type="string",
                  help='Experiment ID used to link various parts of experiment together (UUID generated by default)')
parser.add_option('-o', '--observer', dest='observer', type="string", help='Name of person doing the observation (**required)')
parser.add_option('-d', '--description', dest='description', type="string", default="Baseline calibration",
                  help='Description of observation (default="%default")')
parser.add_option('-a', '--ants', dest='ants', type="string", metavar='ANTS',
                  help="Comma-separated list of antennas to include in scan (e.g. 'ant1,ant2')," +
                       " or 'all' for all antennas (**required - safety reasons)")
parser.add_option('-f', '--centre_freq', dest='centre_freq', type="float", default=1822.0,
                  help='Centre frequency, in MHz (default="%default")')
# Experiment-specific options
parser.add_option('-p', '--print_only', dest='print_only', action="store_true", default=False,
                  help="Do not actually observe, but display which sources will be scanned, "+
                       "plus predicted end time (default=%default)")
parser.add_option('-m', '--min_time', dest='min_time', type="float", default=-1.0,
                  help="Minimum duration to run experiment, in seconds (default=one loop through sources)")

(opts, args) = parser.parse_args()

if opts.ants is None:
    print 'Please specify the antennas to use via -a option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.observer is None:
    print 'Please specify the observer name via -o option (yes, this is a non-optional option...)'
    sys.exit(1)
if opts.experiment_id is None:
    # Generate unique string via RFC 4122 version 1
    opts.experiment_id = str(uuid.uuid1())

kat = katuilib.tbuild(opts.ini_file, opts.selected_config)

# Create baseline calibrator catalogue
baseline_sources = katpoint.Catalogue(add_specials=False, antenna=kat.sources.antenna)
# Load catalogue files if given
if len(args) > 0:
    for catfile in args:
        baseline_sources.add(file(catfile))
else:
    # Prune the standard catalogue to only contain sources that are good for baseline calibration
    great_sources = ['3C123', 'Taurus A', 'Orion A', 'Hydra A', '3C273', 'Virgo A', 'Centaurus A', 'Pictoris A']
    good_sources =  ['3C48', '3C84', 'J0408-6545', 'J0522-3627', '3C161', 'J1819-6345', 'J1939-6342', '3C433', 'J2253+1608']
    baseline_sources.add([kat.sources[src] for src in great_sources + good_sources])

start_time = katpoint.Timestamp()
targets_observed = []

if opts.print_only:
    current_time = katpoint.Timestamp(start_time)
    # Find out where first antenna is currently pointing (assume all antennas point there)
    ants = katuilib.observe.ant_array(kat, opts.ants)
    az = ants.devs[0].sensor.pos_actual_scan_azim.get_value()
    el = ants.devs[0].sensor.pos_actual_scan_elev.get_value()
    prev_target = katpoint.construct_azel_target(az, el)
    # Keep going until the time is up
    keep_going, compscan = True, 0
    while keep_going:
        # Iterate through baseline sources that are up
        for target in baseline_sources.iterfilter(el_limit_deg=5, timestamp=current_time):
            print "At about %s, antennas will start slewing to '%s'" % (current_time.local(), target.name)
            # Assume 1 deg/s slew rate on average -> add time to slew from previous target to new one
            current_time += 1.0 * katpoint.rad2deg(target.separation(prev_target))
            print "At about %s, baseline track (compound scan %d) will start on '%s'" % \
                  (current_time.local(), compscan, target.name)
            # Do track of 120 seconds, and also allow one second of overhead per scan
            current_time += 120.0 + 1.0
            targets_observed.append(target.name)
            prev_target = target
            compscan += 1
            # The default is to do only one iteration through source list
            if opts.min_time <= 0.0:
                keep_going = False
            # If the time is up, stop immediately
            elif current_time - start_time >= opts.min_time:
                keep_going = False
                break
    print "Experiment to finish at about", current_time.local()
    print "Targets observed :", len(targets_observed), " (",len(set(targets_observed))," unique )"

else:
    # The real experiment: Create a data capturing session with the selected sub-array of antennas
    with CaptureSession(kat, opts.experiment_id, opts.observer, opts.description, opts.ants, opts.centre_freq) as session:
        # Keep going until the time is up
        keep_going = True
        while keep_going:
            # Iterate through baseline sources that are up
            for target in baseline_sources.iterfilter(el_limit_deg=5):
                session.track(target, duration=120.0, drive_strategy='longest-track')
                targets_observed.append(target.name)
                # The default is to do only one iteration through source list
                if opts.min_time <= 0.0:
                    keep_going = False
                # If the time is up, stop immediately
                elif katpoint.Timestamp() - start_time >= opts.min_time:
                    keep_going = False
                    break

        print "Targets observed :", len(targets_observed), " (",len(set(targets_observed))," unique )"

# WORKAROUND BEWARE
# Don't disconnect for IPython, but disconnect when run via standard Python
# Without this disconnect, the script currently hangs here when run from the command line
try:
    import IPython
    if IPython.ipapi.get() is None:
        kat.disconnect()
except ImportError:
    kat.disconnect()
