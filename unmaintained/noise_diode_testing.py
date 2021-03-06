#!/usr/bin/python
# Fire noise diode while at zenith and record the data.

import katpoint
import katuilib
from katuilib import CaptureSession
import uuid
import time

kat = katuilib.tbuild('cfg-local.ini', 'local_ff')

with CaptureSession(kat, str(uuid.uuid1()), 'ffuser', 'Noise diode testing', kat.ants) as session:
    session.standard_setup(centre_freq=1822, dump_rate=512.0 / 1000.0)

    kat.peds.req.rfe3_rfe15_noise_source_on("coupler", 1, "now", 1, 10240, 0.5)

    kat.ants.req.target(kat.sources["Zenith"].description)
    kat.ants.req.mode("POINT")
    kat.ants.wait("lock", True, 300)

    kat.dbe.req.capture_start()

    # let the capture run for approximately 1 hour
    time.sleep(60.0 * 60)
