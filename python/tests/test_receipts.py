import threading
from time import sleep
from rqse import EventClient, EventListener, ReceiptListener, message, receipt_for

class ReceiptGeneratorListener(EventListener):

   def __init__(self,key,group,selection,max):
      super().__init__(key,group,select=selection)
      self._count = 0
      self._max = max

   def process(self,id, event):
      self._count += 1
      print(f'Received message, count={self._count}')
      self.append(receipt_for(id))
      if self._count==self._max:
         self.stop()
      return True

   @property
   def count(self):
      return self._count

class ReceiptLog:

   def __init__(self):
      self.count = 0

   def log(self,connection,id,receipt,target_id,target):
      self.count += 1
      return True

def test_receipts():
   key = 'test_receipts'
   client = EventClient(key)
   client.delete_stream()
   generator = ReceiptGeneratorListener(key,'generator',['fruit'],3)

   logger = ReceiptLog()
   receipts = ReceiptListener(key,logger=logger)

   generator_thread = threading.Thread(target=lambda : generator.listen())
   generator_thread.start()

   receipts_thread = threading.Thread(target=lambda : receipts.listen())
   receipts_thread.start()

   # guarantee the consumer groups have been created first so we don't lose messages
   max_wait = 3
   while (not generator.established or not receipts.established) and max_wait>0:
      sleep(1)
      max_wait -= 1

   assert generator.established
   assert receipts.established

   client.append(message({'name':'apple'},kind='fruit'))
   client.append(message({'name':'orange'},kind='fruit'))
   client.append(message({'name':'banana'},kind='fruit'))

   max_wait = 10
   while generator.listening and max_wait>0:
      sleep(1)
      max_wait -= 1

   generator.stop()
   receipts.stop()

   in_stream = len(client)

   max_wait = receipts.wait
   while (generator.running or receipts.running) and max_wait>0:
      sleep(1)
      max_wait -= 1

   client.delete_stream()
   assert generator.count==3
   assert logger.count==3
   assert in_stream==0

def test_different_receipts():
   key = 'test_different_receipts'
   client = EventClient(key)
   client.delete_stream()

   generator_fruit = ReceiptGeneratorListener(key,'fruit',['fruit'],3)
   generator_animals = ReceiptGeneratorListener(key,'animal',['animal'],3)
   receipts = ReceiptListener(key)

   generator_fruit_thread = threading.Thread(target=lambda : generator_fruit.listen())
   generator_fruit_thread.start()

   generator_animals_thread = threading.Thread(target=lambda : generator_animals.listen())
   generator_animals_thread.start()

   receipts_thread = threading.Thread(target=lambda : receipts.listen())
   receipts_thread.start()

   # guarantee the consumer groups have been created first so we don't lose messages
   max_wait = 3
   while (not generator_fruit.established or not generator_animals.established or not receipts.established) and max_wait>0:
      sleep(1)
      max_wait -= 1

   assert generator_fruit.established
   assert generator_animals.established
   assert receipts.established

   client.append(message({'name':'apple'},kind='fruit'))
   client.append(message({'name':'monkey'},kind='animal'))
   client.append(message({'name':'orange'},kind='fruit'))
   client.append(message({'name':'cat'},kind='animal'))
   client.append(message({'name':'dog'},kind='animal'))
   client.append(message({'name':'banana'},kind='fruit'))

   max_wait = 10
   while (generator_fruit.listening or generator_animals.listening) and max_wait>0:
      sleep(1)
      max_wait -= 1

   generator_fruit.stop()
   generator_animals.stop()
   receipts.stop()

   in_stream = len(client)

   max_wait = receipts.wait
   while (generator_fruit.running or generator_animals.running or receipts.running) and max_wait>0:
      sleep(1)
      max_wait -= 1

   client.delete_stream()

   assert generator_fruit.count==3
   assert generator_animals.count==3
   assert in_stream==0
