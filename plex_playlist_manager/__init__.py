import locale
from importlib import metadata

__version__ = metadata.version("plex-playlist-manager")

locale.setlocale(locale.LC_ALL, "")
