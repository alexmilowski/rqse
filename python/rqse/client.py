import sys
import logging
import json
from uuid import uuid4
import traceback
from threading import Event

import redis

LOGGER = logging.getLogger("rqse")

def encode_dictionary(parameters):
   redis_parameters = {}
   for key, value in parameters.items():
      redis_parameters[key] = json.dumps(value)

   return redis_parameters

def decode_dictionary(redis_parameters,as_json=True):
   parameters = {}
   for key, value in redis_parameters.items():
      parameters[key.decode('UTF-8')] = json.loads(value.decode('utf-8')) if as_json else value.decode('utf-8')
   return parameters

class EventClient:

   def __init__(self,key,host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      if key is None:
         raise ValueError('The key parameter can not be None')
      self._stream_key = key
      self._pool = pool if pool is not None else redis.ConnectionPool(host=host,port=port,username=username,password=password)

   @property
   def pool(self):
      return self._pool

   @property
   def connection(self):
      return redis.Redis(connection_pool=self.pool)

   def delete(self,id):
      # then we delete it for good
      self.connection.xdel(self._stream_key,id)

   def append(self,data):
      id = self.connection.xadd(self._stream_key,encode_dictionary(data))
      return id

   def __len__(self):
      return self.connection.xlen(self._stream_key)

   def delete_stream(self):
      return self.connection.delete(self._stream_key)

   def read(self,count=1):
      result = self.connection.xread({self._stream_key : '0'},count=count)
      if len(result)>0:
         for id, data in result[0][1]:
            event = decode_dictionary(data)
            yield id.decode('utf-8'), event

   def range(self,start='-',finish='+',count=1):
      result = self.connection.xrange(self._stream_key,start,finish,count)
      if len(result)>0:
         for id, data in result:
            event = decode_dictionary(data)
            yield id.decode('utf-8'), event

# TODO: We use a generic function here so that the method isn't exposed
def handle_event(self,id,event):
   if self.should_process(event):
      ok = self.process(id,event)
      if ok:
         self.acknowledge(id,event)
      else:
         logging.debug(f'Not acknowledging {id}')
   else:
      self.ignore(id,event)

class EventListener(EventClient):
   def __init__(self,key,group,host='0.0.0.0',port=6379,username=None,password=None,pool=None,select=[],select_attribute='kind',wait=10,pause=1,block=200,idle_count=5,backoff=10):
      super().__init__(key,host=host,port=port,username=username,password=password,pool=pool)
      if group is None:
         raise ValueError('The group parameter can not be None')
      self._group = group
      self._consumer = str(uuid4())
      self._select = select
      self._select_attribute = select_attribute
      self._wait = wait
      self._pause = pause
      self._block = block
      self._idle_count = idle_count
      self._backoff = backoff
      self._established = False
      self._exiting = Event()
      self._running = False

   @property
   def listening(self):
      return not self._exiting.is_set()

   def sleep(self,duration):
      self._exiting.wait(duration)

   @property
   def running(self):
      return self._running

   @property
   def established(self):
      return self._established

   @property
   def wait(self):
      return self._wait

   def process(self,id,event):
      return True

   def onStart(self):
      pass

   def onEstablished(self):
      pass

   def onStop(self):
      pass

   def establish_consumer(self):
      create_group = True

      # Check to see if the key exists and whether the consumer group
      # has been created.

      redis_client = self.connection

      if redis_client.exists(self._stream_key):
         groups = redis_client.xinfo_groups(self._stream_key)
         found = False
         for group in groups:
            if group['name'].decode('utf-8')==self._group:
               found = True
         create_group = not found

      # If the key does not exist or the group does not exist, create the
      # consumer group.
      if create_group:
         try:
            redis_client.xgroup_create(self._stream_key,self._group,id='0',mkstream=True)
         except redis.exceptions.ResponseError as ex:
            # BUSYGROUP means the consumer groupt was already created and so
            # another client beat us to it
            if not (len(ex.args)>0 and ex.args[0].startswith('BUSYGROUP')):
               raise ex

      return True

   def should_process(self,event):
      kind = event.get(self._select_attribute)
      return True if len(self._select)==0 or kind in self._select else False

   def ignore(self,id,event):
      # we just acknowledge the event
      kind = event.get(self._select_attribute)
      LOGGER.debug(f'Ignoring {id} {kind}')
      self.connection.xack(self._stream_key,self._group,id)

   def acknowledge(self,id,event):
      # we acknowledge the event
      kind = event.get(self._select_attribute)
      LOGGER.debug(f'Acknowledging {id} {kind}')
      self.connection.xack(self._stream_key,self._group,id)

   def find_pending(self,count=100):
      has_pending = True
      while has_pending and self.listening:
         pending = self.connection.xpending_range(self._stream_key,self._group,idle=60*1000,min='-',max='+',count=count)
         has_pending = len(pending)>0
         for message in pending:
            claimed = self.connection.xclaim(self._stream_key,self._group,self._consumer,60*1000,[message['message_id'].decode('utf-8')])
            if len(claimed)==0 or claimed[0][0] is None:
               continue
            id, redis_event = claimed[0]
            id = id.decode('utf-8')
            event = decode_dictionary(redis_event)
            kind = event.get(self._select_attribute)
            LOGGER.info(f'Claimed pending {id} {kind}')

            handle_event(self,id,event)

   def groupread(self,count=1,block=-1):
      # read a messsage blocking for the wait period of time
      result = self.connection.xreadgroup(self._group,self._consumer,{self._stream_key : '>'},count=count,block=self._wait*1000 if block<0 else block)
      if len(result)>0:
         for id, data in result[0][1]:
            event = decode_dictionary(data)
            yield id.decode('utf-8'), event

   def stop(self):
      self._exiting.set()

   def listen(self):

      self._running = True
      self._exiting = Event()

      self.onStart()

      self._established = False

      count = 0
      idle = 0
      while self.listening:

         if count >= self._idle_count:
            delay = self._pause + (idle % self._backoff)*self._pause
            self.sleep(delay)
            if idle>0 and idle % self._backoff == 0:
               idle -= int(self._backoff/2)
            idle += 1
            count = 0

         while not self._established and self.listening:
            try:
               self.establish_consumer()
               self._established = True
               self.onEstablished()
            except Exception as ex:
               traceback.print_exc(file=sys.stderr)
               self.sleep(self._wait)

         if self._established:
            try:
               self.find_pending()

               start_count = count
               for id, event in self.groupread(block=self._block):
                  count = 0
                  idle = 0
                  handle_event(self,id,event)
               if start_count==count:
                  count += 1

            except Exception as ex:
               traceback.print_exc(file=sys.stderr)
               # Note: The key could have been deleted. Setting this
               # to false will enable resetting the consumer
               self._established = False
               self.sleep(self._wait)

      self._running = False
      self.onStop()
