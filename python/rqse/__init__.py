__version__=(0,5,2)
__author__ = 'Alex Miłowski'
__author_email__ = 'alex@milowski.com'

from .client import EventClient, EventListener
from .messaging import message, receipt_for, ReceiptListener
