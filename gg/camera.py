# Author: Robert Park <robru@gottengeography.ca>, (C) 2012
# Copyright: See COPYING file included with this distribution.

"""The Camera class handles per-camera configuration.

It uniquely identifies each camera model that the user owns and stores
settings such as what timezone to use and how wrong the camera's clock is.
A 'relocatable' GSettings schema is used to persist this data across application
launches.

Note that the Cameras tab will only display the cameras responsible for
creating the currently loaded photos. This means that it's entirely possible
for GSettings to store a camera definition that isn't displayed in the UI.
Rest assured that your camera's settings are simply gone but not forgotten,
and if you want to see the camera in the camera list, you should load a photo
taken by that camera.
"""


from gi.repository import GtkClutter
GtkClutter.init([])

from gi.repository import GObject, Gtk
from math import modf as split_float
from gettext import gettext as _
from time import tzset
from os import environ

from gg.common import staticmethod
from gg.widgets import Builder, Widgets
from gg.common import GSettings, Binding, memoize
from gg.territories import tz_regions, get_timezone


@memoize
class Camera(GObject.GObject):
    """Store per-camera configuration in GSettings.

    >>> from mock import Mock as Photo
    >>> cam = Camera('unknown_camera')
    >>> cam.add_photo(Photo())
    >>> cam.num_photos
    1
    >>> photo = Photo()
    >>> cam.add_photo(photo)
    >>> cam.num_photos
    2
    >>> cam.remove_photo(photo)
    >>> cam.num_photos
    1

    >>> Camera.generate_id({'Make': 'Nikon',
    ...                     'Model': 'Wonder Cam',
    ...                     'Serial': '12345'})
    ('12345_nikon_wonder_cam', 'Nikon Wonder Cam')
    >>> Camera.generate_id({})
    ('unknown_camera', 'Unknown Camera')

    >>> cam = Camera('canon_canon_powershot_a590_is')
    >>> cam.timezone_method = 'lookup'
    >>> environ['TZ']
    'America/Edmonton'
    >>> cam.timezone_method = 'offset'
    >>> environ['TZ'].startswith('UTC')
    True
    """
    offset = GObject.property(type=int, minimum=-3600, maximum=3600)
    utc_offset = GObject.property(type=str)
    found_timezone = GObject.property(type=str)
    timezone_method = GObject.property(type=str)
    timezone_region = GObject.property(type=str)
    timezone_city = GObject.property(type=str)

    @GObject.property(type=int)
    def num_photos(self):
        """Read-only count of the loaded photos taken by this camera."""
        return len(self.photos)

    @staticmethod
    def generate_id(info):
        """Identifies a camera by serial number, make, and model."""
        maker = info.get('Make', '').capitalize()
        model = info.get('Model', '')

        # Some makers put their name twice
        model = model if model.startswith(maker) else maker + ' ' + model

        camera_id = '_'.join(sorted(info.values())).lower().replace(' ', '_')

        return (camera_id.strip(' _') or 'unknown_camera',
                model.strip() or _('Unknown Camera'))

    @staticmethod
    def set_all_found_timezone(timezone):
        """"Set all cameras to the given timezone."""
        for camera in Camera.instances:
            camera.found_timezone = timezone

    @staticmethod
    def timezone_handler_all():
        """Update all of the photos from all of the cameras."""
        for camera in Camera.instances:
            camera.timezone_handler()

    def __init__(self, camera_id):
        GObject.GObject.__init__(self)
        self.id = camera_id
        self.photos = set()

        # Bind properties to settings
        self.gst = GSettings('camera', camera_id)
        for prop in self.gst.list_keys():
            self.gst.bind(prop, self)

        # Get notifications when properties are changed
        self.connect('notify::offset', self.offset_handler)
        self.connect('notify::timezone-method', self.timezone_handler)
        self.connect('notify::timezone-city', self.timezone_handler)
        self.connect('notify::utc-offset', self.timezone_handler)

    def timezone_handler(self, *ignore):
        """Set the timezone to the chosen zone and update all photos."""
        environ['TZ'] = ''
        if self.timezone_method == 'lookup':
            # Note that this will gracefully fallback on system timezone
            # if no timezone has actually been found yet.
            environ['TZ'] = self.found_timezone
        elif self.timezone_method == 'offset':
            minutes, hours = split_float(-float(self.utc_offset))
            environ['TZ'] = 'UTC{:+}:{:02}'.format(
                int(hours), int(abs(minutes) * 60))
        elif self.timezone_method == 'custom' and \
             self.timezone_region and self.timezone_city:
            environ['TZ'] = '/'.join(
                [self.timezone_region, self.timezone_city])

        tzset()
        self.offset_handler()

    def get_offset_from_clock_photo(self, btn, orig, tz):
        """Subtract the camera's clock from the photographed clock."""
        delta_s = Widgets.clock_photo_seconds.get_value_as_int() - orig.tm_sec
        delta_m = Widgets.clock_photo_minutes.get_value_as_int() - orig.tm_min
        delta_h = Widgets.clock_photo_hours.get_value_as_int() - orig.tm_hour
        delta_h += float(Widgets.clock_photo_tz.get_active_id())
        self.offset = delta_m * 60 + delta_s

        utc_offset = int(tz[1:3]) + int(tz[-2:]) / 60
        utc_offset *= -1 if tz.startswith('-') else 1
        self.utc_offset = str(utc_offset + delta_h)
        self.timezone_method = 'offset'

    def offset_handler(self, *ignore):
        """When the offset is changed, update the loaded photos."""
        for i, photo in enumerate(self.photos):
            if not i % 10:
                Widgets.redraw_interface()
            photo.calculate_timestamp(self.offset)

    def add_photo(self, photo):
        """Adds photo to the list of photos taken by this camera."""
        photo.camera = self
        self.photos.add(photo)
        self.notify('num_photos')

    def remove_photo(self, photo):
        """Removes photo from the list of photos taken by this camera."""
        photo.camera = None
        self.photos.discard(photo)
        self.notify('num_photos')


