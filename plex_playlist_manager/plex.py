from typing import *

from plexapi.exceptions import PlexApiException


T = TypeVar("T")


def plex_batch(
    func: Callable[..., List[T]], batch_size: int = 50, **kwargs: Any
) -> Iterator[T]:
    """Call API method in batches and yield combined results."""
    container_start = 0
    container_size = batch_size

    while True:
        container = func(
            container_start=container_start,
            maxresults=container_size,
            **kwargs,
        )
        if not container:
            break
        container_start += container_size
        yield from container
