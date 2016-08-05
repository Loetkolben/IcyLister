import sys

from urllib.request import Request, urlopen
from datetime import datetime

BAD_ARTISTS = ["ANTENNE BAYERN"]


def print_streamtitle_formatted(url):
    stream = get_stream(url)
    meta_interval = stream.metaint

    try:
        while True:
            meta_data_parsed = get_metadata_once(stream, meta_interval)
            if meta_data_parsed is not None:
                if "StreamTitle" in meta_data_parsed:
                    try:
                        artist, song = meta_data_parsed["StreamTitle"].split(" - ", 1)
                        if artist not in BAD_ARTISTS:
                            print(str(datetime.now()) + "\t" + artist + " ~ " + song)
                        else:
                            eprint(str(datetime.now()) + "\t" + artist + " ~ " + song)
                    except ValueError:  # Unpack error
                        eprint(str(datetime.now()) + "\t" + "StreamTitle bad(?):" + meta_data_parsed["StreamTitle"])
                else:
                    eprint(str(datetime.now()) + "\t" + str(meta_data_parsed))
    except KeyboardInterrupt:
        stream.close()


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_stream(stream_url):
    """
    Gets the stream, pretending to be VLC media player (via User-Agent header).
    Args:
        stream_url: HTTP URL where the stream can be found

    Returns:
        The data stream from the server as obtained by `urllib.request.urlopen(...)`.
        Has the special attribute `metaint` which is the mp3 meta interval.
    """
    request = Request(stream_url, headers={"Icy-MetaData": "1",
                                           "User-Agent": "VLC/2.2.4 LibVLC/2.2.4"})
    stream = urlopen(request)

    for header, value in stream.getheaders():
        if header.lower() == "icy-metaint":
            meta_interval = int(value)
    try:
        meta_interval
    except NameError:
        print("Server did NOT respond with a \'Icy-Metaint\' header, cannot extract metadata!")
        print("Are you sure the server we're talking to is a Icecast (... compatible thingy)?")
        meta_interval = None

    stream.metaint = meta_interval

    return stream


def get_metadata_once(stream, metaint):
    """
    Read `metaint` bytes from the stream, get and parse the metadata.
    Args:
        stream: stream from `get_stream(...)`
        metaint: metaint fron `get_stream(...)`

    Returns:
        The parsed metadata as a dict (key => value) (sometimes potentially unescaped), if available.
        Returns `None` if metadata length was specified as 0.
    """
    stream.read(metaint)  # Eat the useless mp3 data
    meta_len = int(stream.read(1).hex(), 16) * 16  # This just feels so wrong. There has to be a better way...
    if meta_len > 0:
        meta_data = stream.read(meta_len).replace(b"\x00", b"")
        meta_data = meta_data.decode("Windows-1252")  # Default western code page? Seems to work, so...
        return parse_icy_metadata(meta_data)


def parse_icy_metadata(data_string):
    """
    Args:
        data_string: The extracted metadata, as string

    Returns:
        dict mapping tag to value
    """
    metadata = {}

    current_tag = ""
    current_value = ""
    reading_tag = True

    for char in data_string:
        if reading_tag:  # Are we currently reading what should be part of a tag
            if char == '=':
                reading_tag = False
            else:
                current_tag += char
        else:  # Currently reading value field
            if char == "'":
                pass  # I hope this works
            elif char == ';':
                metadata[current_tag] = current_value
                current_tag = ""
                current_value = ""
                reading_tag = True
            else:
                current_value += char
    return metadata


if __name__ == "__main__":
    print_streamtitle_formatted("http://mp3channels.webradio.antenne.de:80/antenne")
