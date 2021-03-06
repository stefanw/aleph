from aleph.model import Entity
from aleph.index import TYPE_RECORD
from aleph.search.fragments import text_query_string
from aleph.search.util import execute_basic


def records_query(document_id, args, size=5, snippet_size=100):
    shoulds = []
    text = args.get('q', '').strip()
    if len(text):
        shoulds.append(text_query_string(text))

    entities = Entity.by_id_set(args.getlist('entity'))
    for entity in entities.values():
        for term in entity.terms:
            shoulds.append({
                'multi_match': {
                    'query': term,
                    'type': "best_fields",
                    'fields': ['text^5', 'text_latin'],
                    'operator': 'AND'
                }
            })

    if not len(shoulds):
        return None

    q = {
        'bool': {
            'minimum_should_match': 1,
            'should': shoulds
        }
    }
    if document_id is not None:
        q['bool']['must'] = {
            'term': {'document_id': document_id}
        }

    try:
        snippet_size = int(args.get('snippet', snippet_size))
    except:
        pass

    return {
        'size': size,
        'query': q,
        'highlight': {
            'fields': {
                'text': {
                    'fragment_size': snippet_size,
                    'number_of_fragments': 1
                },
                'text_latin': {
                    'fragment_size': snippet_size,
                    'number_of_fragments': 1
                }
            }
        },
        '_source': ['document_id', 'sheet', 'row_id', 'page']
    }


def execute_records_query(query):
    """Execute a query against records and return a set of results."""
    result, hits, output = execute_basic(TYPE_RECORD, query)
    for rec in hits.get('hits', []):
        record = rec.get('_source')
        record['score'] = rec.get('_score')
        record['text'] = rec.get('highlight', {}).get('text')
        output['results'].append(record)
    return output
