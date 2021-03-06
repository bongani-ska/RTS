#!/usr/bin/env python
# Retrieve sensor data as CSV files or as plots.

"""Retrieve sensor data from a central monitor archive."""

from katuilib.katcp_client import KATBaseSensor
from katuilib.data import AnimatableSensorPlot
import katcp
import calendar
import datetime
import optparse
import urllib2
import urlparse
import sys
import re
import os


HOWTO = \
"""By default data is written out to .csv files. One
of -l (list), -d (show dates) or -p (plot) may be given
to perform other tasks.

Sensor names are cached in sensor_names.csv to avoid
having to trawl the monitoring store each time for a list
of known sensors.

The start and end times may be formatted as either 'YYYY-MM-DD'
or 'YYYY-MM-DD HH:MM'.

Examples
--------

# Find out what sensors named anc.asc.air are in the store
$ ./retrieve_sensor_data.py -l 'anc.asc.air'

# Find out what dates sensor information is available over
$ ./retrieve_sensor_data.py -d 'anc.asc.air'

# Plot temperature and pressure over a given date range
$ ./retrieve_sensor_data.py -p --start 2010-01-01 --end 2010-02-01 \\
 anc.asc.air.pressure anc.asc.air.temperature

# Download same data to .csv files in current folder
$ ./retrieve_sensor_data.py --start 2010-01-01 --end 2010-02-01 \\
 anc.asc.air.pressure anc.asc.air.temperature
"""


# known central monitor URLS

CM_URLS = {
    'lab': 'http://ff-proxy.lab.kat.ac.za/central_monitoring/',
    'karoo_archive_cpt': 'http://ff-dc.lab.kat.ac.za/karoo_archive_cpt/central_monitoring/',
    'sim': 'http://ff-sim.lab.kat.ac.za/central_monitoring/',
    'karoo': 'http://ff-proxy.karoo.kat.ac.za/central_monitoring/',
}

CM_KEYS = list(sorted(CM_URLS.keys()))

CM_DEFAULT = 'karoo_archive_cpt'


# parser for command-line options and arguments

parser = optparse.OptionParser(usage="%prog [options] <sensor names or regexes>", description=__doc__)
parser.add_option('--cm', '--central-monitor', dest='cm_url', type="string", metavar='CENTRAL_MONITOR', default=CM_DEFAULT,
                  help="Which monitor store to use. May be one of the known stores (%s) or a full URL [%%default]." \
                  % ", ".join(CM_KEYS))
parser.add_option('-l', '--list-sensors', dest='list_sensors', action="store_true", metavar='LIST_SENSORS',
                  help="List information on sensors instead of downloading data or plotting graphs [%default]")
parser.add_option('-d', '--list-dates', dest='list_dates', action="store_true", metavar='LIST_DATES',
                  help="List which periods sensor information is available over [%default]")
parser.add_option('-p', '--plot', dest='plot_graph', action="store_true", metavar='PLOT_GRAPHS',
                  help="Plot a graph instead of downloading data as CSV files [%default].")
parser.add_option('--start', dest='start_time', type="string", metavar='START_TIME', default=None,
                  help="Start of sensor data retrieval range [%default].")
parser.add_option('--end', dest='end_time', type="string", metavar='END_TIME', default=None,
                  help="End of sensor data retrieval range [%default].")
parser.add_option('--cache', dest='sensor_cache', type="string", metavar='SENSOR_CACHE', default="./sensor_cache.csv",
                  help="File to cache sensor names in [%default].")
parser.add_option('--title', dest='title', type="string", metavar='PLOT_TITLE', default=None,
                  help="Title for graph; only useful when using -p [%default].")
parser.add_option('--legend-loc', dest='legend_loc', type="int", metavar='LEGEND_LOC', default=0,
                  help="Matplotlib legend loc parameter; used to position legend; only useful when using -p [%default].")
parser.add_option('--howto', dest='howto', action="store_true", metavar='HOWTO',
                  help="Print out a HOWTO and exit.")


