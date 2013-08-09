'''
Created on June 26, 2013

@author: Mohammad Faraji <ms.faraji@utoronto.ca>
'''

from keystone.common import sql
from keystone import exception
from keystone.openstack.common import timeutils
from keystone import delegate


class DelegateModel(sql.ModelBase, sql.DictBase):
    __tablename__ = 'delegate'
    attributes = ['id', 'delegator_user_id', 'delegatee_user_id',
                  'project_id', 'impersonation', 'expires_at']
    id = sql.Column(sql.String(64), primary_key=True)
    delegator_user_id = sql.Column(sql.String(64), unique=False, nullable=False,)
    delegatee_user_id = sql.Column(sql.String(64), unique=False, nullable=False)
    project_id = sql.Column(sql.String(64), unique=False, nullable=True)
    impersonation = sql.Column(sql.Boolean)
    deleted_at = sql.Column(sql.DateTime)
    expires_at = sql.Column(sql.DateTime)
    extra = sql.Column(sql.JsonBlob())


class DelegateRole(sql.ModelBase):
    __tablename__ = 'delegate_role'
    attributes = ['delegate_id', 'role_id']
    delegate_id = sql.Column(sql.String(64), primary_key=True, nullable=False)
    role_id = sql.Column(sql.String(64), primary_key=True, nullable=False)


class Delegate(sql.Base, delegate.Driver):
    @sql.handle_conflicts(type='delegate')
    def create_delegate(self, delegate_id, delegate, roles):
        session = self.get_session()
        with session.begin():
            ref = DelegateModel.from_dict(delegate)
            ref['id'] = delegate_id
            if ref.get('expires_at') and ref['expires_at'].tzinfo is not None:
                ref['expires_at'] = timeutils.normalize_time(ref['expires_at'])
            session.add(ref)
            added_roles = []
            for role in roles:
                delegate_role = DelegateRole()
                delegate_role.delegate_id = delegate_id
                delegate_role.role_id = role['id']
                added_roles.append({'id': role['id']})
                session.add(delegate_role)
            session.flush()
        delegate_dict = ref.to_dict()
        delegate_dict['roles'] = added_roles
        return delegate_dict

    def _add_roles(self, delegate_id, session, delegate_dict):
        roles = []
        for role in session.query(DelegateRole).filter_by(delegate_id=delegate_id):
            roles.append({'id': role.role_id})
        delegate_dict['roles'] = roles

    @sql.handle_conflicts(type='delegate')
    def get_delegate(self, delegate_id):
        session = self.get_session()
        ref = (session.query(DelegateModel).
               filter_by(deleted_at=None).
               filter_by(id=delegate_id).first())
        if ref is None:
            return None
        if ref.expires_at is not None:
            now = timeutils.utcnow()
            if now > ref.expires_at:
                return None
        delegate_dict = ref.to_dict()

        self._add_roles(delegate_id, session, delegate_dict)
        return delegate_dict

    @sql.handle_conflicts(type='delegate')
    def list_delegates(self):
        session = self.get_session()
        delegates = session.query(DelegateModel).filter_by(deleted_at=None)
        return [delegate_ref.to_dict() for delegate_ref in delegates]

    @sql.handle_conflicts(type='delegate')
    def list_delegates_for_delegatee(self, delegatee_user_id):
        session = self.get_session()
        delegates = (session.query(delegateModel).
                  filter_by(deleted_at=None).
                  filter_by(delegatee_user_id=delegatee_user_id))
        return [delegate_ref.to_dict() for delegate_ref in delegates]

    @sql.handle_conflicts(type='delegate')
    def list_delegates_for_delegators(self, delegator_user_id):
        session = self.get_session()
        delegates = (session.query(DelegateModel).
                  filter_by(deleted_at=None).
                  filter_by(delegator_user_id=delegator_user_id))
        return [delegate_ref.to_dict() for delegate_ref in delegates]

    @sql.handle_conflicts(type='delegate')
    def delete_delegate(self, delegate_id):
        session = self.get_session()
        with session.begin():
            delegate_ref = session.query(DelegategateModel).get(delegate_id)
            if not delegate_ref:
                raise exception.DelegateNotFound(delegate_id=delegate_id)
            delegate_ref.deleted_at = timeutils.utcnow()
            session.flush()
