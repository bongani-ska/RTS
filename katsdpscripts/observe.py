"""Set of useful routines to do standard observations with KAT."""

import time
import logging

import numpy as np

from .array import Array
from .katcp_client import KATDevice

# Use default logger for now (but make sure logs are also displayed during interactive sessions)
logger = logging.getLogger("ffLogger")

# Ripped from katpoint.construct_target_params, to avoid extra dependencies
def preferred_name(description):
    fields = [s.strip() for s in description.split(',')]
    # Extract preferred name from name list (starred or first entry)
    names = [s.strip() for s in fields[0].split('|')]
    if len(names) == 0:
        return ''
    first_word = names[0].split(' ')[0]
    if first_word in ('azel', 'radec'):
        return first_word
    if first_word == 'xephem':
        edb_string = fields[-1].replace('~', ',')
        edb_name_field = edb_string.partition(',')[0]
        edb_names = [name.strip() for name in edb_name_field.split('|')]
        return edb_names[0]
    try:
        ind = [name.startswith('*') for name in names].index(True)
        return names[ind][1:]
    except ValueError:
        return names[0]

def ant_array(kat, ants, name='ants'):
    """Create sub-array of antennas from flexible specification.

    Parameters
    ----------
    kat : :class:`utility.KATHost` object
        KAT connection object
    ants : :class:`Array` or :class:`KATDevice` object, or list, or string
        Antennas specified by an Array object containing antenna devices, or
        a single antenna device or a list of antenna devices, or a string of
        comma-separated antenna names, or the string 'all' for all antennas
        controlled via the KAT connection associated with this session

    Returns
    -------
    array : :class:`Array` object
        Array object containing selected antenna devices

    Raises
    ------
    ValueError
        If antenna with a specified name is not found on KAT connection object

    """
    if isinstance(ants, Array):
        return ants
    elif isinstance(ants, KATDevice):
        return Array(name, [ants])
    elif isinstance(ants, basestring):
        if ants.strip() == 'all':
            return kat.ants
        else:
            try:
                return Array(name, [getattr(kat, ant.strip()) for ant in ants.split(',')])
            except AttributeError:
                raise ValueError("Antenna '%s' not found (i.e. no kat.%s exists)" % (ant, ant))
    else:
        # The default assumes that *ants* is a list of antenna devices
        return Array(name, ants)

