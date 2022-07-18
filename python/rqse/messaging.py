import logging
from datetime import datetime, timezone

from .client import EventListener, decode_dictionary

LOGGER = logging.getLogger("rqse")

def message(data=None,kind=None,api_version='v1',at=None,response_for=None):
   if data is None:
      data = {}
   if kind is not None and 'kind' not in data:
      data['kind'] = kind
   if 'apiVersion' not in data:
      data['apiVersion'] = api_version
   if at is None and 'at' not in data:
      at = datetime.now(timezone.utc)
   if 'at' not in data:
      data['at'] = at.isoformat()
   if response_for is not None and 'for' not in data:
      data['for'] = response_for
   return data

def receipt_for(id,action='processed',target=None):
   data = {'for':id,'action':action}
   if target is not None:
      data['target'] = target
   return message(kind='receipt',data=data)

class ReceiptListener(EventListener):
   def __init__(self,key,logger=None,host='0.0.0.0',port=6379,username=None,password=None,pool=None,wait=10):
      super().__init__(key,'__receipt__',host=host,port=port,username=username,password=password,pool=pool,select=['receipt'],wait=wait)
      self._logger = logger
      self._deferred = []

   @property
   def logger(self):
      return self._logger

   @logger.setter
   def logger(self,value):
      self._logger = value

   def process(self,receipt_id,event):

      # A true value return will delete the receipt and target on acknowledgement

      if self._logger is None:
         return True;

      receipt_for = event.get('for')
      if receipt_for is not None:
         items = self.connection.xrange(self._stream_key,min=receipt_for,max=receipt_for,count=1)
         if len(items)>0:
            redis_event = items[0][1]
            # convert the key/values back into a dictionary
            target_event = decode_dictionary(redis_event)
            try:
               result = self._logger.log(self.connection,receipt_id,event,receipt_for,target_event)
               # A boolean result means the logger immediately accepted or rejected the receipt
               if type(result)==bool:
                  # A true value means will cause the receipt and target to get deleted on acknowledgement
                  return result

               if result<0:
                  # failed to log
                  return False
               elif result==0:
                  # deferred logging, cache the receipt
                  self._deferred.append((receipt_id,receipt_for))
                  return False
               else:
                  # committed the deferred logs, commit the log receipts
                  self._deferred.append((receipt_id,receipt_for))
                  self.commit()
            except Exception as err:
               LOGGER.exception(f'Logging message {receipt_id} failed.')

      return True

   def commit(self):
      to_process = self._logger.commit(self.client,self._deferred)
      last_processed = -1
      for index, value in enumerate(self._deferred[:to_process]):
         msg_id, target_id = value
         try:
            self.delete_receipt(msg_id,target_id)
            last_processed = index
         except Exception as ex:
            LOGGER.exception(f'Deleting message {msg_id} and target {target_id} failed.')
      self._deferred = self._deferred[last_processed+1:]

   def onStop(self):
      if self._logger is not None and len(self._deferred)>0:
         self.commit()
         if len(self._deferred)>0:
            LOGGER.error(f'Unable to commit all the deferred messages, {len(self._deferred)} remaining undeleted.')

   def delete_receipt(self,receipt_id,target_id):
      if target_id is not None:
         LOGGER.info(f'Deleting {target_id} on receipt {receipt_id}')
         self.delete(target_id)
      LOGGER.info(f'Deleting {receipt_id}')
      self.delete(receipt_id)

   def acknowledge(self,id,event):

      super().acknowledge(id,event)

      receipt_for = event.get('for')
      self.delete_receipt(id,receipt_for)
