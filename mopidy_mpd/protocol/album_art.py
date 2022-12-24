import logging
from mopidy_mpd import protocol
from urllib.request import urlopen, ProxyHandler
from uritools import isuri, urisplit
from pathlib import PurePath

logger = logging.getLogger(__name__)

cover_cache = {}


class _config:
    config = {}
    image_dir = ""
    
    def load_config(context):
        from mopidy_local import Extension as local_ext
        _config.config = context.dispatcher.config
        logger.debug("Loaded config: %s", str(_config.config))
        
        _config.image_dir = local_ext.get_image_dir(_config.config)
        logger.debug("Local image directory: %s", str(_config.image_dir))


def _get_art_uri(context, uri):
    # Get art uri from backend libraries
    # Note: for mopidy_local extension images configuration parameter
    # local/album_art_files determines which images are made available

    image_uri = ""

    images = context.core.library.get_images([uri]).get()

    if images:
        if images[uri]:
            # Select smallest image with a minium width of 600px to limit
            # download and client cache size.
            # If no image with min. width exists use largest available.
            # To do: implement user config parameter for image size preference
            images_sorted = sorted(
                images[uri], key=lambda i: i.width or 0, reverse=False
            )
            for i in images_sorted:
                if i.width > 599:
                    image_uri = i.uri
                    break
            if not image_uri:
                image_uri = images_sorted[-1].uri

            logger.debug("Found image uri in library: %s", str(image_uri))
    return image_uri


def _search_uri(context, uri):
    # Request image uri from backend libraries

    album_uri = ""

    resultList = context.core.library.search({"uri": [uri]}).get()
    if resultList[0].tracks:
        album_uri = str(resultList[0].tracks[0].album.uri)
        logger.debug("Found album uri in library: %s", str(album_uri))
        # Note an album uri is encrypted and MD5 hashed
    return album_uri


def _get_local_art_uri(context, uri):
    # Translate local extension image uri value to absolute file path

    art_uri = ""

    art_uri = PurePath(_config.image_dir).joinpath(PurePath(uri).name).as_uri()
    logger.debug("Local art filename: %s", str(art_uri))
    return art_uri


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
        New in MPD protocol version 0.21.0
        Major improvement in MPD  protocol version 0.21.11
    """

    global cover_cache
    art_uri = ""

    logger.debug("Album art request for uri: %s", str(uri))

    if not isuri(uri):
        logger.debug("Not a valid uri: %s", str(uri))
        return b"binary: 0\n"

    if not _config.config:
        _config.load_config(context)

    if uri not in cover_cache:
        art_uri = _get_art_uri(context, uri)
        if not art_uri:
            # Attempt to find art via a library uri search
            # Applicable when an MPD client supplies only the album part of a uri

            album_uri = _search_uri(context, uri)
            
            if album_uri:
                art_uri = _get_art_uri(context, album_uri)
            if not art_uri:
                uri_scheme = urisplit(uri).scheme
                if uri_scheme == "http" or uri_scheme == "https":
                    # As a last resort, allow external web searches (incl. internet)

                    art_uri = uri
                else:
                    logger.debug("Can't find album art for uri: %s", str(uri))
                    return b"binary: 0\n"

        if art_uri.find("local", 1, 7) != -1:
            # For images obtained from local backend translate file path to uri          
            art_uri = _get_local_art_uri(context, art_uri)

        try:
            # The uri of local files uses the 'file:' scheme. urllib reads
            # these files from the filesystem and not via Mopidy HTTP
            cover_cache[uri] = urlopen(art_uri).read()
        except:
            logger.debug("Can't open uri: %s", art_uri)
            return b"binary: 0\n"

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
