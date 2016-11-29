import os
import errno
import certifi
import logging
import mimetypes
import os.path
import uuid
import urlparse
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from ioboxd.core import STORAGE_PATH, AUTHENTICATION, get_client_identity, client_has_identity, Unauthorized

CHUNK_SIZE = 1024 * 1024
HEADERS = {'Connection': 'keep-alive'}

logger = logging.getLogger('')
logger.propagate = False


def get_named_exception(e):
    exc = "".join(("[", type(e).__name__, "] "))
    return "".join((exc, str(e)))


def configure_logging(level=logging.INFO, log_path=None):

    logger.setLevel(level)
    if log_path:
        handler = logging.FileHandler(log_path)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

    return handler


def create_output_dir():

    key = str(uuid.uuid4())
    output_dir = os.path.abspath(os.path.join(STORAGE_PATH, key))
    if not os.path.isdir(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
    return key, output_dir


def get_final_output_path(output_path, output_name=None, ext=''):
    return ''.join([os.path.join(output_path, output_name) if output_name else output_path, ext])


def create_access_descriptor(directory, identity):
    with open(os.path.abspath(os.path.join(directory, ".access")), 'w') as access:
        access.writelines(''.join([identity if identity else "*", '\n']))


def check_access(directory):
    if not AUTHENTICATION:
        return True

    with open(os.path.abspath(os.path.join(directory, ".access")), 'r') as access:
        for identity in access.readlines():
            if client_has_identity(identity.strip()):
                return True
    return False


def authenticate(host, cookies=None, username=None, password=None):
    if username and password:
        session = open_session(host, login_params={'username': username, 'password': password})
    elif cookies:
        session = open_session(host, cookies=cookies)
    else:
        session = open_session(host)

    return session


def open_session(host, cookies=None, login_params=None):
    session = requests.session()
    retries = Retry(connect=5,
                    read=5,
                    backoff_factor=1.0,
                    status_forcelist=[500, 502, 503, 504])

    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))

    if cookies:
        session.cookies.update(cookies)
        return session
    if login_params:
        url = ''.join([host, '/ermrest/authn/session'])
        r = session.post(url, headers=HEADERS, data=login_params, verify=certifi.where())
        if r.status_code > 203:
            raise Unauthorized('Open Session Failed with Status Code: %s\n%s\n' % (r.status_code, r.text))
        else:
            logger.info("Session established: %s", url)

    return session


def get_file(url, output_path, headers, session):
    if output_path:
        try:
            output_dir = os.path.dirname(os.path.abspath(output_path))
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            if not headers:
                headers = HEADERS
            else:
                headers.update(HEADERS)
            if session is not None:
                r = session.get(url, headers=headers, stream=True, verify=certifi.where())
            else:
                r = requests.get(url, headers=headers, stream=True, verify=certifi.where())
            if r.status_code != 200:
                file_error = "File transfer failed: [%s]" % output_path
                url_error = 'HTTP GET Failed for url: %s' % url
                host_error = "Host %s responded:\n\n%s" % (urlparse.urlsplit(url).netloc, r.text)
                # logger.error(file_error)
                # logger.error(url_error)
                # logger.error(host_error)
                raise RuntimeError('%s\n\n%s\n%s' % (file_error, url_error, host_error))
            else:
                with open(output_path, 'wb') as data_file:
                    for chunk in r.iter_content(CHUNK_SIZE):
                        data_file.write(chunk)
                    data_file.flush()
                logger.info('File transfer successful: [%s]' % output_path)
        except requests.exceptions.RequestException as e:
            raise RuntimeError('HTTP Request Exception: %s %s' % (e.errno, e.message))


def guess_mimetype(file_path):
    mtype = mimetypes.guess_type(file_path, False)
    mimetype = "+".join([mtype[0], mtype[1]]) if (mtype[0] is not None and mtype[1] is not None) \
        else (mtype[0] if mtype[0] is not None else mtype[1])
    return mimetype


def has_attr(obj, attr, quiet=False):
    if getattr(obj, attr, None) is None:
        if not quiet:
            logger.warn("Unable to locate attribute [%s] in object: %s" %
                        (attr, str(obj)))
        return False
    return True
