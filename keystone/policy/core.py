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

"""Main entry point into the Policy service."""
import uuid

from keystone.common import manager
from keystone.common import wsgi
from keystone.common import controller
from keystone.common import logging
from keystone import config
from keystone import exception


CONF = config.CONF

LOG=logging.getLogger(__name__)

class Manager(manager.Manager):
    """Default pivot point for the Policy backend.

    See :mod:`keystone.common.manager.Manager` for more details on how this
    dynamically calls the backend.

    """

    def __init__(self):
        super(Manager, self).__init__(CONF.policy.driver)

    def get_policy(self, context, policy_id):
        try:
            return self.driver.get_policy(policy_id)
        except exception.NotFound:
            raise exception.PolicyNotFound(policy_id=policy_id)

    def update_policy(self, context, policy_id, policy):
        if 'id' in policy and policy_id != policy['id']:
            raise exception.ValidationError('Cannot change policy ID')
        try:
            return self.driver.update_policy(policy_id, policy)
        except exception.NotFound:
            raise exception.PolicyNotFound(policy_id=policy_id)

    def delete_policy(self, context, policy_id):
        try:
            return self.driver.delete_policy(policy_id)
        except exception.NotFound:
            raise exception.PolicyNotFound(policy_id=policy_id)


class Driver(object):
    def enforce(context, credentials, action, target):
        """Verify that a user is authorized to perform action.

        For more information on a full implementation of this see:
        `keystone.common.policy.enforce`.
        """
        raise exception.NotImplemented()

    def create_policy(self, policy_id, policy):
        """Store a policy blob for a particular endpoint.

        :raises: keystone.exception.EndpointNotFound,
                 keystone.exception.Conflict

        """
        raise exception.NotImplemented()

    def list_policies(self):
        """List all policies."""
        raise exception.NotImplemented()

    def get_policy(self, policy_id):
        """Retrieve a specific policy blob.

        :raises: keystone.exception.PolicyNotFound

        """
        raise exception.NotImplemented()

    def update_policy(self, policy_id, policy):
        """Update a policy blob.

        :raises: keystone.exception.PolicyNotFound,
                 keystone.exception.EndpointNotFound

        """
        raise exception.NotImplemented()

    def delete_policy(self, policy_id):
        """Remove a policy blob.

        :raises: keystone.exception.PolicyNotFound

        """
        raise exception.NotImplemented()


class PolicyControllerV3(controller.V3Controller):
    def create_policy(self, context, policy):
        self.assert_admin(context)

        ref = self._assign_unique_id(self._normalize_dict(policy))
        self._require_attribute(ref, 'blob')
        self._require_attribute(ref, 'type')
        self._require_attribute(ref, 'endpoint_id')

        self.catalog_api.get_endpoint(context, ref['endpoint_id'])

        ref = self.policy_api.create_policy(context, ref['id'], ref)
        return {'policy': ref}

    def list_policies(self, context):
        self.assert_admin(context)
        refs = self.policy_api.list_policies(context)
        refs = self._filter_by_attribute(context, refs, 'endpoint_id')
        refs = self._filter_by_attribute(context, refs, 'type')
        return {'policies': self._paginate(context, refs)}

    def get_policy(self, context, policy_id):
        self.assert_admin(context)
        ref = self.policy_api.get_policy(context, policy_id)
        return {'policy': ref}

    def update_policy(self, context, policy_id, policy):
        self.assert_admin(context)

        if 'endpoint_id' in policy:
            self.catalog_api.get_endpoint(context, policy['endpoint_id'])

        ref = self.policy_api.update_policy(context, policy_id, policy)
        return {'policy': ref}

    def delete_policy(self, context, policy_id):
        self.assert_admin(context)
        return self.policy_api.delete_policy(context, policy_id)

    def enforce(self,context, action, traget_object):
        raise exception.NotImplemented

class PolicyController(wsgi.Application):
    def __init__(self):
        self.poliy_api=Manager()
        super(PolicyController,self).__init__()

    def create_policy(self, context, policy):
        policy = self._normalize_dict(policy)
        self.assert_admin(context)
        if not 'endpoint_id' in policy or not policy['endpoint_id']:
            msg = "endpoint_id is required and can't be empty"
            raise exception.ValidationError(message=msg)
        if not 'blob' in policy or not policy['blob']:
            msg = "blob is required and can't be empty"
            raise exception.ValidationError(message=msg)
        if not 'type' in policy or not policy['type']:
            msg = "type is required and can't be empty"
            raise exception.ValidationError(message=msg)
        policy_id = uuid.uuid4().hex
        policy_ref=policy.copy()
        policy_ref['id']=policy_id
        new_policy=self.poliy_api.create_policy(
            context, policy_id, policy_ref)
        return {'policy': policy_ref}

    def list_policies(self, context,**kwargs):
        self.assert_admin(context)
        return {'policies': self.poliy_api.list_policies(context)}

    def get_policy(self, context, policy_id):
        self.assert_admin(context)
        return {'policy': self.poliy_api.get_policy(context,
                                              policy_id)}

    def update_policy(self, context, policy_id, policy):
        self.assert_admin(context)
        policy_ref = self.poliy_api.update_policy(context,
                                     policy_id, policy)

        return {'policy': policy_ref}

    def delete_policy(self, context, policy_id):
        self.assert_admin(context)
        self.poliy_api.delete_policy(context, policy_id)


