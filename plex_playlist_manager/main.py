import unicodedata
import urllib.parse
from pathlib import Path
from typing import *

import click
import cloup
import typer_cloup as typer
from cloup.constraints import mutually_exclusive
from plexapi.audio import Album, Artist, Audio, Track
from plexapi.base import MediaContainer
from plexapi.exceptions import BadRequest
from plexapi.library import MusicSection
from plexapi.media import Media, MediaPart
from plexapi.myplex import MyPlexAccount, PlexServer
from plexapi.playlist import Playlist
from tqdm import tqdm
from typer_cloup import Abort, Exit, colors, constraint, echo, secho
from typer_cloup.core import TyperCommand, TyperGroup, TyperOption

from . import __version__
from .apple_music import AppleMusicLibrary
from .util import batched


PLEX_BATCH_SIZE = 100

app = typer.Typer(
    context_settings=typer.Context.settings(
        help_option_names=["--help", "-h"],
    ),
)

_plex_account: Optional[MyPlexAccount] = None
_plex_server: Optional[PlexServer] = None

_debug: bool = False
_plex_username: Optional[str] = None
_plex_password: Optional[str] = None
_plex_server_name: Optional[str] = None
_plex_library_name: Optional[str] = None


def print_version(ctx: typer.Context, param: TyperOption, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return  # pragma: no cover

    echo(f"Plex Playlist Manager v{__version__}")
    raise Exit()


def plex_account() -> MyPlexAccount:
    global _plex_account

    if _plex_account is None:
        _plex_account = MyPlexAccount(_plex_username, _plex_password)

    return _plex_account


def plex_server() -> PlexServer:
    global _plex_server

    if _plex_server is None:
        _plex_server = plex_account().resource(_plex_server_name).connect()

    return _plex_server


def sync_playlist(
    playlist_name: str,
    lib_playlist_tracks: Sequence[Mapping],
    plex_music_section: MusicSection,
    plex_tracks_by_path: Mapping[Path, Track],
    plex_playlist: Playlist,
) -> None:
    secho(
        f"Syncing library playlist '{playlist_name}' ({len(lib_playlist_tracks):n} tracks) to Plex..."
    )

    if plex_playlist is not None:
        plex_playlist.delete()
        secho(f"Removed existing Plex playlist '{plex_playlist.title}'")

    def get_path_from_url(url: AnyStr) -> Path:
        url_parts = urllib.parse.urlparse(urllib.parse.unquote(url))
        path = urllib.parse.unquote(url_parts.path)
        return Path(unicodedata.normalize("NFC", path)).resolve()

    def get_plex_track(lib_track: Mapping) -> Track:
        lib_track_location = lib_track["Location"]
        lib_track_path = get_path_from_url(lib_track_location)
        plex_track = plex_tracks_by_path.get(lib_track_path, None)

        if plex_track is None:
            secho(
                f"WARNING: Could not find Plex track for path `{lib_track_path}`",
                err=True,
                fg=colors.YELLOW,
            )

        return plex_track

    plex_playlist_items = [get_plex_track(track) for track in lib_playlist_tracks]
    plex_playlist_items = list(filter(None, plex_playlist_items))

    if plex_playlist_items:
        try:
            plex_playlist_items_batches = batched(plex_playlist_items, PLEX_BATCH_SIZE)

            plex_playlist_items_first_batch = next(plex_playlist_items_batches)
            plex_playlist = plex_music_section.createPlaylist(
                playlist_name, plex_playlist_items_first_batch
            )

            for plex_playlist_items_batch in plex_playlist_items_batches:
                plex_playlist.addItems(plex_playlist_items_batch)
        except BadRequest as err:
            secho(
                f"ERROR: Failed to create Plex playlist 'playlist_name': {err}",
                err=True,
                fg=colors.RED,
            )
        else:
            secho(
                f"Added Plex playlist '{plex_playlist.title}' ({len(plex_playlist_items):n} tracks)"
            )
    else:
        secho(
            f"WARNING: No Plex tracks found for playlist '{playlist_name}'",
            err=True,
            fg=colors.YELLOW,
        )


@app.callback()
def callback(
    ctx: typer.Context,
    *,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        envvar="DEBUG",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=print_version,
        is_eager=True,
    ),
    plex_username: Optional[str] = typer.Option(
        None,
        "--plex-username",
        envvar="PLEX_USERNAME",
    ),
    plex_password: Optional[str] = typer.Option(
        None,
        "--plex-password",
        envvar="PLEX_PASSWORD",
    ),
    plex_server_name: Optional[str] = typer.Option(
        None,
        "--plex-server",
        envvar="PLEX_SERVER",
    ),
    plex_library_name: Optional[str] = typer.Option(
        ...,
        "--plex-library",
        envvar="PLEX_LIBRARY",
    ),
) -> None:
    """Manage playlists on a Plex server.

    :param verbose: Write verbose output.
    :param version: Print version and exit.
    :param plex_userame: The username of the Plex account to use.
    :param plex_password: The password of the Plex account to use.
    :param plex_server: The name of the Plex server to use.
    :param plex_library: The name of the library on the Plex server to use.
    """
    # TODO: Just fetch these values via `click.get_current_context()`?
    global _debug, _plex_username, _plex_password, _plex_server_name, _plex_library_name

    _debug = True
    _plex_username = plex_username
    _plex_password = plex_password
    _plex_server_name = plex_server_name
    _plex_library_name = plex_library_name


