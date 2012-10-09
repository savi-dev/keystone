'''
Created on Oct 9, 2012

@author: Mohammad Faraji <ms.faraji@utoronto.ca>
'''

from migrate import *
from sqlalchemy import *

from keystone.common import sql

import keystone.policy.backends.sql

def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    sql.ModelBase.metadata.create_all(migrate_engine)


def downgrade(migrate_engine):
    pass