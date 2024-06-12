from typing import *

import os
import plistlib
from pathlib import Path
from typing import Tuple, Iterable, Dict, Union


PathLike = Union[str, bytes, os.PathLike]


def load_plist_file(path: PathLike) -> Dict:
    with open(path, "rb") as fp:
        plist = plistlib.load(fp)
        return plist


class AppleMusicLibrary:
    @classmethod
    def load(cls, path: PathLike) -> "AppleMusicLibrary":
        """Extracts the user-defined playlists from the Apple plist.

        :param xml_plist: The parsed XML plist.
        :returns: An Iterable of (playlist_name, playlist_items) tuples.
        """

        plist = load_plist_file(path)

        tracks_node: Dict[str, Dict] = plist["Tracks"]
        tracks = {int(id): track_node for id, track_node in tracks_node.items()}

        playlists = {}
        playlists_node: Dict[Any, Dict] = plist["Playlists"]
        for playlist_node in playlists_node:
            if (
                "Master" not in playlist_node
                and "Distinguished Kind" not in playlist_node
            ):
                playlist_name: str = playlist_node["Name"]
                playlist_track_nodes: List[Dict] = playlist_node.get("Playlist Items", [])
                playlists[playlist_name] = [tracks[track_node["Track ID"]] for track_node in playlist_track_nodes]

        return cls(tracks, playlists)

    def __init__(
        self, tracks: Mapping[int, Mapping], playlists: Mapping[str, Sequence[Mapping]]
    ) -> None:
        self.tracks = tracks
        self.playlists = playlists
