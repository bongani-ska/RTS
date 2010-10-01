#!/usr/bin/python
# Produce various scans across a simulated DBE target producing scan data for signal displays and loading into scape (using CaptureSession).

from __future__ import with_statement

import katuilib

target = 'Takreem,azel,45,10'

with katuilib.tbuild('systems/local.conf') as kat:

    # Tell the DBE sim to make a test target at specfied az and el and with specified flux
    kat.dbe.req.dbe_test_target(45, 10, 100)
    nd_params = {'diode' : 'coupler', 'on_duration' : 3.0, 'off_duration' : 3.0, 'period' : 40.}

    with katuilib.CaptureSession(kat, 'id', 'nobody', 'The scan zoo', kat.ants,
                                 record_slews=True, nd_params=nd_params) as session:
        session.track(target, duration=5.0)
        session.fire_noise_diode('coupler', 5.0, 5.0)
        session.scan(target, duration=20.0)
        session.raster_scan(target, scan_duration=20.0)
