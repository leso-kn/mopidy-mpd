import logging
from mopidy_mpd import protocol
from urllib.request import urlopen

logger = logging.getLogger(__name__)

cover_cache = {}

def _get_art_uri(context, uri):
    image_uri = ''
    images = context.core.library.get_images([uri]).get()
    if images:
        if images[uri]:
            #To do: implement user config parameter for image size preference
            #For now return smallest image to limit wireless download size
            image_uri = sorted(
                images[uri], key=lambda i: i.width or 0, reverse=False
            )[0].uri
            logger.debug("Found image uri: %s", str(image_uri))
    return image_uri

def _search_uri(context, uri):
    album_uri = ''
    uriList = context.core.library.search({'uri': [uri]}).get()
    if uriList:
        album_uri = str(uriList[0].tracks[0].album.uri)
        logger.debug("Found album uri: %s", str(album_uri))
        # Note an album uri is encrypted and MD5 hashed
    return album_uri

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
    art_uri = ''

    logger.debug("Album art request for uri: %s", str(uri)) 

    if uri not in cover_cache:
        art_uri = _get_art_uri(context ,uri)   
        if not art_uri:
            # Attempt to find art via a library uri search
            # Applicable when an MPD client supplies only the album part of a uri
            album_uri = _search_uri(context, uri)
            if album_uri:
                art_uri = _get_art_uri(context, album_uri)
            if not art_uri:
                return b"binary: 0\n"

        art_uri = art_uri.replace("/local/", "file:///media/Data1/Mopidy/Data/local/images/", 1) 
       
        logger.info("Open image uri: %s", str(art_uri))
            
        cover_cache[uri] = urlopen(art_uri).read()

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
