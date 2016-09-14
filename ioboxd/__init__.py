#
# Copyright 2016 University of Southern California
# Distributed under the Apache License, Version 2.0. See LICENSE for more info.
#

from ioboxd.providers.export.rest import *
from ioboxd.providers.export.bdbag.rest import *
from ioboxd.providers.export.file.rest import *


def web_urls():
    """Builds and returns the web_urls for web.py.
    """
    urls = (
        '/export/bdbag/?', ExportBag,
        '/export/bdbag/([^/]+)', ExportRetrieve,
        '/export/bdbag/([^/]+)/(.+)', ExportRetrieve,
        '/export/file/?', ExportFiles,
        '/export/file/([^/]+)', ExportRetrieve,
        '/export/file/([^/]+)/(.+)', ExportRetrieve,
    )
    return tuple(urls)


class IOBoxException (Exception):
    """Base class for IOBox API exceptions."""
    pass


class BadRequest (IOBoxException):
    """Exceptions representing malformed requests."""
    pass


class Conflict (IOBoxException):
    """Exceptions representing conflict between usage and current state."""
    pass


class Forbidden (IOBoxException):
    """Exceptions representing lack of authorization for known client."""
    pass


class Unauthenticated (IOBoxException):
    """Exceptions representing lack of authorization for anonymous client."""
    pass


class NotFound (IOBoxException):
    """Exceptions representing attempted access to unknown resource."""
    pass

