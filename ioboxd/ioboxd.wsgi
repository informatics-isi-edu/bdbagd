#
# Copyright 2016 University of Southern California
# Distributed under the Apache License, Version 2.0. See LICENSE for more info.
#

import web
import ioboxd

application = web.application(ioboxd.web_urls(), globals()).wsgifunc()
