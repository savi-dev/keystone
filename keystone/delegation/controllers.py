# vim: tabstop=4 shiftwidth=4 softtabstop=4

import datetime

from keystone.common import controller
from keystone import exception
from keystone.common import logging
from keystone.common import dependency


LOG = logging.getLogger(__name__)

@dependency.requires('identity_api', 'delegation_api', 'token_api')
class Delegation(controller.V2Controller):

    def create_delegate(self, context, delegate=None):
        """
        Create a new delegation.
        The user creating the delegation must be the delegator.
        """
        if not delegate:
            raise exception.ValidationError(attribute='delegate',
                                            target='request')
        try:
            user_id = self._get_user_id(context)
            _delegator_only(context, delegate, user_id)
            delegatee_ref = self.identity_api.get_user(delegate['delegatee_user_id'])
            if not delegatee_ref:
                raise exception.UserNotFound(user_id=delegate['delegatee_user_id'])
            global_roles = self.identity_api.list_roles()
            clean_roles = self._clean_role_list(context, delegate, global_roles)
            if delegate.get('project_id'):
                user_roles = self.identity_api.get_roles_for_user_and_project(
                    user_id, delegate['project_id'])
            else:
                user_roles = []
            for delegate_role in clean_roles:
                matching_roles = [x for x in user_roles
                                  if x == delegate_role['id']]
                if not matching_roles:
                    raise exception.RoleNotFound(role_id=delegate_role['id'])
            if delegate.get('expires_at') is not None:
                if not delegate['expires_at'].endswith('Z'):
                    delegate['expires_at'] += 'Z'
                delegate['expires_at'] = (timeutils.parse_isotime
                                       (delegate['expires_at']))
            new_delegate = self.delegate_api.create_delegate(
                delegate_id=uuid.uuid4().hex,
                delegate=delegate,
                roles=clean_roles)
            self._fill_in_roles(context,
                                new_delegate,
                                global_roles)
            return {'delegate':new_delegate}
        except KeyError as e:
            raise exception.ValidationError(attribute=e.args[0],
                                            target='delegate')
            
    def _get_user_id(self, context):
        if 'token_id' in context:
            token_id = context['token_id']
            token = self.token_api.get_token(token_id)
            user_id = token['user']['id']
            return user_id
        return None

    def get_delegate(self, context, delegate_id):
        user_id = self._get_user_id(context)
        delegate = self.delegate_api.get_delegate(delegateate_id)
        if not delegate:
            raise exception.DelegateNotFound(delegate_id)
        _admin_delegator_delegatee_only(context, delegate, user_id)
        if not delegate:
            raise exception.DelegateNotFound(delegate_id=delegate_id)
        if (user_id != delegate['delegator_user_id'] and
                user_id != delegate['delegatee_user_id']):
            raise exception.Forbidden()
        self._fill_in_roles(context, delegate,
                            self.identity_api.list_roles())
        return {'delegate': delegate}
    
    def _fill_in_roles(self, context, delegate, global_roles):
        if delegate.get('expires_at') is not None:
            delegate['expires_at'] = (timeutils.isotime
                                   (delegate['expires_at'],
                                    subsecond=True))

        if 'roles' not in delegate:
            delegate['roles'] = []
        delegate_full_roles = []
        for delegate_role in delegate['roles']:
            if isinstance(delegate_role, basestring):
                delegate_role = {'id': delegate_role}
            matching_roles = [x for x in global_roles
                              if x['id'] == delegate_role['id']]
            if matching_roles:
                full_role = identity.controllers.RoleV3.wrap_member(
                    context, matching_roles[0])['role']
                delegate_full_roles.append(full_role)
        delegate['roles'] = delegate_full_roles
        delegate['roles_links'] = {
            'self': (CONF.public_endpoint % CONF +
                     "delegates/%s/roles" % delegate['id']),
            'next': None,
            'previous': None}

    def _clean_role_list(self, context, delegate, global_roles):
        delegate_roles = []
        global_role_names = dict((r['name'], r)
                                 for r in
                                 global_roles)
        for role in delegate.get('roles', []):
            if 'id' in role:
                delegate_roles.append({'id': role['id']})
            elif 'name' in role:
                rolename = role['name']
                if rolename in global_role_names:
                    delegate_roles.append({'id':
                                        global_role_names[rolename]['id']})
                else:
                    raise exception.RoleNotFound("role %s is not defined" %
                                                 rolename)
            else:
                raise exception.ValidationError(attribute='id or name',
                                                target='roles')
        return delegate_roles

    def list_delegates(self, context):
        query = context['query_string']
        delegates = []
        if not query:
            self.assert_admin(context)
            delegates += self.delegate_api.list_delegates()
        if 'delegator_user_id' in query:
            user_id = query['delegator_user_id']
            calling_user_id = self._get_user_id(context)
            if user_id != calling_user_id:
                raise exception.Forbidden()
            delegates += (self.delegate_api.
                       list_delegates_for_delegator(user_id))
        if 'delegatee_user_id' in query:
            user_id = query['delegatee_user_id']
            calling_user_id = self._get_user_id(context)
            if user_id != calling_user_id:
                raise exception.Forbidden()
            delegates += self.delegate_api.list_delegates_for_delegatee(user_id)
        global_roles = self.identity_api.list_roles()
        for delegate in delegates:
            self._fill_in_roles(context, delegate, global_roles)
        return {'delegates':delegates}

    def delete_delegate(self, context, delegate_id):
        delegate = self.delegate_api.get_delegate(delegate_id)
        if not delegate:
            raise exception.DelegateNotFound(delegate_id)

        user_id = self._get_user_id(context)
        _admin_delegator_only(context, delegate, user_id)
        self.delegate_api.delete_delegate(delegate_id)
        userid = delegate['delegator_user_id']
        token_list = self.token_api.list_tokens(userid, delegate_id=delegate_id)
        for token in token_list:
            self.token_api.delete_token(token)

    def list_roles_for_delegate(self, context, delegate_id):
        delegate = self.get_delegate(context, delegate_id)['delegate']
        if not delegate:
            raise exception.DelegateNotFound(delegate_id)
        user_id = self._get_user_id(context)
        _admin_delegator_delegatee_only(context, delegate, user_id)
        return {'roles': delegate['roles'],
                'links': delegate['roles_links']}
        
    def check_role_for_delegate(self, context, delegate_id, role_id):
        """Checks if a role has been assigned to a delegate."""
        delegate = self.delegate_api.get_delegate(delegate_id)
        if not delegate:
            raise exception.DelegateNotFound(delegate_id)
        user_id = self._get_user_id(context)
        _admin_delegator_delegatee_only(context, delegate, user_id)
        matching_roles = [x for x in delegate['roles']
                          if x['id'] == role_id]
        if not matching_roles:
            raise exception.RoleNotFound(role_id=role_id)
        
    def get_role_for_delegate(self, context, delegate_id, role_id):
        """Checks if a role has been assigned to a delegate."""
        delegate = self.delegate_api.get_delegate(delegate_id)
        if not delegate:
            raise exception.DelegateNotFound(delegate_id)

        user_id = self._get_user_id(context)
        _admin_delegator_delegatee_only(context, delegate, user_id)
        matching_roles = [x for x in delegate['roles']
                          if x['id'] == role_id]
        if not matching_roles:
            raise exception.RoleNotFound(role_id=role_id)
        global_roles = self.identity_api.list_roles()
        matching_roles = [x for x in global_roles
                          if x['id'] == role_id]
        if matching_roles:
            full_role = {'roles': matching_roles[0]}
            return full_role
        else:
            raise exception.RoleNotFound(role_id=role_id)


def _delegator_only(context, delegate, user_id):
    if user_id != delegate.get('delegator_user_id'):
        raise exception.Forbidden()
    
    
def _admin_delegator_delegatee_only(context, delegate, user_id):
    if (user_id != delegate.get('delegator_user_id') and
            user_id != delegate.get('delegotor_user_id') and
            context['is_admin']):
                raise exception.Forbidden()


def _admin_delegator_only(context, delegate, user_id):
    if user_id != delegate.get('delegator_user_id') and not context['is_admin']:
        raise exception.Forbidden()