class CaptureSession(object):
    """Context manager that encapsulates a single data capturing session.

    A data capturing *session* results in a single data file, potentially
    containing multiple scans and compound scans. An *experiment* may consist of
    multiple sessions. This object ensures that the capturing process is
    started and completed cleanly, even if exceptions occur during the session.
    It also provides canned routines for simple observations such as tracks,
    single scans, raster scans and holography scans on a specific source.

    The initialisation of the session object selects a sub-array of antennas,
    prepares the data capturing subsystem (DBE and k7writer) and sets the RFE7
    LO frequency.

    The antenna specification *ants* do not have a default, which forces the
    user to specify them explicitly. This is for safety reasons, to remind
    the user of which antennas will be moved around by the script. The
    *observer* and *description* similarly have no default, to force the
    user to document the observation to some extent.

    Parameters
    ----------
    kat : :class:`utility.KATHost` object
        KAT connection object associated with this experiment
    experiment_id : string
        Experiment ID, a unique string used to link the data files of an
        experiment together with blog entries, etc.
    observer : string
        Name of person doing the observation
    description : string
        Short description of the purpose of the capturing session
    ants : :class:`Array` or :class:`KATDevice` object, or list, or string
        Antennas that will participate in the capturing session, as an Array
        object containing antenna devices, or a single antenna device or a
        list of antenna devices, or a string of comma-separated antenna
        names, or the string 'all' for all antennas controlled via the
        KAT connection associated with this session
    centre_freq : float, optional
        RF centre frequency, in MHz
    dump_rate : float, optional
        Correlator dump rate, in Hz
    record_slews : {True, False}, optional
        If True, correlator data is recorded contiguously and the data file
        includes 'slew' scans which occur while the antennas slew to the start
        of the next proper scan. If False, the file output (but not the signal
        displays) is paused while the antennas slew, and the data file contains
        only proper scans.

    Raises
    ------
    ValueError
        If antenna with a specified name is not found on KAT connection object

    """
    def __init__(self, kat, experiment_id, observer, description, ants,
                 centre_freq=1800.0, dump_rate=1.0, record_slews=True):
        self.kat = kat
        self.ants = ants = ant_array(kat, ants)
        self.experiment_id = experiment_id
        self.record_slews = record_slews

        # Start with a clean state, by stopping the DBE
        kat.dbe.req.capture_stop()

        # Set centre frequency in RFE stage 7
        kat.rfe7.req.rfe7_lo1_frequency(4200.0 + centre_freq, 'MHz')
        effective_lo_freq = (centre_freq - 200.0) * 1e6

        # Set data output directory (typically on ff-dc machine)
        kat.dbe.req.k7w_output_directory("/var/kat/data")
        # Enable output to HDF5 file (takes effect on capture_start only), and set basic experimental info
        kat.dbe.req.k7w_write_hdf5(1)
        kat.dbe.req.k7w_experiment_info(experiment_id, observer, description)

        # The DBE proxy needs to know the dump period (in ms) as well as the effective LO freq,
        # which is used for fringe stopping (eventually). This sets the delay model and other
        # correlator parameters, such as the dump rate, and instructs the correlator to pass
        # its data to the k7writer daemon (set via configuration)
        kat.dbe.req.capture_setup(1000.0 / dump_rate, effective_lo_freq)

        logger.info("New data capturing session")
        logger.info("--------------------------")
        logger.info("Experiment ID = %s" % (experiment_id,))
        logger.info("Observer = %s" % (observer,))
        logger.info("Description ='%s'" % description)
        logger.info("RF centre frequency = %g MHz, dump rate = %g Hz, keep slews = %s" %
                    (centre_freq, dump_rate, record_slews))

        # If the DBE is simulated, it will have position update commands
        if hasattr(kat.dbe.req, 'dbe_pointing_az') and hasattr(kat.dbe.req, 'dbe_pointing_el'):
            first_ant = ants.devs[0]
            # Tell the DBE simulator where the first antenna is so that it can generate target flux at the right time
            # The minimum time between position updates is just a little less than the standard (az, el) sensor period
            first_ant.sensor.pos_actual_scan_azim.register_listener(kat.dbe.req.dbe_pointing_az, 0.4)
            first_ant.sensor.pos_actual_scan_elev.register_listener(kat.dbe.req.dbe_pointing_el, 0.4)
            logger.info("DBE simulator receives position updates from antenna '%s'" % (first_ant.name,))

    def __enter__(self):
        """Enter the data capturing session."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the data capturing session, closing the data file."""
        self.shutdown()
        # Do not suppress any exceptions that occurred in the body of with-statement
        return False

    def fire_noise_diode(self, diode='pin', on_duration=5.0, off_duration=5.0):
        """Switch noise diode on and off.

        This starts a new scan and switches the selected noise diode on and off
        for all the antennas doing the observation. The recorded scan is
        labelled as 'cal' in the HDF5 files. The target and compound scan are
        not changed. It therefore makes sense to fire the noise diode *after*
        a scan or track, when a target has already been loaded. The on and off
        durations can be specified.

        When the function returns, data will still be recorded to the HDF5 file.
        The specified *off_duration* is therefore a minimum value. Remember to
        run :meth:`shutdown` to close the file and finally stop the observation
        (automatically done when this object is used in a with-statement)!

        Parameters
        ----------
        diode : {'pin', 'coupler'}
            Noise diode source to use (pin diode is situated in feed horn and
            produces high-level signal, while coupler diode couples into
            electronics after the feed at a much lower level)
        on_duration : float, optional
            Minimum duration for which diode is switched on, in seconds
        off_duration : float, optional
            Minimum duration for which diode is switched off, in seconds

        """
        # Create reference to KAT object and antennas, as this allows easy copy-and-pasting from this function
        kat, ants = self.kat, self.ants
        # Find pedestal controllers with the same number as antennas (i.e. 'ant1' maps to 'ped1') and put into Array
        pedestals = Array('peds', [getattr(kat, 'ped' + ant.name[3:]) for ant in ants.devs])

        logger.info("Firing '%s' noise diode" % (diode,))
        # Create a new Scan group in HDF5 file, with 'cal' label
        kat.dbe.req.k7w_new_scan('cal')
        # Switch noise diode on on all antennas
        pedestals.req.rfe3_rfe15_noise_source_on(diode, 1, 'now', 0)
        # Unpause HDF5 file output
        kat.dbe.req.k7w_write_hdf5(1)
        # If we haven't yet, start recording data from the correlator (which creates the data file)
        if kat.dbe.sensor.capturing.get_value() == '0':
            kat.dbe.req.capture_start()
        time.sleep(on_duration)
        # Switch noise diode off on all antennas
        pedestals.req.rfe3_rfe15_noise_source_on(diode, 0, 'now', 0)
        time.sleep(off_duration)
        # If slews are not to be recorded, pause the file output again afterwards
        if not self.record_slews:
            kat.dbe.req.k7w_write_hdf5(0)

    def track(self, target, duration=20.0, drive_strategy='longest-track', label='track'):
        """Track a target.

        This tracks the specified target while recording data.

        In addition to the proper track on the source (labelled 'scan' in the
        dataset), data is also recorded while the antennas are moving to the start
        of the track. (This is due to the design of the data capturing system,
        which prefers to run continuously.) This segment is labelled 'slew' in
        the dataset and will typically be discarded during processing.

        Data capturing is started before the track starts, if it isn't running yet.
        A new compound scan will be created in the HDF5 data file, with a 'slew'
        and 'scan' scan. The antennas all track the same target in parallel.

        When the function returns, the antennas will still track the target and
        data will still be recorded to the HDF5 file. The specified *duration*
        is therefore a minimum value. Remember to run :meth:`shutdown` to close
        the file and finally stop the observation (automatically done when this
        object is used in a with-statement)!

        Parameters
        ----------
        target : :class:`katpoint.Target` object or string
            Target to track, as an object or description string
        duration : float, optional
            Minimum duration of track, in seconds
        drive_strategy : {'longest-track', 'shortest-slew'}
            Drive strategy employed by antennas, used to decide what to do when
            target is in azimuth overlap region of antenna. The default is to
            go to the wrap that will permit the longest possible track before
            the target sets.
        label : string, optional
            Label for compound scan, usually a single computer-parseable word

        """
        # Create reference to KAT object and antennas, as this allows easy copy-and-pasting from this function
        kat, ants = self.kat, self.ants
        # Turn target object into description string (or use string as is)
        target = getattr(target, 'description', target)

        # Set the drive strategy for how antenna moves between targets
        ants.req.drive_strategy(drive_strategy)
        # Set the antenna target (antennas will already move there if in mode 'POINT')
        ants.req.target(target)
        # Provide target to the DBE proxy, which will use it as delay-tracking center
        kat.dbe.req.target(target)
        # Create new CompoundScan group in HDF5 file, which automatically also creates the first Scan group
        kat.dbe.req.k7w_new_compound_scan(target, label, 'slew' if self.record_slews else 'scan')

        logger.info("Slewing to target '%s'" % (preferred_name(target),))
        # If we haven't yet, start recording data from the correlator if slews are recorded (which creates data file)
        if self.record_slews and (kat.dbe.sensor.capturing.get_value() == '0'):
            kat.dbe.req.capture_start()
        # Start moving each antenna to the target
        ants.req.mode('POINT')
        # Wait until they are all in position (with 5 minute timeout)
        ants.wait('lock', True, 300)

        logger.info("Tracking target '%s'" % (preferred_name(target),))
        if not self.record_slews:
            # Unpause HDF5 file output (or create data file and start recording)
            kat.dbe.req.k7w_write_hdf5(1)
            if kat.dbe.sensor.capturing.get_value() == '0':
                kat.dbe.req.capture_start()
        else:
            # Start a new Scan group in the HDF5 file, this time labelled as a proper 'scan'
            kat.dbe.req.k7w_new_scan('scan')
        # Do nothing else for the duration of the track
        time.sleep(duration)
        # If slews are not to be recorded, pause the file output again directly after track
        if not self.record_slews:
            kat.dbe.req.k7w_write_hdf5(0)

    def scan(self, target, duration=20.0, start=-2.0, end=2.0, scan_in_azimuth=True,
             drive_strategy='shortest-slew', label='scan'):
        """Scan across a target.

        This scans across a target, either in azimuth or elevation (depending on
        the *scan_in_azimuth* flag). The scan starts at an offset of *start*
        degrees from the target and ends at an offset of *end* degrees. These
        offsets are calculated in a projected coordinate system (see *Notes*
        below). The scan lasts for *duration* seconds.

        In addition to the proper scan across the source (labelled 'scan' in the
        dataset), data is also recorded while the antennas are moving to the
        start of the scan. (This is due to the design of the data capturing
        system, which prefers to run continuously.) This segment is labelled
        'slew' in the dataset and will typically be discarded during processing.

        Data capturing is started before the scan starts, if it isn't running yet.
        A new compound scan will be created in the HDF5 data file, with a 'slew'
        and 'scan' scan. The antennas all scan across the same target in parallel.

        When the function returns, the antennas will still track the end-point of
        the scan and data will still be recorded to the HDF5 file. The specified
        *duration* is therefore a minimum value. Remember to run :meth:`shutdown`
        to close the file and finally stop the observation (automatically done
        when this object is used in a with-statement)!

        Parameters
        ----------
        target : :class:`katpoint.Target` object or string
            Target to scan across, as an object or description string
        duration : float, optional
            Minimum duration of scan across target, in seconds
        start : float, optional
            Start offset of scan along scanning coordinate, in degrees
            (see *Notes* below)
        end : float, optional
            End offset of scan along scanning coordinate, in degrees
            (see *Notes* below)
        scan_in_azimuth : {True, False}
            True if azimuth changes during scan while elevation remains fixed;
            False if scanning in elevation and stepping in azimuth instead
        drive_strategy : {'shortest-slew', 'longest-track'}
            Drive strategy employed by antennas, used to decide what to do when
            target is in azimuth overlap region of antenna. The default is to
            go to the wrap that is nearest to the antenna's current position,
            thereby saving time.
        label : string, optional
            Label for compound scan, usually a single computer-parseable word

        Notes
        -----
        Take note that scanning is done in a projection on the celestial sphere,
        and the scan start and end are in the projected coordinates. The azimuth
        coordinate of a scan in azimuth will therefore change more than the
        *start* and *end* parameters suggest, especially at high elevations.
        This ensures that the same scan parameters will lead to the same
        qualitative scan for any position on the celestial sphere.

        """
        # Create reference to KAT object and antennas, as this allows easy copy-and-pasting from this function
        kat, ants = self.kat, self.ants
        # Turn target object into description string (or use string as is)
        target = getattr(target, 'description', target)

        # Set the drive strategy for how antenna moves between targets
        ants.req.drive_strategy(drive_strategy)
        # Set the antenna target
        ants.req.target(target)
        # Provide target to the DBE proxy, which will use it as delay-tracking center
        kat.dbe.req.target(target)
        # Create new CompoundScan group in HDF5 file, which automatically also creates the first Scan group
        kat.dbe.req.k7w_new_compound_scan(target, label, 'slew' if self.record_slews else 'scan')

        logger.info("Slewing to start of scan across target '%s'" % (preferred_name(target),))
        # If we haven't yet, start recording data from the correlator if slews are recorded (which creates data file)
        if self.record_slews and (kat.dbe.sensor.capturing.get_value() == '0'):
            kat.dbe.req.capture_start()
        # Move each antenna to the start position of the scan
        if scan_in_azimuth:
            ants.req.scan_asym(start, 0.0, end, 0.0, duration)
        else:
            ants.req.scan_asym(0.0, start, 0.0, end, duration)
        ants.req.mode('POINT')
        # Wait until they are all in position (with 5 minute timeout)
        ants.wait('lock', True, 300)

        logger.info("Starting scan across target '%s'" % (preferred_name(target),))
        if not self.record_slews:
            # Unpause HDF5 file output (or create data file and start recording)
            kat.dbe.req.k7w_write_hdf5(1)
            if kat.dbe.sensor.capturing.get_value() == '0':
                kat.dbe.req.capture_start()
        else:
            # Start a new Scan group in the HDF5 file, this time labelled as a proper 'scan'
            kat.dbe.req.k7w_new_scan('scan')
        # Start scanning the antennas
        ants.req.mode('SCAN')
        # Wait until they are all finished scanning (with 5 minute timeout)
        ants.wait('scan_status', 'after', 300)
        # If slews are not to be recorded, pause the file output again directly after scan
        if not self.record_slews:
            kat.dbe.req.k7w_write_hdf5(0)

    def raster_scan(self, target, num_scans=3, scan_duration=20.0,
                    scan_extent=4.0, scan_spacing=0.5, scan_in_azimuth=True,
                    drive_strategy='shortest-slew', label='raster'):
        """Perform raster scan on target.

        A *raster scan* is a series of scans across a target, scanning in either
        azimuth or elevation, while the other coordinate is changed in steps for
        each scan. Each scan is offset by the same amount on both sides of the
        target along the scanning coordinate (and therefore has the same extent),
        and the scans are arranged symmetrically around the target in the
        non-scanning (stepping) direction. If an odd number of scans are done,
        the middle scan will therefore pass directly over the target. The default
        is to scan in azimuth and step in elevation, leading to a series of
        horizontal scans. Each scan is scanned in the opposite direction to the
        previous scan to save time. Additionally, the first scan always starts
        at the top left of the target, regardless of scan direction.

        In addition to the proper scans across the source (labelled 'scan' in the
        dataset), data is also recorded while the antennas are moving to the
        start of the next scan. (This is due to the design of the data capturing
        system, which prefers to run continuously.) These segments are labelled
        'slew' and will typically be discarded during processing.

        Data capturing is started before the first scan, if it isn't running yet.
        All scans in the raster scan are grouped together in a single compound
        scan in the HDF5 data file, as they share the same target. The antennas
        all perform the same raster scan across the given target, in parallel.

        When the function returns, the antennas will still track the end-point of
        the last scan and data will still be recorded to the HDF5 file. The
        specified *scan_duration* is therefore a minimum value. Remember to run
        :meth:`shutdown` to close the files and finally stop the observation
        (automatically done when this object is used in a with-statement)!

        Parameters
        ----------
        target : :class:`katpoint.Target` object or string
            Target to scan across, as an object or description string
        num_scans : integer, optional
            Number of scans across target (an odd number is better, as this will
            scan directly over the source during the middle scan)
        scan_duration : float, optional
            Minimum duration of each scan across target, in seconds
        scan_extent : float, optional
            Extent (angular length) of scan along scanning coordinate, in degrees
            (see *Notes* below)
        scan_spacing : float, optional
            Separation between each consecutive scan along the coordinate that is
            not scanned but stepped, in degrees
        scan_in_azimuth : {True, False}
            True if azimuth changes during scan while elevation remains fixed;
            False if scanning in elevation and stepping in azimuth instead
        drive_strategy : {'shortest-slew', 'longest-track'}
            Drive strategy employed by antennas, used to decide what to do when
            target is in azimuth overlap region of antenna. The default is to
            go to the wrap that is nearest to the antenna's current position,
            thereby saving time.
        label : string, optional
            Label for compound scan, usually a single computer-parseable word

        Notes
        -----
        Take note that scanning is done in a projection on the celestial sphere,
        and the scan extent and spacing apply to the projected coordinates.
        The azimuth coordinate of a scan in azimuth will therefore change more
        than the *scan_extent* parameter suggests, especially at high elevations.
        This ensures that the same scan parameters will lead to the same
        qualitative scan for any position on the celestial sphere.

        """
        # Create reference to KAT object and antennas, as this allows easy copy-and-pasting from this function
        kat, ants = self.kat, self.ants
        # Turn target object into description string (or use string as is)
        target = getattr(target, 'description', target)

        # Set the drive strategy for how antenna moves between targets
        ants.req.drive_strategy(drive_strategy)
        # Set the antenna target
        ants.req.target(target)
        # Provide target to the DBE proxy, which will use it as delay-tracking center
        kat.dbe.req.target(target)
        # Create new CompoundScan group in HDF5 file, which automatically also creates the first Scan group
        kat.dbe.req.k7w_new_compound_scan(target, label, 'slew' if self.record_slews else 'scan')

        # Create start positions of each scan, based on scan parameters
        scan_steps = np.arange(-(num_scans // 2), num_scans // 2 + 1)
        scanning_coord = (scan_extent / 2.0) * (-1) ** scan_steps
        stepping_coord = scan_spacing * scan_steps
        # These minus signs ensure that the first scan always starts at the top left of target
        scan_starts = zip(scanning_coord, -stepping_coord) if scan_in_azimuth else zip(stepping_coord, -scanning_coord)

        # Iterate through the scans across the target
        for scan_count, scan in enumerate(scan_starts):

            logger.info("Slewing to start of scan %d of %d on target '%s'" %
                        (scan_count + 1, len(scan_starts), preferred_name(target)))
            if self.record_slews:
                # Create a new Scan group in HDF5 file, with 'slew' label (not necessary the first time)
                if scan_count > 0:
                    kat.dbe.req.k7w_new_scan('slew')
                # If we haven't yet, start recording data from the correlator (which creates the file)
                if kat.dbe.sensor.capturing.get_value() == '0':
                    kat.dbe.req.capture_start()
            # Move each antenna to the start position of the next scan
            if scan_in_azimuth:
                ants.req.scan_asym(scan[0], scan[1], -scan[0], scan[1], scan_duration)
            else:
                ants.req.scan_asym(scan[0], scan[1], scan[0], -scan[1], scan_duration)
            ants.req.mode('POINT')
            # Wait until they are all in position (with 5 minute timeout)
            ants.wait('lock', True, 300)

            logger.info("Starting scan %d of %d on target '%s'" %
                        (scan_count + 1, len(scan_starts), preferred_name(target)))
            if self.record_slews or (scan_count > 0):
                # Start a new Scan group in the HDF5 file, labelled as a proper 'scan'
                kat.dbe.req.k7w_new_scan('scan')
            # Unpause HDF5 file output (or create data file and start recording if not done yet)
            kat.dbe.req.k7w_write_hdf5(1)
            if not self.record_slews and (kat.dbe.sensor.capturing.get_value() == '0'):
                kat.dbe.req.capture_start()
            # Start scanning the antennas
            ants.req.mode('SCAN')
            # Wait until they are all finished scanning (with 5 minute timeout)
            ants.wait('scan_status', 'after', 300)
            # If slews are not to be recorded, pause the file output again directly after the scan
            if not self.record_slews:
                kat.dbe.req.k7w_write_hdf5(0)

    def holography_scan(self, scan_ants, target, num_scans=3, scan_duration=20.0,
                        scan_extent=4.0, scan_spacing=0.5, scan_in_azimuth=True,
                        drive_strategy='shortest-slew', label='holo'):
        """Perform holography scan on target.

        A *holography scan* is a mixture of a raster scan and a track, where
        a subset of the antennas (the *scan_ants*) perform a raster scan on the
        target, while another subset (the *track_ants*) track the target. The
        tracking antennas serve as reference antennas, and the correlation
        between the scanning and tracking antennas provide a complex beam
        pattern in a procedure known as *holography*. All antennas should be
        specified when the :meth:`setup` method is called.

        The scan parameters have the same meaning as for :meth:`raster_scan`.
        The tracking antennas track the target for the entire duration of the
        raster scan.

        Data capturing is started before the first scan, if it isn't running yet.
        All scans in the holography scan are grouped together in a single
        compound scan in the HDF5 data file, as they share the same target. As
        with :meth:`raster_scan`, the proper scans across the target are labelled
        'scan' in the dataset, and scans recorded while the antennas are moving
        to the start of the next scan are labelled 'slew'.

        When the function returns, the antennas will still track the end-point of
        the last scan (or the target itself) and data will still be recorded to
        the HDF5 file. The specified *scan_duration* is therefore a minimum
        value. Remember to run :meth:`shutdown` to close the files and finally
        stop the observation (automatically done when this object is used in a
        with-statement)!

        Parameters
        ----------
        scan_ants : :class:`Array` or :class:`KATDevice` object, or list or string
            Antennas that will scan across the target, as an Array object
            containing antenna devices, or a single antenna device or a list of
            antenna devices, or a string of comma-separated antenna names
        target : :class:`katpoint.Target` object or string
            Target to scan across or track, as an object or description string
        num_scans : integer, optional
            Number of scans across target (an odd number is better, as this will
            scan directly over the source during the middle scan)
        scan_duration : float, optional
            Minimum duration of each scan across target, in seconds
        scan_extent : float, optional
            Extent (angular length) of scan along scanning coordinate, in degrees
            (see *Notes* in :meth:`raster_scan`)
        scan_spacing : float, optional
            Separation between each consecutive scan along the coordinate that is
            not scanned but stepped, in degrees
        scan_in_azimuth : {True, False}
            True if azimuth changes during scan while elevation remains fixed;
            False if scanning in elevation and stepping in azimuth instead
        drive_strategy : {'shortest-slew', 'longest-track'}
            Drive strategy employed by antennas, used to decide what to do when
            target is in azimuth overlap region of antenna. The default is to
            go to the wrap that is nearest to the antenna's current position,
            thereby saving time.
        label : string, optional
            Label for compound scan, usually a single computer-parseable word

        Raises
        ------
        ValueError
            If scanning antenna is not found or if the set of scanning antennas
            is not a proper subset of all antennas given during setup

        """
        # Create reference to KAT object and antennas, as this allows easy copy-and-pasting from this function
        kat, all_ants = self.kat, self.ants
        scan_ants = ant_array(kat, scan_ants, 'scan_ants')
        # Verify that scan_ants is a proper subset of all_ants
        if not set(scan_ants.devs).issubset(set(all_ants.devs)):
            raise ValueError('Scanning antenna not found in full antenna list given during setup()')
        elif set(scan_ants.devs) == set(all_ants.devs):
            raise ValueError('All antennas cannot be scanning in a holography scan (some have to track...)')
        # Turn target object into description string (or use string as is)
        target = getattr(target, 'description', target)

        # Set the drive strategy for how antenna moves between targets
        all_ants.req.drive_strategy(drive_strategy)
        # Set the antenna target (both scanning and tracking antennas have the same target)
        all_ants.req.target(target)
        # Provide target to the DBE proxy, which will use it as delay-tracking center
        kat.dbe.req.target(target)
        # Create new CompoundScan group in HDF5 file, which automatically also creates the first Scan group
        kat.dbe.req.k7w_new_compound_scan(target, label, 'slew' if self.record_slews else 'scan')

        # Create start positions of each scan, based on scan parameters
        scan_steps = np.arange(-(num_scans // 2), num_scans // 2 + 1)
        scanning_coord = (scan_extent / 2.0) * (-1) ** scan_steps
        stepping_coord = scan_spacing * scan_steps
        # These minus signs ensure that the first scan always starts at the top left of target
        scan_starts = zip(scanning_coord, -stepping_coord) if scan_in_azimuth else zip(stepping_coord, -scanning_coord)

        # Iterate through the scans across the target
        for scan_count, scan in enumerate(scan_starts):

            logger.info("Slewing to start of scan %d of %d on target '%s'" %
                        (scan_count + 1, len(scan_starts), preferred_name(target)))
            if self.record_slews:
                # Create a new Scan group in HDF5 file, with 'slew' label (not necessary the first time)
                if scan_count > 0:
                    kat.dbe.req.k7w_new_scan('slew')
                # If we haven't yet, start recording data from the correlator (which creates the file)
                if kat.dbe.sensor.capturing.get_value() == '0':
                    kat.dbe.req.capture_start()
            # Set up scans for scanning antennas
            if scan_in_azimuth:
                scan_ants.req.scan_asym(scan[0], scan[1], -scan[0], scan[1], scan_duration)
            else:
                scan_ants.req.scan_asym(scan[0], scan[1], scan[0], -scan[1], scan_duration)
            # Send scanning antennas to start of next scan, and tracking antennas to target itself
            all_ants.req.mode('POINT')
            # Wait until they are all in position (with 5 minute timeout)
            all_ants.wait('lock', True, 300)

            logger.info("Starting scan %d of %d on target '%s'" %
                        (scan_count + 1, len(scan_starts), preferred_name(target)))
            if self.record_slews or (scan_count > 0):
                # Start a new Scan group in the HDF5 file, labelled as a proper 'scan'
                kat.dbe.req.k7w_new_scan('scan')
            # Unpause HDF5 file output (or create data file and start recording if not done yet)
            kat.dbe.req.k7w_write_hdf5(1)
            if not self.record_slews and (kat.dbe.sensor.capturing.get_value() == '0'):
                kat.dbe.req.capture_start()
            # Start scanning the scanning antennas (tracking antennas keep tracking in the background)
            scan_ants.req.mode('SCAN')
            # Wait until they are all finished scanning (with 5 minute timeout)
            scan_ants.wait('scan_status', 'after', 300)
            # If slews are not to be recorded, pause the file output again directly after the scan
            if not self.record_slews:
                kat.dbe.req.k7w_write_hdf5(0)

    def shutdown(self):
        """Stop data capturing to shut down the session and close the data file.

        This does not affect the antennas, which continue to perform their
        last action.

        """
        # Create reference to KAT object, as this allows easy copy-and-pasting from this function
        kat = self.kat
        # Obtain the names of the files currently being written to
        files = kat.dbe.req.k7w_get_current_files(tuple=True)[1][2]
        logger.info('Scans complete, data captured to %s' % ([f.replace('writing','unaugmented') for f in files],))

        # Stop the DBE data flow (this indirectly stops k7writer via a stop packet, which then closes the HDF5 file)
        kat.dbe.req.capture_stop()
        logger.info('Ended data capturing session with experiment ID %s' % (self.experiment_id,))