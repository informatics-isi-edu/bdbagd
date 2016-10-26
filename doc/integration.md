# Chaise Integration

The `ioboxd` service integration with Chaise is driven primarily through the use of ERMrest annotations.

### Export 

Export of data from Chaise is configured through the use of *export templates*. An export template is a JSON object that
 is used in an ERMrest table annotation payload.  The annotation is specified using the following annotation key:
* `tag:isrd.isi.edu,2016:export`

The annotation payload is a JSON object containing a single array of `template` objects. One or more templates can be 
specified for a given table entity.  Templates specify a format name and type, followed by a set of output descriptor 
objects. A template output descriptor maps one or more source table queries to one or more output file destinations.  

The table entity that the template is bound to is considered the *root* of the query for join purposes. In other words, 
any output sources listed in a table's export templates must have a foreign key relationship to the table entity that the 
template is applied to.

The object structure of an export template annotation is defined as follows:

## root (object)
| Variable | Type | Inclusion| Description |
| --- | --- | --- | --- |
| `templates` | array[`template`] | required | An array of `template` objects.
## `template` (object)
| Variable | Type | Inclusion| Description |
| --- | --- | --- | --- |
| `name`| string | required | The name of the template instance, which should be unique among all other template instances in this `templates` array.
| `format_name` | string | required | The display name that will be used to populate the Chaise export format drop-down box for this `template`. 
| `format_type` | string, enum [`"FILE"`,`"BAG"`] | required | One of two keywords; `"FILE"` or `"BAG"`, used to determine the container format for results.
| `outputs` | array[`output`] | required | An array of `output` objects. See below.

## `output` (object)
| Variable | Type | Inclusion| Description |
| --- | --- | --- | --- |
| `source` | `source` | required | An object that contains parameters used to generate source data by querying ERMrest.
| `destination` | `destination` | required | An object that contains parameters used to render the results of the source query into a specified destination format. 

## `source` (object)
| Variable | Type | Inclusion| Description |
| --- | --- | --- | --- |
| `name` | string | required | A schema-qualified ERMrest table name in the form `schema_name:table_name`.
| `type` | string, enum [`entity`,`attribute`, `attributegroup`] | required | The type of ERMrest query projection to perform.  Valid values are `entity`,`attribute`, and `attributegroup`.
| `filter` | string | optional | An optional ERMrest filter predicate.
| `column_map` | object | conditionally required | For queries where the `type` is set to `attribute` or `attributegroup`, a column map must be specified.  The column map is a simple 'dictionary' object which serves two purposes: the keys of the dictionary specify the columns to select from source table, while the values represent the name of the result column in tbe target projection.

## `destination` (object)
| Variable | Type | Inclusion| Description |
| --- | --- | --- | --- |
| `name` | string | required | The base name to use for the output file.
| `type` | string | required | A type keyword that determines the output format. Supported values are dependent on the `template`.`format_type` selected. For the `FILE` type, the values `csv`, `json`, and `fasta` are currently supported. For the `BAG` type, the values `csv`,`json`,`fasta`,`fetch` and `prefetch` are currently supported. See additional notes on destination format types.
| `params` | object | conditionally required | An object containing destination format-specific parameters.  Some destination formats (particularly those that require some kind of post-processing or data transformation), may require additional parameters  to be specified.


