import os.path
import logging
from ioboxd.core import BadRequest, Unauthorized
from ioboxd.providers.export.api import configure_logging, create_access_descriptor, open_session, get_file

logger = logging.getLogger('')
logger.propagate = False


def export_files(config=None, cookies=None, base_dir=None, identity=None, quiet=False):

    log_handler = configure_logging(logging.WARN if quiet else logging.INFO,
                                    log_path=os.path.abspath(os.path.join(base_dir, '.log')))
    try:
        try:
            if not config:
                raise BadRequest("No configuration provided.")
            catalog_config = config['catalog']
            host = catalog_config['host']
            path = catalog_config['path']
            username = catalog_config.get('username', None)
            password = catalog_config.get('password', None)
        except Exception as e:
            raise BadRequest('Error parsing configuration: %s' % e)

        if username and password:
            session = open_session(host, login_params={'username': username, 'password': password})
        elif cookies:
            session = open_session(host, cookies=cookies)
        else:
            raise Unauthorized("The requested service requires authentication.")

        create_access_descriptor(base_dir, identity)

        file_list = list()
        for query in catalog_config['queries']:
            url = ''.join([host, path, query['query_path']])
            output_name = query.get('output_name', None)
            output_path = query['output_path']
            output_format = query['output_format']
            schema_path = query.get('schema_path', None)
            schema_output_file = os.path.abspath(os.path.join(base_dir, ''.join([output_path, '-schema.json'])))

            try:
                if output_format == 'csv':
                    headers = {'accept': 'text/csv'}
                    output_path = \
                        ''.join([os.path.join(output_path, output_name) if output_name else output_path, '.csv'])
                    output_file = os.path.abspath(os.path.join(base_dir, output_path))
                elif output_format == 'json':
                    headers = {'accept': 'application/json'}
                    output_path = \
                        ''.join([os.path.join(output_path, output_name) if output_name else output_path, '.json'])
                    output_file = os.path.abspath(os.path.join(base_dir, output_path))
                else:
                    raise BadRequest("Unsupported output type: %s" % output_format)

                get_file(url, output_file, headers, session)
                file_list.append(output_file)

                if schema_path:
                    schema_url = ''.join([host, path, schema_path])
                    get_file(schema_url, schema_output_file, {'accept': 'application/json'}, session)
                    file_list.append(schema_output_file)

                return file_list

            except RuntimeError as e:
                logger.error("Unhandled runtime error: %s", e)
                raise e

    finally:
        logger.removeHandler(log_handler)