@app.command()
def servers():
    resources = plex_account().resources()
    for resource in resources:
        if resource.provides == "server":
            echo(resource.name)


@app.command()
def stats():
    secho("Finding Plex library...", nl=False)
    plex_music_section = cast(
        MusicSection, plex_server().library.section(_plex_library_name)
    )
    secho(" Done.")

    secho("Fetching Plex tracks...", nl=False)
    plex_tracks = cast(MediaContainer[Track], plex_music_section.searchTracks())
    secho(" Done.")

    secho("Fetching Plex albums...", nl=False)
    plex_albums = cast(Iterable[Album], plex_music_section.searchAlbums())
    secho(" Done.")

    echo(f"{len(plex_tracks):n} tracks")
    echo(f"{len(plex_albums):n} albums")


@app.command()
def playlists():
    secho("Finding Plex library...", nl=False)
    plex_music_section = cast(
        MusicSection, plex_server().library.section(_plex_library_name)
    )
    secho(" Done.")

    secho("Fetching Plex playlists...", nl=False)
    plex_playlists = cast(Iterable[Playlist], plex_music_section.playlists("audio"))
    secho(" Done.")

    for plex_playlist in plex_playlists:
        echo(f"{plex_playlist.title} ({len(plex_playlist.items()):n} tracks)")


@app.command()
def clear():
    secho("Finding Plex library...", nl=False)
    plex_music_section = cast(
        MusicSection, plex_server().library.section(_plex_library_name)
    )
    secho(" Done.")

    secho("Fetching Plex playlists...", nl=False)
    plex_playlists = cast(Iterable[Playlist], plex_music_section.playlists("audio"))
    secho(" Done.")

    secho("Deleting Plex playlists...", nl=False)
    for plex_playlist in plex_playlists:
        plex_playlist.delete()
    secho(" Done.")


@app.command()
def sync(
    ctx: typer.Context,
    *,
    library_path: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
    ),
):
    """Sync playlists from an Apple music library to a Plex server.

    :param library: The path to the Apple Music library XML file.
    """
    secho("Loading Apple Music library...", nl=False)
    music_library = AppleMusicLibrary.load(library_path)
    secho(" Done.")

    secho("Finding Plex library...", nl=False)
    plex_music_section = cast(
        MusicSection, plex_server().library.section(_plex_library_name)
    )
    secho(" Done.")

    secho("Fetching Plex tracks...", nl=False)
    plex_tracks = cast(MediaContainer[Track], plex_music_section.searchTracks())
    secho(" Done.")

    secho("Fetching Plex playlists...", nl=False)
    plex_playlists = cast(MediaContainer[Playlist], plex_server().playlists("audio"))
    secho(" Done.")

    def get_plex_track_path(plex_track: Track) -> Path:
        media = cast(Media, plex_track.media[0])
        media_part = cast(MediaPart, media.parts[0])
        path = cast(str, media_part.file)
        return Path(unicodedata.normalize("NFC", path)).resolve()

    plex_tracks_by_path = {
        get_plex_track_path(plex_track): plex_track for plex_track in plex_tracks
    }

    if _debug:
        with open("plex-tracks.txt", "w") as file:
            for track_path in plex_tracks_by_path.keys():
                file.write(str(track_path) + "\n")

    for playlist_name, playlist_tracks in music_library.playlists.items():
        plex_playlist = next(
            (
                playlist
                for playlist in plex_playlists
                if playlist.title == playlist_name
            ),
            None,
        )

        sync_playlist(
            playlist_name,
            playlist_tracks,
            plex_music_section,
            plex_tracks_by_path,
            plex_playlist,
        )
