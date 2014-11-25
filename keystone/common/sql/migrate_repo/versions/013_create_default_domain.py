# Copyright 2012 OpenStack Foundation
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

import json

import six

import sqlalchemy as sql
from sqlalchemy import orm

from keystone import config


CONF = config.CONF
DISABLED_VALUES = ['false', 'disabled', 'no', '0']


def is_enabled(enabled):
    # no explicit value means enabled
    if enabled is True or enabled is None:
        return True
    if (isinstance(enabled, six.string_types)
            and enabled.lower() in DISABLED_VALUES):
        return False
    return bool(enabled)


def upgrade_tenant_table(meta, migrate_engine, session):
    tenant_table = sql.Table('tenant', meta, autoload=True)
    for tenant in session.query(tenant_table):
        extra = json.loads(tenant.extra)
        values = {'description': extra.pop('description', None),
                  'enabled': is_enabled(extra.pop('enabled', True)),
                  'extra': json.dumps(extra)}
        update = tenant_table.update().\
            where(tenant_table.c.id == tenant.id).\
            values(values)
        migrate_engine.execute(update)


def downgrade_tenant_table(meta, migrate_engine, session):
    tenant_table = sql.Table('tenant', meta, autoload=True)
    for tenant in session.query(tenant_table).all():
        extra = json.loads(tenant.extra)
        extra['description'] = tenant.description
        extra['enabled'] = '%r' % is_enabled(tenant.enabled)
        values = {'extra': json.dumps(extra)}
        update = tenant_table.update().\
            where(tenant_table.c.id == tenant.id).\
            values(values)
        migrate_engine.execute(update)


def upgrade(migrate_engine):
    """Creates the default domain."""
    meta = sql.MetaData()
    meta.bind = migrate_engine
    session = orm.sessionmaker(bind=migrate_engine)()

    upgrade_tenant_table(meta, migrate_engine, session)
    domain_table = sql.Table('domain', meta, autoload=True)
    domain_table.create_column(
        sql.Column('enabled',
                   sql.Boolean,
                   nullable=False,
                   default=True))

    domain = {
        'id': CONF.identity.default_domain_id,
        'name': 'Default',
        'enabled': True,
        'extra': json.dumps({
            'description': 'Owns users and tenants (i.e. projects) available '
                           'on Identity API v2.'})}

    insert = domain_table.insert()
    insert.execute(domain)
    session.commit()


def downgrade(migrate_engine):
    """Delete the default domain."""
    meta = sql.MetaData()
    meta.bind = migrate_engine
    session = orm.sessionmaker(bind=migrate_engine)()

    downgrade_tenant_table(meta, migrate_engine, session)
    domain_table = sql.Table('domain', meta, autoload=True)
    domain_table.drop_column(
        sql.Column('enabled',
                   sql.Boolean,
                   nullable=False,
                   default=True))

    session.execute(
        'DELETE FROM domain WHERE id=:id',
        {'id': CONF.identity.default_domain_id})
    session.commit()
