from hashlib import sha1
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB
from werkzeug.datastructures import MultiDict

from aleph.core import db
from aleph.model.entity import Entity
from aleph.model.validation import validate
from aleph.model.common import SoftDeleteModel


def extract_query(q):
    """Remove parts of the query which do not affect the result set."""
    q = MultiDict(q)
    cleaned = MultiDict()
    for key in q.keys():
        values = q.getlist(key)
        if key == 'q':
            values = [v.strip() for v in values]
        if key.startswith('filter:') or key in ['entity', 'q']:
            for val in values:
                if not isinstance(val, (list, tuple, set)):
                    val = [val]
                for v in val:
                    if v is None:
                        continue
                    v = unicode(v).lower()
                    if len(v):
                        cleaned.add(key, v)
    return cleaned


def query_signature(q):
    """Generate a SHA1 signature for the given query."""
    q = extract_query(q)
    out = sha1()
    for field in q.keys():
        out.update('::' + field.encode('utf-8'))
        for value in set(sorted(q.getlist(field))):
            out.update('==' + value.encode('utf-8'))
    return out.hexdigest()


class Alert(db.Model, SoftDeleteModel):
    """A subscription to notifications on a given query."""

    __tablename__ = 'alert'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), index=True)
    custom_label = db.Column(db.Unicode, nullable=True)
    signature = db.Column(db.Unicode)
    query = db.Column(JSONB)
    notified_at = db.Column(db.DateTime, nullable=True)

    @property
    def label(self):
        if self.custom_label is not None:
            return self.custom_label
        # This is weird. Should live somewhere else.
        fragments = []
        q = self.query.get('q')
        if q and len(q):
            fragments.append('matching "%s"' % ''.join(q))
        entities = self.query.get('entity')
        if entities and len(entities):
            try:
                entities = Entity.by_id_set(entities)
                sub_fragments = []
                for entity in entities.values():
                    sub_fragments.append('"%s"' % entity.name)
                fragment = ' and '.join(sub_fragments)
                fragments.append('mentioning %s' % fragment)
            except:
                pass
        for key in self.query.keys():
            try:
                if not key.startswith('filter:'):
                    continue
                _, field = key.split(':', 1)
                # TODO: source_id special handling?
                field = field.replace('_', ' ')
                value = '; '.join(self.query.get(key))
                fragments.append('filtered by %s: %s' % (field, value))
            except:
                pass
        if not len(fragments):
            return 'Everything'
        return 'Results %s' % ', '.join(fragments)

    def delete(self):
        self.deleted_at = datetime.utcnow()
        db.session.add(self)
        db.session.flush()

    def update(self):
        self.notified_at = datetime.utcnow()
        db.session.add(self)
        db.session.flush()

    @classmethod
    def by_id(cls, id, role=None):
        q = cls.all().filter_by(id=id)
        if role is not None:
            q = q.filter(cls.role_id == role.id)
        return q.first()

    @classmethod
    def by_role(cls, role):
        return cls.all().filter(cls.role_id == role.id)

    @classmethod
    def create(cls, data, role):
        validate(data, 'alert.json#')
        alert = cls()
        alert.role_id = role.id
        q = extract_query(data.get('query'))
        alert.query = {k: q.getlist(k) for k in q.keys()}
        alert.signature = query_signature(q)
        alert.custom_label = data.get('custom_label')
        alert.update()
        return alert

    @classmethod
    def exists(cls, query, role):
        q = cls.all_ids().filter(cls.role_id == role.id)
        q = q.filter(cls.signature == query_signature(query))
        return q.scalar()

    def __repr__(self):
        return '<Alert(%r, %r)>' % (self.id, self.query)

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'custom_label': self.custom_label,
            'signature': self.signature,
            'role_id': self.role_id,
            'notified_at': self.notified_at,
            'query': self.query,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
