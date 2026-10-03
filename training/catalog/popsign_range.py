"""Thread-local keep-alive connections for verified, bounded PopSign range reads."""
import http.client
import re
import threading
import time
from urllib.parse import urlsplit

LOCAL = threading.local()


def request(url, start, size):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'signdata.cc.gatech.edu'
            or not parsed.path.startswith('/data/popsign_v1_0/game/train/')
            or parsed.query or parsed.fragment):
        raise ValueError('Only official training archives are allowed')
    if type(start) is not int or type(size) is not int or start < 0 or not 0 < size <= 64 * 1024 * 1024:
        raise ValueError('Invalid byte range')
    for attempt in range(4):
        try:
            connection = getattr(LOCAL, 'connection', None)
            if connection is None:
                connection = LOCAL.connection = http.client.HTTPSConnection(parsed.netloc, timeout=30)
            connection.request('GET', parsed.path, headers={'Range': f'bytes={start}-{start+size-1}'})
            response = connection.getresponse()
            expected = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.getheader('Content-Range', ''))
            if (response.status != 206 or not expected or
                    tuple(map(int, expected.groups()[:2])) != (start, start + size - 1)):
                raise ValueError('Server did not return the requested byte range')
            data = response.read(size + 1)
            if len(data) != size:
                raise ValueError('Incomplete or oversized range response')
            return data
        except Exception:
            connection = getattr(LOCAL, 'connection', None)
            if connection is not None:
                connection.close()
            LOCAL.connection = None
            if attempt == 3:
                raise
            time.sleep(attempt + 1)
