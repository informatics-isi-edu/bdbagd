#
# Copyright 2016 University of Southern California
# Distributed under the Apache License, Version 2.0. See LICENSE for more info.
#

"""Core service logic and dispatch rules for IOBox REST API
   Most of this logic lifted from hatrac...

"""

import os
import logging
import web
import json
import random
import base64
import datetime
import pytz
import webauthn2
import struct
import urllib
import ioboxd
from collections import OrderedDict
from logging.handlers import SysLogHandler
from webauthn2.util import merge_config, context_from_environment

SERVICE_BASE_DIR = os.path.expanduser("~")
STORAGE_BASE_DIR = os.path.join("ioboxd", "data")

DEFAULT_CONFIG = {
    "storage_path": os.path.abspath(os.path.join(SERVICE_BASE_DIR, STORAGE_BASE_DIR)),
    "authentication": None,
    "404_html": "<html><body><h1>Resource Not Found</h1><p>The requested resource could not be found at this location."
                "</p><p>Additional information:</p><p><pre>%(message)s</pre></p></body></html>",
    "403_html": "<html><body><h1>Access Forbidden</h1><p>%(message)s</p></body></html>",
    "401_html": "<html><body><h1>Authentication Required</h1><p>%(message)s</p></body></html>",
    "400_html": "<html><body><h1>Bad Request</h1><p>One or more request parameters are incorrect. "
                "</p><p>Additional information:</p><p><pre>%(message)s</pre></p></body></html>",
}
DEFAULT_CONFIG_FILE = os.path.abspath(os.path.join(SERVICE_BASE_DIR, 'ioboxd_config.json'))

config = dict()
if os.path.isfile(DEFAULT_CONFIG_FILE):
    config = merge_config(jsonFileName=DEFAULT_CONFIG_FILE)
else:
    config = merge_config(defaults=DEFAULT_CONFIG)

STORAGE_PATH = config.get('storage_path')

# instantiate webauthn2 manager if using webauthn
AUTHENTICATION = config.get("authentication", None)
webauthn2_manager = webauthn2.Manager() if AUTHENTICATION == "webauthn" else None

# setup logger and web request log helpers
logger = logging.getLogger('ioboxd')
logger.setLevel(logging.INFO)
try:
    # the use of '/dev/log' causes SysLogHandler to assume the availability of Unix sockets
    sysloghandler = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL1)
except:
    # this fallback allows this file to at least be cleanly imported on non-Unix systems
    sysloghandler = logging.StreamHandler()
syslogformatter = logging.Formatter('%(name)s[%(process)d.%(thread)d]: %(message)s')
sysloghandler.setFormatter(syslogformatter)
logger.addHandler(sysloghandler)


def log_parts():
    """Generate a dictionary of interpolation keys used by our logging template."""
    now = datetime.datetime.now(pytz.timezone('UTC'))
    elapsed = (now - web.ctx.ioboxd_start_time)
    client_identity_obj = web.ctx.webauthn2_context and web.ctx.webauthn2_context.client or None
    parts = dict(
        elapsed=elapsed.seconds + 0.001 * (elapsed.microseconds / 1000),
        client_ip=web.ctx.ip,
        client_identity_obj=client_identity_obj,
        reqid=web.ctx.ioboxd_request_guid
    )
    return parts


def request_trace(tracedata):
    """Log one tracedata event as part of a request's audit trail.

       tracedata: a string representation of trace event data
    """
    parts = log_parts()
    od = OrderedDict([
        (k, v) for k, v in [
            ('elapsed', parts['elapsed']),
            ('req', parts['reqid']),
            ('trace', tracedata),
            ('client', parts['client_ip']),
            ('user', parts['client_identity_obj']),
        ]
        if v
    ])
    logger.info(json.dumps(od, separators=(', ', ':')).encode('utf-8'))


class RestException(web.HTTPError):
    message = None
    status = None
    headers = {
        'Content-Type': 'text/plain'
    }

    def __init__(self, message=None, headers=None):
        if headers:
            hdr = dict(self.headers)
            hdr.update(headers)
        else:
            hdr = self.headers
        msg = message or self.message
        web.HTTPError.__init__(self, self.status, hdr, msg + '\n')


