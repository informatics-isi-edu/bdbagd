import simplejson as json
from collections import OrderedDict


def convert_json_obj_to_fasta_lines(obj, params):

    comment_line = ''
    data_line = ''

    column_map = params.get("column_map", None)
    if (len(obj) > 1) and (not column_map):
        raise RuntimeError("FASTA converter input data has more than one element and a column map was not specified.")
    elif len(obj) == 1:
        k, v = obj.popitem()
        lines = str("%s\n" % v)
    else:
        for k, v in obj.items():
            if column_map.get(k, None) == "comment":
                if comment_line:
                    comment_line += str(" | %s" % v)
                else:
                    comment_line = str("> %s" % v)
            elif column_map.get(k, None) == "data":
                data_line += v
        lines = str("%s\n%s\n" % (comment_line, data_line))

    return lines


def convert_json_file_to_fasta(input_file, output_file, params):

    with open(input_file, "r") as input_data, open(output_file, "w") as output_data:
        line = input_data.readline().lstrip()
        input_data.seek(0)
        is_json_stream = False
        if line.startswith('{'):
            data = input_data
            is_json_stream = True
        else:
            data = json.load(input_data, object_pairs_hook=OrderedDict)

        for entry in data:
            if is_json_stream:
                entry = json.loads(entry, object_pairs_hook=OrderedDict)

            lines = convert_json_obj_to_fasta_lines(entry, params)
            output_data.writelines(lines)


