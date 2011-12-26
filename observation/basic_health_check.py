#!/usr/bin/python
# Check for basic system health (modified from defaults.py script).
# Intended for use of an observer.
# Code: Jasper (jasper at ska dot ac dot za)

## TODO:
# 1) Might be better to pull max and min values from the system config in some
# way rather than specify them again separately here. The ones used here may not
# be in sync with the value used for alarms etc.
# 2) Probably better to programmatically generate ant1, ant2, etc in future.

from optparse import OptionParser
import time
import sys

import katuilib
from katuilib.ansi import col

# Default settings logically grouped in lists
ant1 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped1.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped1.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped1.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped1.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped1.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped1.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant1.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant1.sensor.windstow_active.get_value()",0,0),
("kat.ant1.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant1.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

ant2 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped2.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped2.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped2.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped2.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped2.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped2.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant2.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant2.sensor.windstow_active.get_value()",0,0),
("kat.ant2.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant2.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

ant3 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped3.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped3.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped3.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped3.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped3.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped3.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant3.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant3.sensor.windstow_active.get_value()",0,0),
("kat.ant3.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant3.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

ant4 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped4.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped4.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped4.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped4.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped4.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped4.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant4.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant4.sensor.windstow_active.get_value()",0,0),
("kat.ant4.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant4.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

ant5 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped5.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped5.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped5.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped5.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped5.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped5.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant5.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant5.sensor.windstow_active.get_value()",0,0),
("kat.ant5.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant5.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

ant6 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped6.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped6.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped6.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped6.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped6.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped6.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant6.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant6.sensor.windstow_active.get_value()",0,0),
("kat.ant6.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant6.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

ant7 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.ped7.sensor.cryo_lna_temperature.get_value()", 70.0,76.0),
("kat.ped7.sensor.bms_chiller_flow_present.get_value()", 1,1),
("kat.ped7.sensor.rfe3_psu_on.get_value()", 1,1),
("kat.ped7.sensor.rfe3_rfe15_rfe1_lna_psu_on.get_value()", 1,1),
("kat.ped7.sensor.rfe3_rfe15_noise_pin_on.get_value()", 0,0),
("kat.ped7.sensor.rfe3_rfe15_noise_coupler_on.get_value()", 0,0),
("kat.ant7.sensor.mode.get_value()",["POINT","STOP","STOW","SCAN"],''), # command, list of string options, blank string
("kat.ant7.sensor.windstow_active.get_value()",0,0),
("kat.ant7.sensor.pos_actual_scan_azim.get_value()",-185.0,275.0),
("kat.ant7.sensor.pos_actual_scan_elev.get_value()",2.0,95.0),
("","",""), # creates a blank line
]

rfe7 = [ # structure is list of tuples with (command to access sensor value, min value, max value)
("kat.rfe7.sensor.rfe7_downconverter_ant1_h_powerswitch.get_value()", 1,1), # do we actually need these to be checked?
("kat.rfe7.sensor.rfe7_downconverter_ant1_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant2_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant2_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant3_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant3_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant4_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant4_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant5_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant5_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant6_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant6_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant7_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant7_v_powerswitch.get_value()", 1,1),
("kat.mon_kat_proxy.sensor.agg_rfe7_psu_states_ok.get_value()", 1,1),
("kat.mon_kat_proxy.sensor.agg_rfe7_orx1_states_ok.get_value()", 1,1),
("kat.mon_kat_proxy.sensor.agg_rfe7_orx2_states_ok.get_value()", 1,1),
("kat.mon_kat_proxy.sensor.agg_rfe7_orx3_states_ok.get_value()", 1,1),
("kat.mon_kat_proxy.sensor.agg_rfe7_osc_states_ok.get_value()", 1,1),
("","",""), # creates a blank line
]

dbe7 = [# structure is list of tuples with (command to access sensor value, min value, max value)
("kat.dbe7.sensor.dbe_mode.get_value()",['wbc','wbc8k'],''), # command, list of string options, blank string
("kat.dbe7.sensor.capturing.get_value()",['0','1'],''), # does this sensor work?? - showed 0 while capturing
("kat.dbe7.sensor.dbe_ant1h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant1v_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant2h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant2v_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant3h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant3v_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant4h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant4v_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant5h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant5v_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant6h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant6v_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant7h_adc_power.get_value()",-27.0,-25.0),
("kat.dbe7.sensor.dbe_ant7v_adc_power.get_value()",-27.0,-25.0),
("","",""), # creates a blank line
]

dc = [# structure is list of tuples with (command to access sensor value, min value, max value)
("kat.dbe7.sensor.k7w_capture_active.get_value()",['0','1'],'')
("kat.nm_kat_dc1.sensor.k7capture_running.get_value()",1,1),
("kat.nm_kat_dc1.sensor.k7aug_running.get_value()",1,1),
("kat.nm_kat_dc1.sensor.k7arch_running.get_value()",1,1),
("","",""), # creates a blank line
]

tfr = [# structure is list of tuples with (command to access sensor value, min value, max value)
("kat.mon_kat_proxy.sensor.agg_anc_tfr_time_synced.get_value()",1,1),
("kat.mon_kat_proxy.sensor.agg_anc_css_ntp_synch.get_value()",1,1), # does this include kat-dc1?
("kat.mon_kat_proxy.sensor.agg_anc_css_ut1_current.get_value()",1,1),
("kat.ant1.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.ant2.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.ant3.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.ant4.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.ant5.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.ant6.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.ant7.sensor.antenna_acu_ntp_time.get_value()",1,1),
("kat.dbe7.sensor.dbe_ntp_synchronised.get_value()",1,1),
("","",""), # creates a blank line
]

anc = [# structure is list of tuples with (command to access sensor value, min value, max value)
("kat.anc.sensor.asc_asc_air_temperature.get_value()", 0.0,32.0),
("kat.anc.sensor.asc_chiller_water_temperature.get_value()", 6.0,22.0),
("kat.anc.sensor.cc_cc_air_temperature.get_value()", 0.0,30.0),
("kat.anc.sensor.cc_chiller_water_temperature.get_value()", 6.0,18.0),
("kat.anc.sensor.asc_wind_speed.get_value()", 0.0,15.2),
("kat.anc.sensor.asc_fire_ok.get_value()", 1,1), # these sensors really should be something like "(not) on fire"
("kat.anc.sensor.cc_fire_ok.get_value()", 1,1),
("kat.anc.sensor.cmc_fire_ok.get_value()", 1,1),
("","",""), # creates a blank line
]

lab_rfe7 = [ # structure is list of tuples with (command to access sensor value, default value, tolerance)
("kat.rfe7.sensor.rfe7_downconverter_ant1_h_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_downconverter_ant1_v_powerswitch.get_value()", 1,1),
("kat.rfe7.sensor.rfe7_orx1_powerswitch.get_value()", 1,1),
("","",""), # creates a blank line
]

# Dictionary containing multiple sets of default settings, identified by name (user selects these by name at runtime)
defaults_set = {
'karoo' : ant1 + ant2 + ant3 + ant4 + ant5 + ant6 + ant7 + rfe7 + dbe7 + dc + tfr + anc,
'ant1' : ant1,
'ant2' : ant2,
'ant3' : ant3,
'ant4' : ant4,
'ant5' : ant5,
'ant6' : ant6,
'ant7' : ant7,
'ants' : ant1 + ant2 + ant3 + ant4 + ant5 + ant6 + ant7
'rfe7' : rfe7,
'dbe7' : dbe7,
'dc' : dc,
'tfr' : tfr,
'anc' : anc,
'lab_rfe7' : lab_rfe7,
'lab' : ant1 + lab_rfe7,
}

def check_sensors(kat, defaults, show_only_errors):
    # check current system setting and compare with defaults and tolerances as specified above
    print "%s %s %s %s" % ("Sensor".ljust(65), "Current Value".ljust(25),"Green Min".ljust(25), "Green Max".ljust(25))
    for checker, min_val, max_val in defaults:
        if checker.strip() == '':
            if not show_only_errors: print "" # print a blank line, but skip this if only showing errors
        else:
            try:
                current_val = str(eval(checker))
                if type(min_val) is list:
                    if current_val in min_val:
                        if not show_only_errors: print "%s %s %s %s" % (col("green") + checker.ljust(65), current_val.ljust(25), str(min_val).ljust(25), '' + col("normal"))
                    else:
                        print "%s %s %s %s" % (col("red") + checker.ljust(65), current_val.ljust(25), str(min_val).ljust(25), '' + col("normal"))
                else:
                    if (min_val <= float(current_val) and float(current_val) <=  max_val):
                        if not show_only_errors: print "%s %s %s %s" % (col("green") + checker.ljust(65), current_val.ljust(25), str(min_val).ljust(25), str(max_val).ljust(25) + col("normal"))
                    else:
                        print "%s %s %s %s" % (col("red") + checker.ljust(65), current_val.ljust(25), str(min_val).ljust(25), str(max_val).ljust(25) + col("normal"))
            except:
                print "Could not check", checker, "[expected range: %r , %r]" % (min_val,max_val)


if __name__ == "__main__":

    parser = OptionParser(usage="%prog [options]",
                          description="Perform basic health check of the system for observers.")
    parser.add_option('-s', '--system', help='System configuration file to use, relative to conf directory ' +
                      '(default reuses existing connection, or falls back to systems/local.conf)')
    parser.add_option('-d', '--defaults_set', default="karoo", metavar='DEFAULTS',
                      help='Selected defaults set to use, ' + '|'.join(defaults_set.keys()) + ' (default="%default")')
    parser.add_option('-e', '--errors_only', action='store_true', default=False,
                      help='Show only values in error, if this switch is included (default="%default")')

    (opts, args) = parser.parse_args()

    try:
        defaults = defaults_set[opts.defaults_set]
    except KeyError:
        print "Unknown defaults set '%s', expected one of %s" % (opts.defaults_set, defaults_set.keys())
        sys.exit()

    # Try to build the given KAT configuration (which might be None, in which case try to reuse latest active connection)
    # This connects to all the proxies and devices and queries their commands and sensors
    try:
        kat = katuilib.tbuild(opts.system)
    # Fall back to *local* configuration to prevent inadvertent use of the real hardware
    except ValueError:
        kat = katuilib.tbuild('systems/local.conf')
    print "Using KAT connection with configuration: %s" % (kat.config_file,)

    ants = katuilib.observe.ant_array(kat,'all')
    tgts = []
    locks = []

    try:
        print 'Current system centre frequency: %s MHz' % (kat.rfe7.sensor.rfe7_lo1_frequency.get_value() / 1e6 - 4200.)
        for ant in ants.devs:
            tgts.append(ant.sensor.target.get_value())
            locks.append(ant.sensor.lock.get_value())
        if len(set(tgts)) == 1 and len(set(locks)) == 1:
            print 'Current target (all antennas): ' + str(set(tgts).pop())
            print 'Antennas locked: ' + str(set(locks).pop())
        else:
            print 'Current targets :' + str(tgts)
            print 'Current lock states: ' + str(locks)
    except:
        print "Could not retrieve current centre frequency..."
        
    print "\nChecking current settings....."
    check_sensors(kat,defaults,opts.errors_only)

