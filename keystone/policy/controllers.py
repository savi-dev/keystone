# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import uuid

from keystone.common import controller
from keystone import exception
from keystone.common import logging

LOG = logging.getLogger(__name__)
class Policy(controller.V2Controller):

    def create_policy(self, context, policy):
        policy = self._normalize_dict(policy)
        self.assert_admin(context)
        if not 'blob' in policy or not policy['blob']:
            msg = 'blob field is required and cannot be empty'
            raise exception.ValidationError(message=msg)
        if not 'type' in policy or not policy['type']:
            msg = 'type field is required and cannot be empty'
            raise exception.ValidationError(message=msg)
        if not 'role_id' in policy or not policy['role_id']:
            msg = 'role-id field is required and cannot be empty'
            raise exception.ValidationError(message=msg)
        policy_id = uuid.uuid4().hex
        policy_ref = policy.copy()
        policy_ref['id'] = policy_id

        ref = self.policy_api.create_policy(context, policy_ref['id'], policy_ref)
        return {'policy':ref}

    def get_policy(self,context, policy_id):
        self.assert_admin(context)
        ref = self.policy_api.get_policy(context, policy_id)
        return {'policy':ref}

    def get_role_policy(self, context, role_id):
        self.assert_admin(context)
        ref = self.policy_api.get_role_policy(context, role_id)
        return {'policies':ref}

    def list_policies(self, context):
         if 'name' in context['query_string']:
            return self.get_user_by_name(
                context, context['query_string'].get('name'))
         self.assert_admin(context)
         refs = self.policy_api.list_policies(context)
         return {'policies':refs}

    def update_policy(self, context, policy_id, policy):
        self.assert_admin(context)
        ref = self.policy_api.update_policy(context, policy_id, policy)
        return {'policy': ref}

    def delete_policy(self, context, policy_id):
        self.assert_admin(context)
        return self.policy_api.delete_policy(context, policy_id)


class PolicyV3(controller.V3Controller):
    @controller.protected
    def create_policy(self, context, policy):
        ref = self._assign_unique_id(self._normalize_dict(policy))
        self._require_attribute(ref, 'blob')
        self._require_attribute(ref, 'type')

        ref = self.policy_api.create_policy(context, ref['id'], ref)
        return {'policy': ref}

    @controller.protected
    def list_policies(self, context):
        refs = self.policy_api.list_policies(context)
        refs = self._filter_by_attribute(context, refs, 'type')
        return {'policies': self._paginate(context, refs)}

    @controller.protected
    def get_policy(self, context, policy_id):
        ref = self.policy_api.get_policy(context, policy_id)
        return {'policy': ref}

    @controller.protected
    def update_policy(self, context, policy_id, policy):
        ref = self.policy_api.update_policy(context, policy_id, policy)
        return {'policy': ref}

    @controller.protected
    def delete_policy(self, context, policy_id):
        return self.policy_api.delete_policy(context, policy_id)
