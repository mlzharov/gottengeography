"""Test the classes and functions defined by gg/xmlfiles.py"""

from mock import Mock, call
from os.path import join
from xml.parsers.expat import ExpatError

from tests import BaseTestCase


class XmlFilesTestCase(BaseTestCase):
    filename = 'xmlfiles'

    def setUp(self):
        """Initialize mocks."""
        super().setUp()
        self.mod.Gst = Mock()
        self.mod.GSettings = Mock()
        self.mod.MapView = Mock()
        self.normal_kml = join(self.data_dir, 'normal.kml')

    def test_gtkclutter_init(self):
        """Ensure GtkClutter.__init__() has been called."""
        self.mod.GtkClutter.init.assert_called_once_with([])

    def test_make_clutter_color(self):
        """Ensure we can create Clutter colors."""
        m = Mock(red=32767, green=65535, blue=32767)
        color = self.mod.make_clutter_color(m)
        self.assertEqual(color, self.mod.Clutter.Color.new.return_value)
        self.mod.Clutter.Color.new.assert_called_once_with(
            127.99609375, 255.99609375, 127.99609375, 192.0)

    def test_track_color_changed(self):
        """Ensure we can change GPX track colors."""
        s = Mock()
        p = [Mock(), Mock()]
        self.mod.make_clutter_color = Mock()
        self.mod.track_color_changed(s, p)
        s.get_color.assert_called_once_with()
        self.mod.Gst.set_color.assert_called_once_with(
            s.get_color.return_value)
        self.mod.make_clutter_color.assert_called_once_with(
            s.get_color.return_value)
        c = self.mod.make_clutter_color.return_value
        c.lighten.return_value.lighten.assert_called_once_with()
        p[0].set_stroke_color.assert_called_once_with(c)
        p[1].set_stroke_color.assert_called_once_with(c.lighten().lighten())

    def test_polygon_init(self):
        """Ensure we can create Polygons."""
        p = self.mod.Polygon()
        p.set_stroke_width.assert_called_once_with(4)
        self.mod.MapView.add_layer.assert_called_once_with(p)

    def test_polygon_append_point(self):
        """Ensure we can append points to Polygons."""
        p = self.mod.Polygon()
        coord = p.append_point(1, 2, 3)
        self.mod.Champlain.Coordinate.new_full.assert_called_once_with(1, 2)
        self.assertEqual(coord.lat, 1)
        self.assertEqual(coord.lon, 2)
        self.assertEqual(coord.ele, 3.0)
        p.add_node.assert_called_once_with(coord)

    def test_polygon_append_point_invalid_elevation(self):
        """Ensure we can append invalid elevation values."""
        p = self.mod.Polygon()
        coord = p.append_point(1, 2, 'five')
        self.mod.Champlain.Coordinate.new_full.assert_called_once_with(1, 2)
        self.assertEqual(coord.lat, 1)
        self.assertEqual(coord.lon, 2)
        self.assertEqual(coord.ele, 0.0)
        p.add_node.assert_called_once_with(coord)

    def test_xmlsimpleparser_init(self):
        """Ensure we can initialize the simple XML parser."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, 3, 4, 5)
        self.assertEqual(x.call_start, 4)
        self.assertEqual(x.call_end, 5)
        self.assertEqual(x.watchlist, 3)
        self.assertEqual(x.rootname, 2)
        self.assertIsNone(x.tracking)
        self.assertIsNone(x.element)
        self.mod.ParserCreate.assert_called_once_with()
        self.assertEqual(
            x.parser.ParseFile.mock_calls[0][1][0].name, self.normal_kml)
        self.assertEqual(x.parser.StartElementHandler, x.element_root)

    def test_xmlsimpleparser_init_failed(self):
        """Ensure the simple XML parser fails correctly."""
        self.mod.ParserCreate = Mock()
        self.mod.ParserCreate.return_value.ParseFile.side_effect = ExpatError()
        with self.assertRaises(OSError):
            self.mod.XMLSimpleParser(self.normal_kml, 2, 3, 4, 5)

    def test_xmlsimpleparser_element_root(self):
        """Ensure the simple XML parser finds the correct root element."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, 3, 4, 5)
        self.assertEqual(x.parser.StartElementHandler, x.element_root)
        x.element_root(2, 'five')
        self.assertEqual(x.parser.StartElementHandler, x.element_start)

    def test_xmlsimpleparser_element_root_failed(self):
        """Ensure the XML parser fails to find the root element correctly."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, 3, 4, 5)
        self.assertEqual(x.parser.StartElementHandler, x.element_root)
        with self.assertRaises(OSError):
            x.element_root(3, 'five')
        self.assertEqual(x.parser.StartElementHandler, x.element_root)

    def test_xmlsimpleparser_element_start_ignored(self):
        """Ensure the XML parser ignores the right starting elements."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, [], 4, 5)
        x.call_start = Mock()
        x.element_start('foo', 'bar')
        self.assertEqual(x.call_start.mock_calls, [])
        self.assertIsNone(x.element)

    def test_xmlsimpleparser_element_start_watching(self):
        """Ensure the XML parser starts watching."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, ['foo'], 4, 5)
        x.call_start = Mock()
        x.element_start('foo', dict(bar='grill'))
        x.call_start.assert_called_once_with('foo', dict(bar='grill'))
        self.assertEqual(x.tracking, 'foo')
        self.assertEqual(x.element, 'foo')
        self.assertEqual(x.parser.CharacterDataHandler, x.element_data)
        self.assertEqual(x.parser.EndElementHandler, x.element_end)
        self.assertEqual(x.state, dict(bar='grill'))

    def test_xmlsimpleparser_element_data_empty(self):
        """Ensure the XML parser handles empty data."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, ['foo'], 4, 5)
        self.assertEqual(x.state, {})
        x.element_data('        ')
        self.assertEqual(x.state, {})

    def test_xmlsimpleparser_element_data_something(self):
        """Ensure the XML parser handles data."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, ['foo'], 4, 5)
        x.element = 'neon'
        self.assertEqual(x.state, {})
        x.element_data('atomic number: 10')
        self.assertEqual(x.state, dict(neon='atomic number: 10'))

    def test_xmlsimpleparser_element_data_chunked(self):
        """Ensure the XML parser handles chunked data."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, ['foo'], 4, 5)
        x.element = 'neon'
        self.assertEqual(x.state, {})
        x.element_data('atomic ')
        x.element_data('number: 10')
        self.assertEqual(x.state, dict(neon='atomic number: 10'))

    def test_xmlsimpleparser_element_end(self):
        """Ensure the XML parser closes tags correctly."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, ['foo'], 4, 5)
        x.call_end = Mock()
        x.tracking = 'neon'
        x.state = dict(neon='atomic number: 10')
        x.element_end('neon')
        x.call_end.assert_called_once_with('neon', x.state)
        self.assertIsNone(x.tracking)
        self.assertEqual(x.state, dict())
        self.assertIsNone(x.parser.CharacterDataHandler)
        self.assertIsNone(x.parser.EndElementHandler)

    def test_xmlsimpleparser_element_end_ignored(self):
        """Ensure the XML parser ignores the right end tags."""
        self.mod.ParserCreate = Mock()
        x = self.mod.XMLSimpleParser(self.normal_kml, 2, ['foo'], 4, 5)
        x.call_end = Mock()
        x.tracking = 'neon'
        x.element_end('lithium')
        self.assertEqual(x.call_end.mock_calls, [])
        self.assertEqual(x.tracking, 'neon')

    def test_trackfile_update_range(self):
        """Ensure the TrackFile can update its range."""
        self.mod.TrackFile.range = [9, 10]
        self.mod.TrackFile.instances = ['something']
        self.mod.points = [1, 2, 3]
        self.mod.TrackFile.update_range()
        self.mod.Widgets.empty_trackfile_list.hide.assert_called_once_with()
        self.assertEqual(self.mod.TrackFile.range, [1, 3])

    def test_trackfile_update_range_empty(self):
        """Ensure the TrackFile can update an empty range."""
        self.mod.TrackFile.range = [9, 10]
        self.mod.points = [1, 2, 3]
        self.mod.TrackFile.update_range()
        self.mod.Widgets.empty_trackfile_list.show.assert_called_once_with()
        self.assertEqual(self.mod.TrackFile.range, [])

    def test_trackfile_get_bounding_box(self):
        """Ensure the TrackFile can get its bounding box."""
        class tf:
            polygons = [Mock(), Mock()]
        self.mod.TrackFile.instances = [tf]
        bounds = self.mod.TrackFile.get_bounding_box()
        self.mod.Champlain.BoundingBox.new.assert_called_once_with()
        self.assertEqual(bounds.compose.mock_calls, [
            call(tf.polygons[0].get_bounding_box.return_value),
            call(tf.polygons[1].get_bounding_box.return_value),
        ])

    def test_trackfile_query_all_timezones(self):
        """Ensure the TrackFile can query all timezones."""
        class tf:
            class start:
                geotimezone = 'hello'
        self.mod.TrackFile.instances = [tf]
        self.assertEqual(self.mod.TrackFile.query_all_timezones(), 'hello')

    def test_trackfile_query_all_timezones_none(self):
        """Ensure the TrackFile can handle no timezones found."""
        class tf:
            class start:
                geotimezone = None
        self.mod.TrackFile.instances = []
        self.assertIsNone(self.mod.TrackFile.query_all_timezones())
        self.mod.TrackFile.instances = [tf]
        self.assertIsNone(self.mod.TrackFile.query_all_timezones())

    def test_trackfile_clear_all(self):
        """Ensure the TrackFile can clear all tracks."""
        self.mod.points = Mock()
        self.mod.TrackFile.instances = tf = [Mock()]
        self.mod.TrackFile.clear_all()
        tf[0].destroy.assert_called_once_with()
        self.mod.points.clear.assert_called_once_with()

    def test_trackfile_load_from_file(self):
        """Ensure the TrackFile can load a file."""
        times = [2, 1]
        self.mod.clock = lambda: times.pop()
        self.mod.Camera = Mock()
        self.mod.GPXFile = Mock()
        self.mod.GPXFile.return_value.tracks = [1, 2, 3]
        self.mod.Widgets = Mock()
        self.mod.TrackFile.get_bounding_box = Mock()
        self.mod.TrackFile.instances = Mock()
        self.mod.TrackFile.update_range = Mock()
        self.mod.TrackFile.load_from_file('foo.gpx')
        self.mod.GPXFile.assert_called_once_with('foo.gpx')
        self.mod.Widgets.status_message.assert_called_once_with(
            '3 points loaded in 1.00s.', True)
        self.mod.TrackFile.instances.add.assert_called_once_with(
            self.mod.GPXFile.return_value)
        self.mod.MapView.emit.assert_called_once_with('realize')
        self.mod.MapView.get_max_zoom_level.assert_called_once_with()
        self.mod.MapView.set_zoom_level.assert_called_once_with(
            self.mod.MapView.get_max_zoom_level.return_value)
        self.mod.MapView.ensure_visible.assert_called_once_with(
            self.mod.TrackFile.get_bounding_box.return_value, False)
        self.mod.TrackFile.update_range.assert_called_once_with()
        self.mod.Camera.set_all_found_timezone.assert_called_once_with(
            self.mod.GPXFile.return_value.start.geotimezone)

    def test_trackfile_load_from_file_keyerror(self):
        """Ensure the TrackFile raises OSError correctly."""
        with self.assertRaises(OSError):
            self.mod.TrackFile.load_from_file('foo.unsupported')

    def test_trackfile_load_from_file_no_tracks(self):
        """Ensure the TrackFile can load a file with no tracks."""
        self.mod.GPXFile = Mock()
        self.mod.GPXFile.return_value.tracks = [1]
        self.mod.TrackFile.update_range = Mock()
        self.mod.TrackFile.load_from_file('foo.gpx')
        self.assertEqual(self.mod.MapView.emit.mock_calls, [])
        self.assertEqual(self.mod.MapView.ensure_visible.mock_calls, [])
        self.assertEqual(self.mod.TrackFile.update_range.mock_calls, [])

    def test_trackfile_init_first_no_points(self):
        """Ensure the TrackFile can load a track with no points."""
        self.mod.GSettings.return_value.get_string.return_value = ''
        self.mod.TrackFile.parse = Mock()
        with self.assertRaisesRegexp(OSError, 'No points found'):
            self.mod.TrackFile('/path/to/foo.gpx', 'a', 'b')
        self.mod.GSettings.assert_called_once_with('trackfile', 'foo.gpx')
        self.mod.Gst.get_value.assert_called_once_with('track-color')
        self.mod.GSettings.return_value.set_value.assert_called_once_with(
            'track-color', self.mod.Gst.get_value.return_value)

    def test_trackfile_element_end(self):
        """Ensure the TrackFile can end tracks."""
        events = [False, True, True]
        self.mod.Gtk.events_pending = lambda: events.pop()
        self.mod.clock = Mock(return_value=5)
        self.mod.TrackFile.clock = 1
        self.mod.TrackFile.progress = Mock()
        self.mod.TrackFile.__init__ = lambda s: None
        tf = self.mod.TrackFile()
        tf.element_end('foo', 'bar')
        self.assertEqual(
            self.mod.Gtk.main_iteration.mock_calls,
            [call(), call()])
        self.assertEqual(tf.clock, 5)

    def test_trackfile_destroy(self):
        """Ensure the TrackFile can destroy itself."""
        other_tf = Mock()
        self.mod.points = Mock()
        self.mod.TrackFile.__init__ = lambda s: None
        self.mod.TrackFile.update_range = Mock()
        tf = self.mod.TrackFile()
        self.mod.TrackFile.instances = set([tf, other_tf])
        tf.widgets = Mock()
        tf.polygons = set(['poly'])
        tf.filename = 'foo.gpx'
        tf.cache = {'foo.gpx': 'contents'}
        tf.destroy()
        self.mod.points.clear.assert_called_once_with()
        self.mod.points.update.assert_called_once_with(other_tf.tracks)
        tf.widgets.trackfile_settings.destroy.assert_called_once_with()
        self.mod.TrackFile.update_range.assert_called_once_with()

    def test_gpxfile(self, filename='minimal.gpx'):
        """Ensure the GPXFile can parse GPX data."""
        self.mod.Champlain.Coordinate.new_full = Mock
        self.mod.Coordinates = Mock()
        gpx = join(self.data_dir, filename)
        g = self.mod.GPXFile(gpx)
        timestamps = sorted(g.tracks)
        self.assertEqual(len(timestamps), 3)
        self.assertEqual(timestamps[0], 1287259751)
        self.assertEqual(g.tracks[timestamps[0]].lat, 53.52263)
        self.assertEqual(g.tracks[timestamps[0]].lon, -113.448979)
        self.assertEqual(g.tracks[timestamps[0]].ele, 671.666)
        self.assertEqual(timestamps[1], 1287259753)
        self.assertEqual(g.tracks[timestamps[1]].lat, 53.522731)
        self.assertEqual(g.tracks[timestamps[1]].lon, -113.448985)
        self.assertEqual(g.tracks[timestamps[1]].ele, 671.092)
        self.assertEqual(timestamps[2], 1287259755)
        self.assertEqual(g.tracks[timestamps[2]].lat, 53.52283)
        self.assertEqual(g.tracks[timestamps[2]].lon, -113.448985)
        self.assertEqual(g.tracks[timestamps[2]].ele, 671.307)

    def test_gpxfile_unusual(self):
        """Ensure the GPXFile can understand an unusual GPX variant."""
        self.test_gpxfile('unusual.gpx')

    def test_gpxfile_invalid(self):
        """Ensure the GPXFile recovers gracefully from invalid data."""
        self.test_gpxfile('invalid.gpx')

    def test_tcxfile(self):
        """Ensure we can read TCX data."""
        self.mod.Champlain.Coordinate.new_full = Mock
        self.mod.Coordinates = Mock()
        tcx = join(self.data_dir, 'sample.tcx')
        t = self.mod.TCXFile(tcx)
        timestamps = sorted(t.tracks)
        self.assertEqual(len(timestamps), 9)
        middle = len(timestamps) // 2
        self.assertEqual(timestamps[0], 1235221063)
        self.assertEqual(t.tracks[timestamps[0]].lat, 52.148514)
        self.assertEqual(t.tracks[timestamps[0]].lon, 4.500887)
        self.assertEqual(t.tracks[timestamps[0]].ele, -91.731)
        self.assertEqual(timestamps[1], 1235221067)
        self.assertEqual(t.tracks[timestamps[1]].lat, 52.148326)
        self.assertEqual(t.tracks[timestamps[1]].lon, 4.500603)
        self.assertEqual(t.tracks[timestamps[1]].ele, -90.795)
        self.assertEqual(timestamps[middle], 1235229207)
        self.assertEqual(t.tracks[timestamps[middle]].lat, 52.148655)
        self.assertEqual(t.tracks[timestamps[middle]].lon, 4.504016)
        self.assertEqual(t.tracks[timestamps[middle]].ele, 2.33)
        self.assertEqual(timestamps[-2], 1235229241)
        self.assertEqual(t.tracks[timestamps[-2]].lat, 52.149542)
        self.assertEqual(t.tracks[timestamps[-2]].lon, 4.502316)
        self.assertEqual(t.tracks[timestamps[-2]].ele, 2.443)
        self.assertEqual(timestamps[-1], 1235229253)
        self.assertEqual(t.tracks[timestamps[-1]].lat, 52.149317)
        self.assertEqual(t.tracks[timestamps[-1]].lon, 4.50191)
        self.assertEqual(t.tracks[timestamps[-1]].ele, 2.803)

    def test_kmlfile(self, filename='normal.kml'):
        """Ensure we can read KML data."""
        self.mod.Champlain.Coordinate.new_full = Mock
        self.mod.Coordinates = Mock()
        kml = join(self.data_dir, filename)
        k = self.mod.KMLFile(kml)
        timestamps = sorted(k.tracks)
        self.assertEqual(len(timestamps), 84)
        middle = len(timestamps) // 2
        self.assertEqual(timestamps[0], 1336169331)
        self.assertEqual(k.tracks[timestamps[0]].lat, 39.6012887)
        self.assertEqual(k.tracks[timestamps[0]].lon, 3.2617136)
        self.assertEqual(k.tracks[timestamps[0]].ele, 185.0)
        self.assertEqual(timestamps[1], 1336170232)
        self.assertEqual(k.tracks[timestamps[1]].lat, 39.6012887)
        self.assertEqual(k.tracks[timestamps[1]].lon, 3.2617136)
        self.assertEqual(k.tracks[timestamps[1]].ele, 185.0)
        self.assertEqual(timestamps[middle], 1336207136)
        self.assertEqual(k.tracks[timestamps[middle]].lat, 39.6013261)
        self.assertEqual(k.tracks[timestamps[middle]].lon, 3.2617602)
        self.assertEqual(k.tracks[timestamps[middle]].ele, 178.0)
        self.assertEqual(timestamps[-2], 1336253537)
        self.assertEqual(k.tracks[timestamps[-2]].lat, 39.6012402)
        self.assertEqual(k.tracks[timestamps[-2]].lon, 3.2617779)
        self.assertEqual(k.tracks[timestamps[-2]].ele, 0.0)
        self.assertEqual(timestamps[-1], 1336254435)
        self.assertEqual(k.tracks[timestamps[-1]].lat, 39.6012402)
        self.assertEqual(k.tracks[timestamps[-1]].lon, 3.2617779)
        self.assertEqual(k.tracks[timestamps[-1]].ele, 0.0)

    def test_kmlfile_disordered(self):
        """Ensure we can read disordered KML data as per wonky spec."""
        self.test_kmlfile('disordered.kml')

    def test_kmlfile_invalid(self):
        """Ensure we can recover gracefully from invalid KML data."""
        self.test_kmlfile('invalid.kml')

    def test_csvfile_mytracks(self):
        """Ensure we can read CSV data."""
        self.mod.Champlain.Coordinate.new_full = Mock
        self.mod.Coordinates = Mock()
        csv = join(self.data_dir, 'mytracks.csv')
        c = self.mod.CSVFile(csv)
        timestamps = sorted(c.tracks)
        self.assertEqual(len(timestamps), 100)
        middle = len(timestamps) // 2
        self.assertEqual(timestamps[0], 1339795704)
        self.assertEqual(c.tracks[timestamps[0]].lat, 49.887554)
        self.assertEqual(c.tracks[timestamps[0]].lon, -97.131041)
        self.assertEqual(c.tracks[timestamps[0]].ele, 217.1999969482422)
        self.assertEqual(timestamps[1], 1339795705)
        self.assertEqual(c.tracks[timestamps[1]].lat, 49.887552)
        self.assertEqual(c.tracks[timestamps[1]].lon, -97.130966)
        self.assertEqual(c.tracks[timestamps[1]].ele, 220.6999969482422)
        self.assertEqual(timestamps[middle], 1339795840)
        self.assertEqual(c.tracks[timestamps[middle]].lat, 49.886054)
        self.assertEqual(c.tracks[timestamps[middle]].lon, -97.132061)
        self.assertEqual(c.tracks[timestamps[middle]].ele, 199.5)
        self.assertEqual(timestamps[-2], 1339795904)
        self.assertEqual(c.tracks[timestamps[-2]].lat, 49.885123)
        self.assertEqual(c.tracks[timestamps[-2]].lon, -97.136603)
        self.assertEqual(c.tracks[timestamps[-2]].ele, 195.60000610351562)
        self.assertEqual(timestamps[-1], 1339795905)
        self.assertEqual(c.tracks[timestamps[-1]].lat, 49.885108)
        self.assertEqual(c.tracks[timestamps[-1]].lon, -97.136677)
        self.assertEqual(c.tracks[timestamps[-1]].ele, 195.6999969482422)

    def test_csvfile_missing_alt(self):
        """Ensure we can read CSV data that has no altitude info."""
        self.mod.Champlain.Coordinate.new_full = Mock
        self.mod.Coordinates = Mock()
        csv = join(self.data_dir, 'missing_alt.csv')
        c = self.mod.CSVFile(csv)
        timestamps = sorted(c.tracks)
        self.assertEqual(len(timestamps), 10)
        middle = len(timestamps) // 2
        self.assertEqual(timestamps[0], 1339795704)
        self.assertEqual(c.tracks[timestamps[0]].lat, 49.887554)
        self.assertEqual(c.tracks[timestamps[0]].lon, -97.131041)
        self.assertEqual(c.tracks[timestamps[0]].ele, 0)
        self.assertEqual(timestamps[1], 1339795705)
        self.assertEqual(c.tracks[timestamps[1]].lat, 49.887552)
        self.assertEqual(c.tracks[timestamps[1]].lon, -97.130966)
        self.assertEqual(c.tracks[timestamps[1]].ele, 0)
        self.assertEqual(timestamps[middle], 1339795751)
        self.assertEqual(c.tracks[timestamps[middle]].lat, 49.887298)
        self.assertEqual(c.tracks[timestamps[middle]].lon, -97.130747)
        self.assertEqual(c.tracks[timestamps[middle]].ele, 0)
        self.assertEqual(timestamps[-2], 1339795756)
        self.assertEqual(c.tracks[timestamps[-2]].lat, 49.887204)
        self.assertEqual(c.tracks[timestamps[-2]].lon, -97.130554)
        self.assertEqual(c.tracks[timestamps[-2]].ele, 0)
        self.assertEqual(timestamps[-1], 1339795760)
        self.assertEqual(c.tracks[timestamps[-1]].lat, 49.887156)
        self.assertEqual(c.tracks[timestamps[-1]].lon, -97.13052)
        self.assertEqual(c.tracks[timestamps[-1]].ele, 0)

    def test_csvfile_minimal(self, filename='minimal.csv'):
        """Ensure we can read the simplest possible CSV."""
        self.mod.Champlain.Coordinate.new_full = Mock
        self.mod.Coordinates = Mock()
        csv = join(self.data_dir, filename)
        c = self.mod.CSVFile(csv)
        timestamps = sorted(c.tracks)
        self.assertEqual(len(timestamps), 3)
        self.assertEqual(timestamps[0], 1339792700)
        self.assertEqual(c.tracks[timestamps[0]].lat, 49.885583)
        self.assertEqual(c.tracks[timestamps[0]].lon, -97.151421)
        self.assertEqual(c.tracks[timestamps[0]].ele, 0)
        self.assertEqual(timestamps[1], 1339792701)
        self.assertEqual(c.tracks[timestamps[1]].lat, 49.885524)
        self.assertEqual(c.tracks[timestamps[1]].lon, -97.151472)
        self.assertEqual(c.tracks[timestamps[1]].ele, 0)
        self.assertEqual(timestamps[2], 1339792702)
        self.assertEqual(c.tracks[timestamps[2]].lat, 49.885576)
        self.assertEqual(c.tracks[timestamps[2]].lon, -97.151397)
        self.assertEqual(c.tracks[timestamps[2]].ele, 0)

    def test_csvfile_invalid(self):
        """Ensure we can gracefully recover from invalid CSV."""
        self.test_csvfile_minimal('invalid.csv')

    def test_csvfile_invalid2(self):
        """Ensure we can gracefully recover from more invalid CSV."""
        self.test_csvfile_minimal('invalid2.csv')