def display_offset(offset, value, add, subtract):
    """Display minutes and seconds in the offset GtkScale.

    >>> display_offset(None, 10, 'Add %d, %d', 'Subtract %d, %d')
    'Add 0, 10'
    >>> display_offset(None, 100, 'Add %d, %d', 'Subtract %d, %d')
    'Add 1, 40'
    >>> display_offset(None, -100, 'Add %d, %d', 'Subtract %d, %d')
    'Subtract 1, 40'
    """
    seconds, minutes = split_float(abs(value) / 60)
    return (subtract if value < 0 else add) % (minutes, int(seconds * 60))


@memoize
class CameraView(Gtk.Box):
    """A widget to show camera settings.

    >>> view = CameraView(Camera('unknown_camera'), 'Unknown Camera')
    >>> view.widgets.camera_label.get_text()
    'Unknown Camera'
    >>> view.widgets.timezone_method.set_active_id('system')
    True
    >>> view.widgets.utc_label.get_visible()
    False
    >>> view.camera.gst.get_string('timezone-method')
    'system'
    >>> view.widgets.timezone_method.set_active_id('offset')
    True
    >>> view.widgets.utc_label.get_visible()
    True
    >>> view.camera.gst.get_string('timezone-method')
    'offset'
    """

    def __init__(self, camera, name):
        Gtk.Box.__init__(self)
        self.camera = camera

        self.widgets = Builder('camera')
        self.add(self.widgets.camera_settings)

        self.widgets.camera_label.set_text(name)

        self.set_counter_text()

        # GtkScale allows the user to correct the camera's clock.
        scale = self.widgets.offset
        scale.connect('format-value', display_offset,
                      _('Add %dm, %ds to clock.'),
                      _('Subtract %dm, %ds from clock.'))

        # NOTE: This has to be so verbose because of
        # https://bugzilla.gnome.org/show_bug.cgi?id=675582
        # Also, it seems SYNC_CREATE doesn't really work.
        scale.set_value(camera.offset)
        Binding(scale.get_adjustment(), 'value', camera, 'offset',
            flags=GObject.BindingFlags.BIDIRECTIONAL)

        utc = self.widgets.utc_offset
        utc.set_active_id(camera.utc_offset)
        Binding(utc, 'active-id', camera, 'utc-offset',
            flags=GObject.BindingFlags.BIDIRECTIONAL)

        Binding(scale.get_adjustment(), 'value', camera, 'offset')

        # These two ComboBoxTexts are used for choosing the timezone manually.
        # They're hidden to reduce clutter when not needed.
        region_combo = self.widgets.timezone_region
        cities_combo = self.widgets.timezone_city
        for name in tz_regions:
            region_combo.append(name, name)

        for setting in ('region', 'city', 'method'):
            name = 'timezone_' + setting
            Binding(self.widgets[name], 'active-id',
                    camera, name.replace('_', '-'))

        region_combo.connect('changed', self.region_handler, cities_combo)
        region_combo.set_active_id(camera.timezone_region)
        cities_combo.set_active_id(camera.timezone_city)

        method_combo = self.widgets.timezone_method
        method_combo.connect('changed', self.method_handler)
        method_combo.set_active_id(camera.timezone_method)

        Widgets.timezone_cities_group.add_widget(utc)
        Widgets.timezone_cities_group.add_widget(cities_combo)
        Widgets.timezone_regions_group.add_widget(region_combo)
        Widgets.timezone_regions_group.add_widget(self.widgets.utc_label)
        Widgets.cameras_group.add_widget(self.widgets.camera_settings)

        camera.connect('notify::num-photos', self.set_counter_text)

        Widgets.cameras_view.add(self)
        self.show_all()

    def method_handler(self, method):
        """Only show manual tz selectors when necessary."""
        active_method = method.get_active_id()
        self.widgets.timezone_region.set_visible(active_method == 'custom')
        self.widgets.timezone_city.set_visible(active_method == 'custom')
        self.widgets.utc_label.set_visible(active_method == 'offset')
        self.widgets.utc_offset.set_visible(active_method == 'offset')

    def region_handler(self, region, cities):
        """Populate the list of cities when a continent is selected."""
        cities.remove_all()
        append = cities.append
        for city in get_timezone(region.get_active_id(), []):
            append(city.replace('_', ' '), city)

    def set_counter_text(self, *ignore):
        """Display to the user how many photos are loaded."""
        num = self.camera.num_photos
        self.widgets.count_label.set_text(
            {0:   _('No photos loaded.'),
             1:   _('One photo loaded.')}.get(
             num, _('%d photos loaded.') % num))
