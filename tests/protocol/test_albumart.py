from io import BytesIO
from mopidy_mpd.protocol import album_art
from unittest import mock
from mopidy.models import Album, Track, SearchResult, Image
import mopidy_local

from tests import protocol


def mock_get_images(self, uris):
    result = {}
    for uri in uris:
        result[uri] = [
            Image(uri="dummy:/albumart.jpg", width=128, height=128),
            Image(uri="dummy:/albumart-large.jpg", width=640, height=640),
        ]
    return result


def mock_library_search(self, _):
    return [
        SearchResult(
            tracks=[
                Track(
                    uri="dummy:/à",
                    name="a nàme",
                    album=Album(uri="something:àlbum:12345"),
                )
            ]
        )
    ]


class AlbumArtTest(protocol.BaseTestCase):
    def test_albumart_for_track_without_art(self):
        track = Track(
            uri="dummy:/à",
            name="a nàme",
            album=Album(uri="something:àlbum:12345"),
        )
        self.backend.library.dummy_library = [track]
        self.core.tracklist.add(uris=[track.uri]).get()

        self.core.playback.play().get()

        self.send_request("albumart file:///home/test/music.flac 0")
        self.assertInResponse("binary: 0")

    def test_albumart_for_invalid_uri(self):
        self.core.playback.play().get()

        self.send_request("albumart an-invalid-uri 0")

        self.assertInResponse("binary: 0")

    def test_albumart_for_inaccessible_file(self):
        track = Track(
            uri="dummy:/à",
            name="a nàme",
            album=Album(uri="something:àlbum:12345"),
        )
        self.backend.library.dummy_library = [track]
        self.core.tracklist.add(uris=[track.uri]).get()

        self.core.playback.play().get()

        def raise_inaccessible_exception(_):
            raise Exception("inaccessible file")

        with mock.patch.object(
            album_art, "urlopen", raise_inaccessible_exception
        ):
            self.send_request("albumart file:///home/test/music.flac 0")

        self.assertInResponse("binary: 0")

    @mock.patch.object(
        protocol.core.library.LibraryController, "get_images", mock_get_images
    )
    def test_albumart(self):
        track = Track(
            uri="dummy:/à",
            name="a nàme",
            album=Album(uri="something:àlbum:12345"),
        )
        self.backend.library.dummy_library = [track]
        self.core.tracklist.add(uris=[track.uri]).get()

        self.core.playback.play().get()

        ##
        expected = b"result"

        with mock.patch.object(
            album_art, "urlopen", return_value=BytesIO(expected)
        ):
            self.send_request("albumart file:///home/test/music.flac 0")

        self.assertInResponse("binary: " + str(len(expected)))

    @mock.patch.object(
        mopidy_local.Extension, "get_image_dir", lambda _: "/dummy"
    )
    def test_albumart_for_mopidy_local_track(self):
        track = Track(
            uri="dummy:/à",
            name="a nàme",
            album=Album(uri="something:àlbum:12345"),
        )
        self.backend.library.dummy_library = [track]
        self.core.tracklist.add(uris=[track.uri]).get()

        self.core.playback.play().get()

        ##
        expected = b"result"

        with mock.patch.object(
            album_art, "urlopen", return_value=BytesIO(expected)
        ):
            self.send_request("albumart /local/home/test/music.flac 0")

        self.assertInResponse("binary: " + str(len(expected)))

    def test_albumart_for_mopidy_library_search_track(self):
        track = Track(
            uri="dummy:/à",
            name="a nàme",
            album=Album(uri="something:àlbum:12345"),
        )
        self.backend.library.dummy_library = [track]
        self.core.tracklist.add(uris=[track.uri]).get()

        self.core.playback.play().get()

        with mock.patch.object(
            protocol.core.library.LibraryController,
            "search",
            mock_library_search,
        ):
            self.send_request("albumart file:///home/test/music.flac 0")

        self.assertInResponse("binary: 0")
