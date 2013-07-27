# vim: tabstop=4 shiftwidth=4 softtabstop=4


"""Main entry point into the Delegate service."""
from keystone.common import dependency
from keystone.common import logging
from keystone.common import manager
from keystone import config
from keystone import exception


CONF = config.CONF

LOG = logging.getLogger(__name__)


@dependency.provider('delegate_api')
class Manager(manager.Manager):

    def __init__(self):
        super(Manager, self).__init__(CONF.delegate.driver)


class Driver(object):
    def create_delegate(self, delegate_id, delegate, roles):
        raise exception.NotImplemented()

    def get_delegate(self, delegate_id):
        raise exception.NotImplemented()

    def list_delegates(self):
        raise exception.NotImplemented()

    def list_delegates_for_delegatee(self, delegatee):
        raise exception.NotImplemented()

    def list_delegates_for_delegator(self, delegator):
        raise exception.NotImplemented()