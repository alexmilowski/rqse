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
