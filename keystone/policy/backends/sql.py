'''
Created on Oct 9, 2012

@author: Mohammad Faraji <ms.faraji@utoronto.ca>
'''

import functools
import sqlalchemy

from keystone.common import sql
from keystone.common.sql import migration
from keystone import exception
from keystone.policy.backends import rules

def handle_conflicts(type='object'):

    def decorator(method):
        @functools.wraps(method)
        def wrapper(*args,**kwargs):
            try:
                method(*args,**kwargs)
            except sql.IntegrityError as e:
                raise exception.Conflict(type=type, details=str(e))
        return wrapper
    return decorator

class PolicyModel(sql.ModelBase, sql.DictBase):
    __tablename__='policy'
    id = sql.Column(sql.String(64),primary_key=True)
    endpoint_id = sql.Column(sql.String(64), nullable=False)
    blob = sql.Column(sql.JsonBlob(),nullable=False)
    type = sql.Column(sql.String(255), nullable=False)
    extra = sql.Column(sql.JsonBlob())
    attributes =['id','endpoint_id','blob', 'type']

class Policy(sql.Base, rules.Policy):
    def sync_db(self):
        migration.db_sync()

    @handle_conflicts(type='policy')
    def create_policy(self, policy_id, policy):
        session = self.get_session()
        with session.begin():
            policy_ref = PolicyModel.from_dict(policy)
            session.add(policy_ref)
            session.flush()
        return policy_ref.to_dict()

    def list_policies(self):
        session = self.get_session()
        refs = session.query(PolicyModel).all()
        return [ref.to_dict() for ref in refs]

    def get_policy(self, policy_id):
        session =self.get_session()
        try:
            policy_ref = session.query(PolicyModel).filter_by(id=policy_id).first()
        except sqlalchemy.orm.exc.NoResultFound:
            raise exception.PolicyNotFound(policy_id=policy_id)
        return policy_ref.to_dict()

    @handle_conflicts(type='policy')
    def update_policy(self, policy_id, policy):
        session =self.get_session()
        try:
            ref = session.query(PolicyModel).filter_by(id=policy_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise exception.PolicyNotFound(policy_id=policy_id)
        former = ref.to_dict()
        former.update(policy)
        new = PolicyModel.from_dict(former)
        ref.endpoit_id = new.endpoint_id
        ref.type = new.type
        ref.blob = new.blob
        ref.extra = new.extra
        session.flush()
        return ref.to_dict()