### Example 1
This example maps multiple single table queries to single FILE outputs using the FASTA format. 
```json
{
  "templates": [
    {
      "name": "orf",
      "format_name": "FASTA (ORF)",
      "format_type": "FILE",
      "outputs": [
        {
          "source": {
            "name": "gpcr_browser:construct_gui",
            "type": "attribute",
            "filter": "!orf::null::&!orf=%3F",
            "column_map": {
              "title": "title",
              "orf": "orf"
            }
          },
          "destination": {
            "name": "orf",
            "type": "fasta",
            "params": {
              "column_map": {
                "title":"comment",
                "orf":"data"
              }
            }
          }
        }
      ]
    },
    {
      "name": "protein",
      "format_name": "FASTA (Protein)",
      "format_type": "FILE",
      "outputs": [
        {
          "source": {
            "name": "gpcr_browser:construct_gui",
            "type": "attribute",
            "filter": "!receptor_protein_sequence::null::",
            "column_map": {
              "title": "title",
              "receptor_protein_sequence": "receptor_protein_sequence"
            }
          },
          "destination": {
            "name": "protein",
            "type": "fasta",
            "params": {
              "column_map": {
                "title":"comment",
                "receptor_protein_sequence":"data"
              }
            }
          }
        }
      ]
    },
    {
      "name": "nucleotide",
      "format_name": "FASTA (Nucleotide)",
      "format_type": "FILE",
      "outputs": [
        {
          "source": {
            "name": "gpcr_browser:construct_gui",
            "type": "attribute",
            "filter": "!exptnucseq::null::&!exptnucseq=NONE",
            "column_map": {
              "title": "title",
              "exptnucseq": "exptnucseq"
            }
          },
          "destination": {
            "name": "nucleotide",
            "type": "fasta",
            "params": {
              "column_map": {
                "title":"comment",
                "exptnucseq":"data"
              }
            }
          }
        }
      ]
    }
  ]
}
```
### Example 2
This example uses the same queries from Example 1, but instead packages the results in a Bag archive rather than as a set
 of individual files.
```json
{
  "templates": [
    {
      "name": "all_fasta",
      "format_name": "BAG (ALL FASTA)",
      "format_type": "BAG",
      "outputs": [
        {
          "source": {
            "name": "gpcr_browser:construct_gui",
            "type": "attribute",
            "filter": "!orf::null::&!orf=%3F",
            "column_map": {
              "title": "title",
              "orf": "orf"
            }
          },
          "destination": {
            "name": "orf",
            "type": "fasta",
            "params": {
              "column_map": {
                "title":"comment",
                "orf":"data"
              }
            }
          }
        },
        {
          "source": {
            "name": "gpcr_browser:construct_gui",
            "type": "attribute",
            "filter": "!receptor_protein_sequence::null::",
            "column_map": {
              "title": "title",
              "receptor_protein_sequence": "receptor_protein_sequence"
            }
          },
          "destination": {
            "name": "protein",
            "type": "fasta",
            "params": {
              "column_map": {
                "title":"comment",
                "receptor_protein_sequence":"data"
              }
            }
          }
        },
        {
          "source": {
            "name": "gpcr_browser:construct_gui",
            "type": "attribute",
            "filter": "!exptnucseq::null::&!exptnucseq=NONE",
            "column_map": {
              "title": "title",
              "exptnucseq": "exptnucseq"
            }
          },
          "destination": {
            "name": "nucleotide",
            "type": "fasta",
            "params": {
              "column_map": {
                "title":"comment",
                "exptnucseq":"data"
              }
            }
          }
        }
      ]
    }
  ]
}
```
### Example 3
This example shows how a Bag can be created with remote file references by using an attribute query to select a 
filtered set of file types and mapping columns from an image asset table, which can then be used to automatically create
 the bag's `fetch.txt`.
```json
{
  "templates": [
    {
      "name": "default",
      "format_name":"BAG",
      "format_type":"BAG",
      "outputs": [
        {
          "source": {
            "name": "pnc:metrics_v",
            "type": "entity"
          },
          "destination": {
            "name": "metrics",
            "type": "csv"
          }
        },
        {
          "source": {
            "name": "pnc:snp_v",
            "type": "entity"
          },
          "destination": {
            "name": "genotypes",
            "type": "csv"
          }
        },
        {
          "source": {
            "name": "pnc:subject_phenotypes_v",
            "type": "entity"
          },
          "destination": {
            "name": "phenotypes",
            "type": "csv"
          }
        },
        {
          "source": {
            "name": "pnc:image_files",
            "type": "attribute",
            "filter": "filename::ciregexp::0mm.mgh",
            "column_map": {
              "url": "uri",
              "length": "bytes",
              "filename": "filepath",
              "sha256": "sha256sum"
            }
          },
          "destination": {
            "name": "images",
            "type": "fetch"
          }
        }
      ]
    }
  ]
}
```