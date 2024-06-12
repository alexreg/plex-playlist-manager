from itertools import islice
from typing import *

_T_co = TypeVar("_T_co", covariant=True)


def batched(iterable: Iterable[_T_co], n: int) -> Iterator[tuple[_T_co, ...]]:
    """Batch data from the iterable into tuples of length n. The last batch may be shorter than n."""
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        yield batch