class NotModified(RestException):
    status = '304 Not Modified'
    message = 'Resource not modified.'


class TemplatedRestException(RestException):
    error_type = ''
    supported_content_types = ['text/plain', 'text/html']

    def __init__(self, message=None, headers=None):
        # filter types to those for which we have a response template, or text/plain which we always support
        supported_content_types = [
            content_type for content_type in self.supported_content_types
            if "%s_%s" % (
                self.error_type, content_type.split('/')[-1]) in config or content_type == 'text/plain'
        ]
        default_content_type = supported_content_types[0]
        # find client's preferred type
        content_type = webauthn2.util.negotiated_content_type(supported_content_types, default_content_type)
        # lookup template and use it if available
        template_key = '%s_%s' % (self.error_type, content_type.split('/')[-1])
        if template_key in config:
            message = config[template_key] % dict(message=message)
        header = {'Content-Type': content_type}
        headers = headers.update(header) if headers else header
        RestException.__init__(self, message, headers)
        web.header('Content-Type', content_type)


class BadRequest(TemplatedRestException):
    error_type = '400'
    status = '400 Bad Request'
    message = 'Request malformed.'


class Unauthorized(TemplatedRestException):
    error_type = '401'
    status = '401 Unauthorized'
    message = 'Access requires authentication.'


class Forbidden(TemplatedRestException):
    error_type = '403'
    status = '403 Forbidden'
    message = 'Access forbidden.'


class NotFound(TemplatedRestException):
    error_type = '404'
    status = '404 Not Found'
    message = 'Resource not found.'


class NoMethod(RestException):
    status = '405 Method Not Allowed'
    message = 'Request method not allowed on this resource.'


class Conflict(RestException):
    status = '409 Conflict'
    message = 'Request conflicts with state of server.'


class LengthRequired(RestException):
    status = '411 Length Required'
    message = 'Content-Length header is required for this request.'


class PreconditionFailed(RestException):
    status = '412 Precondition Failed'
    message = 'Resource state does not match requested preconditions.'


class BadRange(RestException):
    status = '416 Requested Range Not Satisfiable'
    message = 'Requested Range is not satisfiable for this resource.'

    def __init__(self, msg=None, headers=None, nbytes=None):
        RestException.__init__(self, msg, headers)
        if nbytes is not None:
            web.header('Content-Range', 'bytes */%d' % nbytes)


class InternalServerError(RestException):
    status = '500 Internal Server Error'
    message = 'A processing error prevented the server from fulfilling this request.'


class NotImplemented(RestException):
    status = '501 Not Implemented'
    message = 'Request not implemented for this resource.'


class BadGateway(RestException):
    status = '502 Bad Gateway'
    message = 'A downstream processing error prevented the server from fulfilling this request.'


def client_has_identity(identity):
    if identity == "*":
        return True
    get_client_auth_context()
    for attrib in web.ctx.webauthn2_context.attributes:
        if attrib['id'] == identity:
            return True
    return False


def get_client_identity():
    get_client_auth_context()
    if web.ctx.webauthn2_context and web.ctx.webauthn2_context.client:
        return web.ctx.webauthn2_context.client
    else:
        return None


def get_client_auth_context():

    if web.ctx.webauthn2_context and web.ctx.webauthn2_context.client:
        return

    try:
        web.ctx.webauthn2_context = context_from_environment()
        if web.ctx.webauthn2_context.client is None:
            web.ctx.webauthn2_context = webauthn2_manager.get_request_context() if webauthn2_manager else None
            logger.debug("webauthn2_context: %s" % web.ctx.webauthn2_context)
            # if web.ctx.webauthn2_context and web.ctx.webauthn2_context.client is None:
            #    raise Unauthorized('The requested service requires client authentication.')
    except (ValueError, IndexError), ev:
        raise Unauthorized('The requested service requires client authentication.')


