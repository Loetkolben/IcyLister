import sys, re

from urllib.request import Request, urlopen
from datetime import datetime


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_stream(stream_url, user_agent="VLC/2.2.4 LibVLC/2.2.4"):
    """
    Gets the stream by performing the appropriate HTTP request.
    Args:
        stream_url: HTTP URL where the stream can be found
        user_agent: Optional. User-Agent to supply to the server. Defaults to 'VLC/2.2.4 LibVLC/2.2.4'

    Returns:
        The data stream from the server as obtained by `urllib.request.urlopen(...)`.
        Has the special attribute `metaint` which is the mp3 meta interval.
    """
    request = Request(stream_url, headers={"Icy-MetaData": "1",
                                           "User-Agent": user_agent})
    stream = urlopen(request)

    for header, value in stream.getheaders():
        if header.lower() == "icy-metaint":
            meta_interval = int(value)
    try:
        meta_interval
    except NameError:
        raise RuntimeError("Server did NOT respond with a \'Icy-Metaint\' header. "
                           "This makes it impossible to extract metadata (we do not know which frames hold metadata). "
                           "Are you sure the server we're talking to is a Icecast (... compatible thingy)?")

    stream.metaint = meta_interval
    return stream


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
            if char == ';':
                if current_value[0] == "'" and current_value[-1] == "'":
                    # Cut away the "'" at the beginning and end if they exist.
                    current_value = current_value[1:-1]
                metadata[current_tag] = current_value
                current_tag = ""
                current_value = ""
                reading_tag = True
            else:
                current_value += char
    return metadata


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


def print_stream_titles(stream_url, title_blacklist=[]):
    """
    Prints `Current Time <TAB> StreamTitle` as acquired from stream metadata to STDOUT,
    until interrupted by Ctrl+C. Errors will be printed to STDERR.
    Args:
        stream_url: Stream URL
        title_blacklist: A list of compiled regexes that are used to filter out (-> print to STDERR) unwanted titles.
    """
    stream = get_stream(stream_url)
    meta_interval = stream.metaint

    try:
        while True:
            meta_data = get_metadata_once(stream, meta_interval)
            if meta_data is not None:
                if "StreamTitle" in meta_data:
                    is_blacklisted = False
                    for bl_entry in title_blacklist:
                        if bl_entry.match(meta_data["StreamTitle"]):
                            is_blacklisted = True
                    if is_blacklisted:
                        eprint(str(datetime.now()) + "\t" + meta_data["StreamTitle"])
                    else:
                        print(str(datetime.now()) + "\t" + meta_data["StreamTitle"])
                else:
                    eprint(str(datetime.now()) + "\t" + "No 'StreamTitle' in metadata: " + str(meta_data))
    except KeyboardInterrupt:
        stream.close()


if __name__ == "__main__":
    url = sys.argv[1]

    blacklist_str = sys.argv[2:]
    blacklist_re = []
    for entry in blacklist_str:
        blacklist_re.append(re.compile(entry))

    print_stream_titles(url, blacklist_re)