class CentralStore(object):
    """Access to a central monitoring store.

    Parameters
    ----------
    cm_url : string
        Where to find the central monitoring store.
    cache : string
        File to use as sensor name cache.
    """

    def __init__(self, cm_url, cache):
        self.url = cm_url
        self.cache = cache
        if not self.url.endswith('/'):
            self.url += '/'
        self._sensor_names = self._load_cache()
        self._sensor_types = set(katcp.Sensor.SENSOR_TYPE_LOOKUP.keys())

    def _load_cache(self):
        """Load sensor names from cache."""
        if os.path.isfile(self.cache):
            sensor_names = [line.strip() for line in open(self.cache)]
            return sensor_names
        return None

    def _save_cache(self, sensor_names):
        """Save sensor names to cache."""
        self._sensor_names = sensor_names
        cache_file = open(self.cache, "wb")
        for name in self._sensor_names:
            cache_file.write(name)
            cache_file.write("\n")
        cache_file.close()

    def _list_folder(self, url, ending=''):
        """Return the sub-folders or files of a URL that have a given ending."""
        try:
            folder = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise RuntimeError("Could not read folder %r [%r]" % (url, e))
        try:
            subfolders = []
            for href in re.findall(r"href=\"([^\"]*)\"", folder.read()):
                href = href.strip()
                href = href.rstrip("/")
                if href.startswith('?') or href.endswith('.log') or not href:
                    # skip empty paths, Apaches sorting queries and log files (what are these
                    # doing in the karoo monitoring store?!)
                    continue
                abs_url = urlparse.urljoin(url, href)
                if not abs_url.startswith(url) or not href.endswith(ending):
                    continue
                subfolders.append(href)
        finally:
            folder.close()
        return subfolders

    def sensor_names(self):
        """Retrieve a list of sensor names."""
        if self._sensor_names is not None:
            return self._sensor_names

        # find proxies (folder) and sensor names (sub-folders)
        sensor_names = []
        for folder in self._list_folder(self.url):
            sensor_names.extend("%s.%s" % (folder, child) for child in self._list_folder("%s%s/" % (self.url, folder)))

        self._save_cache(sensor_names)
        return sensor_names

    def sensor(self, name):
        """Retrieve a KATBaseSensor for the given sensor name."""
        parent_name, sensor_name = name.split('.', 1)
        csv_files = self._list_folder("%s%s/%s/" % (self.url, parent_name, sensor_name), ending='.csv')
        csv_files = list(sorted(csv_files))
        if not csv_files:
            return
        latest = csv_files[0]
        header = urllib2.urlopen("%s%s/%s/%s" % (self.url, parent_name, sensor_name, latest)).readline()
        parts = [part.strip() for part in header.split(',')]
        types = [i for i, part in enumerate(parts) if part in self._sensor_types]
        if len(types) != 1:
            raise ValueError("Couldn't determine type of sensor %r from header %r" % (name, parts))
        type_index = types[0]
        description = ", ".join(parts[1:type_index])
        stype = parts[type_index]
        units = parts[type_index+1]
        return KATBaseSensor(parent_name, sensor_name, description, units, stype, central_monitor_url=self.url)


DEFAULT_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]

def parse_date(datestr, formats=None):
    """Parse a user date string into a datetime object."""
    date = None
    if formats is None:
        formats = DEFAULT_FORMATS
    for format in formats:
        try:
            date = datetime.datetime.strptime(datestr, format)
        except ValueError:
            pass
    if date is None:
        raise ValueError("Could not parse %r with any of %s" % (datestr, ", ".join(formats)))
    return date


def main():
    """Main script."""
    (opts, args) = parser.parse_args()

    if opts.howto:
        print HOWTO
        return 1

    if not args:
        print "No sensor expression given."
        parser.print_usage()
        return 1

    if opts.cm_url in CM_URLS:
        cm = CentralStore(CM_URLS[opts.cm_url], opts.sensor_cache)
    else:
        cm = CentralStore(opts.cm_url, opts.sensor_cache)

    print "Using central monitor %s" % (cm.url,)
    print "Using sensor cache %s" % (cm.cache,)

    if opts.start_time is None:
        start = None
        start_s = 0
    else:
        start = parse_date(opts.start_time)
        start_s = calendar.timegm(start.timetuple())
        print "Start of date range:", start.strftime(DEFAULT_FORMATS[0])

    if opts.end_time is None:
        end = None
        end_s = 0
    else:
        end = parse_date(opts.end_time)
        end_s = calendar.timegm(end.timetuple())
        print "End of date range:", end.strftime(DEFAULT_FORMATS[0])

    if opts.title is None:
        title = "Sensor data from %s" % (opts.cm_url)
    else:
        title = opts.title

    sensor_names = cm.sensor_names()
    matching_names = set()
    for regex in [re.compile(arg) for arg in args]:
        matching_names.update(name for name in sensor_names if regex.search(name))
    matching_names = list(sorted(matching_names))

    sensors = []
    for name in matching_names:
        sensor = cm.sensor(name)
        if sensor is None:
            print "Omitting sensor %s (no data found)." % (name,)
        sensors.append(sensor)

    if opts.list_sensors:
        print "Matching sensors"
        print "----------------"
        for sensor in sensors:
            print ", ".join(["%s.%s" % (sensor.parent_name, sensor.name), sensor.type, sensor.units, sensor.description])
        return

    if opts.list_dates:
        for sensor in sensors:
            fullname = "%s.%s" % (sensor.parent_name, sensor.name)
            history = sensor.list_stored_history(start_time=start_s, end_time=end_s, return_array=True)
            if history is None:
                history = []
            history = [(entry[0], entry[1]) for entry in history]
            history.sort()

            compacted = []
            current_start, current_end = 0, 0
            allowed_gap = 60*5
            for start, end in history:
                if start > current_end + allowed_gap:
                    if current_start:
                        compacted.append((current_start, current_end))
                    current_start, current_end = start, end
                else:
                    current_end = end
            if current_start:
                compacted.append((current_start, current_end))

            print
            print "Available data for", fullname
            print "-------------------" + "-"*len(fullname)
            if not compacted:
                print "No data in range."
            for start, end in compacted:
                start = datetime.datetime.fromtimestamp(start)
                end = datetime.datetime.fromtimestamp(end)
                format = DEFAULT_FORMATS[0]
                print start.strftime(format), " -> ",  end.strftime(format)
        return

    if opts.plot_graph:
        import matplotlib.pyplot as plt
        ap = AnimatableSensorPlot(title=title, source="stored", start_time=start_s, end_time=end_s, legend_loc=opts.legend_loc)
        for sensor in sensors:
            ap.add_sensor(sensor)
        ap.show()
        plt.show()
        return

    if True:
        for sensor in sensors:
            dump_file = "%s.%s.csv" % (sensor.parent_name, sensor.name)
            sensor.get_stored_history(start_time=start_s, end_time=end_s, dump_file=dump_file, select=False)
        return


if __name__ == "__main__":
    sys.exit(main())