def web_method():
    """Augment web handler method with common service logic."""

    def helper(original_method):
        def wrapper(*args):
            # request context init
            web.ctx.ioboxd_request_guid = base64.b64encode(struct.pack('Q', random.getrandbits(64)))
            web.ctx.ioboxd_start_time = datetime.datetime.now(pytz.timezone('UTC'))
            web.ctx.ioboxd_request_content_range = '-/-'
            web.ctx.ioboxd_request_error_detail = None
            web.ctx.ioboxd_content_type = None
            web.ctx.webauthn2_manager = webauthn2_manager
            web.ctx.webauthn2_context = webauthn2.Context()  # set empty context for sanity
            web.ctx.ioboxd_request_trace = request_trace

            # get client authentication context
            get_client_auth_context()
            try:
                # run actual method
                return original_method(*args)
            except web.HTTPError as e:
                web.ctx.ioboxd_request_error_detail = e.data
                raise
            except Exception as e:
                web.ctx.ioboxd_request_error_detail = str(e)
                raise
            finally:
                # finalize
                parts = log_parts()
                session = web.ctx.webauthn2_context.session if web.ctx.webauthn2_context else None
                if session is None or isinstance(session, dict):
                    pass
                else:
                    session = session.to_dict()

                try:
                    dcctx = web.ctx.env.get('HTTP_DERIVA_CLIENT_CONTEXT', 'null')
                    dcctx = urllib.unquote(dcctx)
                    dcctx = json.loads(dcctx)
                except:
                    dcctx = None

                od = OrderedDict([
                    (k, v) for k, v in [
                        ('elapsed', parts['elapsed']),
                        ('req', parts['reqid']),
                        ('scheme', web.ctx.protocol),
                        ('host', web.ctx.host),
                        ('status', web.ctx.status),
                        ('detail', web.ctx.ioboxd_request_error_detail),
                        ('method', web.ctx.method),
                        ('path', web.ctx.env['REQUEST_URI']),
                        ('range', web.ctx.ioboxd_request_content_range),
                        ('type', web.ctx.ioboxd_content_type),
                        ('client', parts['client_ip']),
                        ('user', parts['client_identity_obj']),
                        ('referrer', web.ctx.env.get('HTTP_REFERER')),
                        ('agent', web.ctx.env.get('HTTP_USER_AGENT')),
                        ('session', session),
                        ('track', web.ctx.webauthn2_context.tracking if web.ctx.webauthn2_context else None),
                        ('dcctx', dcctx),
                    ]
                    if v
                ])
                logger.info(json.dumps(od, separators=(', ', ':')).encode('utf-8'))

        return wrapper

    return helper


class RestHandler(object):
    """Generic implementation logic for ioboxd REST API handlers.

    """

    def __init__(self):
        self.get_body = True
        self.http_etag = None
        self.http_vary = webauthn2_manager.get_http_vary() if webauthn2_manager else None

    def trace(self, msg):
        web.ctx.ioboxd_request_trace(msg)

    def get_content(self, file_path, client_context, get_body=True):

        web.ctx.status = '200 OK'
        nbytes = os.path.getsize(file_path)
        web.header('Content-Length', nbytes)

        if not get_body:
            return

        try:
            f = open(file_path, 'rb')
            return f.read()
        except Exception as e:
            raise NotFound(e)

    def create_response(self, urls):
        """Form response for resource creation request."""
        web.ctx.status = '201 Created'
        web.header('Content-Type', 'text/uri-list')
        if isinstance(urls, str):
            web.header('Location', urls)
            body = urls + '\n'
        elif isinstance(urls, list):
            body = '\n'.join(urls)
        else:
            body = urls
        web.header('Content-Length', len(body))
        return body

    def delete_response(self):
        """Form response for deletion request."""
        web.ctx.status = '204 No Content'
        return ''

    def update_response(self):
        """Form response for update request."""
        web.ctx.status = '204 No Content'
        return ''

    @web_method()
    def HEAD(self, *args):
        """Get resource metadata."""
        self.get_body = False
        if hasattr(self, 'GET'):
            return self.GET(*args)
        else:
            raise NoMethod('Method HEAD not supported for this resource.')

