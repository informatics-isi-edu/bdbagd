#
# Copyright 2016 University of Southern California
# Distributed under the Apache License, Version 2.0. See LICENSE for more info.
#

from ioboxd.export.rest import ExportRetrieve
from ioboxd.export.providers.file.rest import ExportFiles
from ioboxd.export.providers.bdbag.rest import ExportBag


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
