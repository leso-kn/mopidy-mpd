from mopidy_mpd import protocol
from urllib.request import urlopen


def _get_art_url(self, track):
    images = self.core.library.get_images([track.uri]).get()
    if images[track.uri]:
        largest_image = sorted(
            images[track.uri], key=lambda i: i.width or 0, reverse=True
        )[0]
        return largest_image.uri


cover_cache = {}


@protocol.commands.add("albumart")
def albumart(context, uri, offset):
    """
    *musicpd.org, the music database section:*

        ``albumart {URI} {OFFSET}``

        Locate album art for the given song and return a chunk
        of an album art image file at offset OFFSET.

        This is currently implemented by searching the directory
        the file resides in for a file called cover.png, cover.jpg,
        cover.tiff or cover.bmp.

        Returns the file size and actual number of bytes read at
        the requested offset, followed by the chunk requested as
        raw bytes (see Binary Responses), then a newline and the completion code.

        Example::

            albumart foo/bar.ogg 0
            size: 1024768
            binary: 8192
            <8192 bytes>
            OK

    .. versionadded:: 0.21
        New in MPD protocol version 0.21
    """
    global cover_cache

    if uri not in cover_cache:
        (tlid, track) = context.core.playback.get_current_tl_track().get()
        art_url = _get_art_url(context, track)

        if art_url is None:
            return b"binary: 0\n"

        cover_cache[uri] = urlopen(art_url).read()

    data = cover_cache[uri]

    total_size = len(data)
    chunk_size = 8192

    offset = int(offset)
    size = min(chunk_size, total_size - offset)

    if offset + size >= total_size:
        cover_cache.pop(uri)

    return b"size: %d\nbinary: %d\n%b" % (
        total_size,
        size,
        data[offset : offset + size],
    )


# @protocol.commands.add("readpicture") # not yet implemented
def readpicture(context, uri, offset):
    """
    *musicpd.org, the music database section:*

        ``readpicture {URI} {OFFSET}``

        Locate a picture for the given song and return a chunk
        of the image file at offset OFFSET. This is usually
        implemented by reading embedded pictures from
        binary tags (e.g. ID3v2's APIC tag).

        Returns the following values:

        * size: the total file size
        * type: the file's MIME type (optional)
        * binary: see Binary Responses

        If the song file was recognized, but there is no picture,
        the response is successful, but is otherwise empty.

        Example::

            readpicture foo/bar.ogg 0
            size: 1024768
            type: image/jpeg
            binary: 8192
            <8192 bytes>
            OK

    .. versionadded:: 0.21
        New in MPD protocol version 0.21
    """
    # raise exceptions.MpdNotImplemented  # TODO
