from rqse import EventClient

def test_connect():
   key = 'test_connect'
   client = EventClient(key)
   client.delete_stream()

   client.append({'character':'Phineas'})
   client.append({'character':'Ferb'})
   count = len(client)
   client.delete_stream()
   assert count==2

def test_reading():
   key = 'test_reading'
   client = EventClient(key)
   client.delete_stream()

   sent = [{'test':'one'},{'test':'two'},{'test':'three'}]

   for data in sent:
      client.append(data)

   count = len(client)
   assert count==3

   result = [ data for id, data in client.read(3)]
   client.delete_stream()

   for index, item in enumerate(result):
      assert sent[index]==item
