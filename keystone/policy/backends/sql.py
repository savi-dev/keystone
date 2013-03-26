import functools

from keystone.common import sql
from keystone.common.sql import migration
from keystone import exception
from keystone.policy.backends import rules
from keystone.common import logging

LOG = logging.getLogger(__name__)


def handle_conflicts(type='object'):
    """Converts IntegrityError into HTTP 409 Conflict."""
    def decorator(method):
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except sql.IntegrityError as e:
                raise exception.Conflict(type=type, details=str(e))
        return wrapper
    return decorator


class PolicyModel(sql.ModelBase, sql.DictBase):
    __tablename__ = 'policy'
    attributes = ['id', 'blob', 'type','service_id','timestamp']
    id = sql.Column(sql.String(64), primary_key=True)
    blob = sql.Column(sql.JsonBlob(), nullable=False)
    type = sql.Column(sql.String(255), nullable=False)
    service_id = sql.Column(sql.String(64),
                            sql.ForeignKey('service.id'),
                            nullable=False)
    timestamp = sql.Column(sql.DateTime())
    extra = sql.Column(sql.JsonBlob())


class Policy(sql.Base, rules.Policy):
    # Internal interface to manage the database
    def db_sync(self):
        migration.db_sync()

    @handle_conflicts(type='policy')
    def create_policy(self, policy_id, policy):
        session = self.get_session()

        with session.begin():
            ref = PolicyModel.from_dict(policy)
            session.add(ref)
            session.flush()

        return ref.to_dict()

    def list_policies(self):
        session = self.get_session()

        refs = session.query(PolicyModel).all()
        return [ref.to_dict() for ref in refs]

    def _get_policy(self, session, policy_id):
        """Private method to get a policy model object (NOT a dictionary)."""
        try:
            return session.query(PolicyModel).filter_by(id=policy_id).one()
        except sql.NotFound:
            raise exception.PolicyNotFound(policy_id=policy_id)

    def get_policy(self, policy_id):
        session = self.get_session()

        return self._get_policy(session, policy_id).to_dict()

    def get_service_policy(self, service_id):
        session = self.get_session()

        try:
            return session.query(PolicyModel).filter_by(service_id=service_id).first()
        except sql.NotFound:
            None

    @handle_conflicts(type='policy')
    def update_policy(self, policy_id, policy):
        session = self.get_session()

        with session.begin():
            ref = self._get_policy(session, policy_id)
            old_dict = ref.to_dict()
            old_dict.update(policy)
            new_policy = PolicyModel.from_dict(old_dict)
            ref.blob = new_policy.blob
            ref.type = new_policy.type
            ref.extra = new_policy.extra
            session.flush()

        return ref.to_dict()

    def delete_policy(self, policy_id):
        session = self.get_session()

        with session.begin():
            ref = self._get_policy(session, policy_id)
            session.delete(ref)
            session.flush()

