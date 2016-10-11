import os.path

from ioboxd.core import BadRequest
from ioboxd.export.api import *
from ioboxd.export.transforms import *

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

        session = authenticate(host, cookies, username, password)
        create_access_descriptor(base_dir, identity=username if not identity else identity['id'])

        file_list = list()
        for query in catalog_config['queries']:
            url = ''.join([host, path, query['query_path']])
            output_name = query.get('output_name', None)
            output_path = query['output_path']
            output_format = query['output_format']
            output_format_params = query.get('output_format_params', None)
            schema_path = query.get('schema_path', None)
            schema_output_file = os.path.abspath(os.path.join(base_dir, ''.join([output_path, '-schema.json'])))

            try:
                if output_format == 'csv':
                    headers = {'accept': 'text/csv'}
                    ext = '.csv'
                elif output_format == 'json':
                    headers = {'accept': 'application/json'}
                    ext = '.json'
                elif output_format == 'fasta':
                    headers = {'accept': 'application/x-json-stream'}
                    ext = '.json'
                else:
                    raise BadRequest("Unsupported output type: %s" % output_format)

                output_path = get_final_output_path(output_path, output_name, ext)
                output_file = os.path.abspath(os.path.join(base_dir, output_path))
                get_file(url, output_file, headers, session)

                if output_format == 'fasta':
                    result_file = ''.join([os.path.splitext(output_file)[0], '.fasta'])
                    fasta.convert_json_file_to_fasta(output_file, result_file, output_format_params)
                    os.remove(output_file)
                    output_file = result_file

                file_list.append(output_file)

                if schema_path:
                    schema_url = ''.join([host, path, schema_path])
                    get_file(schema_url, schema_output_file, {'accept': 'application/json'}, session)
                    file_list.append(schema_output_file)

            except (RuntimeError, Exception) as e:
                logger.error(get_named_exception(e))
                raise RuntimeError(e)

        return file_list

    finally:
        logger.removeHandler(log_handler)
