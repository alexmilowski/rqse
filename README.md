# rqse
Queued Service Events for Redis → rqse (pronounced "rose")

## Overview

This library is in the spirit of [Martin Fowler's Event-Carried State Transfer](https://martinfowler.com/articles/201701-event-driven.html)
but for whole system architectures. The intent is we can consider our system
as an obvervable timeline of events. When each event gets processed, the
processor generates an receipt as an event. Eventually, the receipt and the
target of the receipt can be archived into a long-term storage (or thrown away).

At the center of all of this are [Redis Streams](https://redis.io/docs/manual/data-types/streams/).
They provide a lightweight but fast and reliable mechanism for representing the
portion of the timeline that is in progress. It also allows a simple mechanism
for different consumers to process messages and generate receipts.

## Getting Started

Install the package:

```bash
pip install rqse
```

A producing system can add events as JSON objects. By default, the `kind` property is used to designate the kind of system event:

```python
from rqse import EventClient, message

# the stream key
key = 'events'
client = EventClient(key=key)

client.append(message(data={'name':'make-bread'},kind='start'))
client.append(message(data={'name':'make-sandwich'},kind='start'))
```

And a system can receive events as a consumer:

```python
from rqse import EventListener, receipt_for
import logging

# the stream key
key = 'events'
# the consumer group
group = 'starter'

class StartListener()

   def process(self,message_id,event):
      name = event.get('name')
      logging.info(f'Started {name}')
      self.append(receipt_for(message_id))
      return True

listener = StartListener(key=key,group=group,select=['start'])
listener.listen()

```

And we can process receipts for things processed

```python
from rqse import ReceiptListener

# the stream key
key = 'events'

listener = ReceiptListener(key=key)
listener.listen()

```
