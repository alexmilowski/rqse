import threading
from time import sleep
from rqse import EventClient, EventListener, message

class CountListener(EventListener):

   def __init__(self,key,group,max):
      super().__init__(key,group)
      self._count = 0
      self._max = max

   def process(self,id, event):
      self._count += 1
      print(f'Received message, count={self._count}')
      if self._count==self._max:
         self.stop()
      return True

   @property
   def count(self):
      return self._count

def test_simple_listen():
   key = 'test_simple_listen'
   client = EventClient(key)
   client.delete_stream()

   listener = CountListener(key,'mygroup',3)

   thread = threading.Thread(target=lambda : listener.listen())
   thread.start()

   sleep(1)

   client.append({'fruit':'apple'})
   client.append({'fruit':'orange'})
   client.append({'fruit':'banana'})

   max_wait = 10
   while listener.listening and max_wait>0:
      sleep(1)
      max_wait -= 1

   listener.stop()

   client.delete_stream()
   assert listener.count==3

def test_messages():
   key = 'test_messages'
   client = EventClient(key)
   client.delete_stream()

   listener = CountListener(key,'mygroup',3)

   thread = threading.Thread(target=lambda : listener.listen())
   thread.start()

   # guarantee the consumer groups have been created first so we don't lose messages
   max_wait = 3
   while not listener.established and max_wait>0:
      sleep(1)
      max_wait -= 1

   assert listener.established

   client.append(message({'name':'apple'},kind='food'))
   client.append(message({'name':'orange'},kind='food'))
   client.append(message({'name':'banana'},kind='food'))


   max_wait = 10
   while listener.listening and max_wait>0:
      sleep(1)
      max_wait -= 1

   listener.stop()

   client.delete_stream()
   assert listener.count==3
