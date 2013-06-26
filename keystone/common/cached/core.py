import functools

from keystone import config
from keystone import exception
from keystone.common import logging
from keystone.openstack.common import timeutils

CONF = config.CONF
LOG = logging.getLogger(__name__)

def get_client(memcached_servers=None):
    client_cls = None
    if not memcached_servers:
        memcached_servers = CONF.memcached.memcached_server
    if memcached_servers:
        try:
            import memcache
            client_cls = memcache.Client
        except ImportError:
            pass
    return client_cls([memcached_servers], debug=0)


class KVSClient(object):

    def __init__(self, *args, **kwargs):
        self.cache = {}

    def get(self, key):
        now = timeutils.utcnow_ts()
        for k in self.cache.keys():
            (timeout, _value) = self.cache[k]
            if timeout and now >= timeout:
                del self.cache[k]
        return self.cache.get(key, (0, None))[1]

    def set(self, key, value, time=0, min_compress_len=0):
        timeout = 0
        if time != 0:
            timeout = timeutils.utcnow_ts() + time
        self.cache[key] = (timeout, value)
        return True

    def add(self, key, value, time=0, min_compress_len=0):
        if self.get(key) is not None:
            return False
        return self.set(key, value, time, min_compress_len)

    def incr(self, key, delta=1):
        value = self.get(key)
        if value is None:
            return None
        new_value = int(value) + delta
        self.cache[key] = (self.cache[key][0], str(new_value))
        return new_value

    def delete(self, key, time=0):
        if key in self.cache:
            del self.cache[key]

class CacheRouter(object):
    revocation_key = 'revocation'

    def __init__(self, client=None):
        self._memcache_client = client

    @property
    def client(self):
       return self._memcache_client or get_client()


    def __call__(self, key, prefix=None):
       def decorator(f):
           @functools.wraps(f)
           def wrapper(*args, **kwargs):
               try:
                  key_id = kwargs[key]
               except KeyError:
                  msg =  _('There is no argument %s in function %s' % (key,f.__name__))
                  raise exception.UnexpectedError(msg)
               if self.client:
                  resp = self.client.get(self._prefix_id(prefix, key_id))
                  if not resp:
                     resp = f(*args,**kwargs)
                     if resp is None:
                        self.client.set(self._prefix_id(prefix, key_id),none_value)
                        self._add_revocation_items(prefix, key_id)
                     else:
                         self.client.set(self._prefix_id(prefix, key_id),resp)
                         self._add_revocation_items(prefix, key_id)
                  if resp.__class__ is none_value:
                     return None
               else:
                  resp = f(*args,**kwargs)
               return resp
           return wrapper
       return decorator

    def _prefix_id(self, prefix, key):
        return '%s-%s' % (prefix, key.encode('utf-8'))

    def _add_revocation_items(self, prefix, key):
      if not self.client.append(self._get_revocation_key(prefix), ',%s' % key):
         if not self.client.add(self._get_revocation_key(prefix), key):
            if not self.client.append(self._get_revocation_key(prefix), key):
               msg = _('Unable to add token to revocation list.')
               raise exception.UnexpectedError(msg)

    def _get_revocation_key(self, prefix):
        return "%s_%s" % (self.revocation_key,prefix)
  
    def revokeAll(self, prefix):
       def decorator(f):
           @functools.wraps(f)
           def wrapper(*args, **kwargs):
               revocation_list =  self.client.get(self._get_revocation_key(prefix))
               if revocation_list is not None:
                  keys = revocation_list.split(',')
                  for key in keys:
                      self.client.delete(self._prefix_id(prefix,key))

               return f(*args, **kwargs)

           return wrapper
       return decorator


class none_value:
    """
      Stub class for storing None values in memcache to
      distinguish between None values and not-found
      entries.
    """
    pass


cache=CacheRouter()
