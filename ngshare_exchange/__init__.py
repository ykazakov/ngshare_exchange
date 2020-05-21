from .exchange import Exchange
from .submit import ExchangeSubmit
from .release_feedback import ExchangeReleaseFeedback
from .release import ExchangeRelease
from .release_assignment import ExchangeReleaseAssignment
from .fetch_feedback import ExchangeFetchFeedback
from .fetch import ExchangeFetch
from .fetch_assignment import ExchangeFetchAssignment
from .collect import ExchangeCollect
from .list import ExchangeList

def configureExchange(c):
    '''Modifies nbgrader configuration to use ngshare_exchange as the exchange.
    c is the nbgrader config you get using get_config.
    To use, simply specify the following in your nbgrader_config.py file:

    import ngshare_exchage
    ngshare_exchange.configureExchange(get_config())
    '''
    c.ExchangeFactory.exchange = Exchange
    c.ExchangeFactory.fetch_assignment = ExchangeFetchAssignment
    c.ExchangeFactory.fetch_feedback = ExchangeFetchFeedback
    c.ExchangeFactory.release_assignment = ExchangeReleaseAssignment
    c.ExchangeFactory.release_feedback = ExchangeReleaseFeedback
    c.ExchangeFactory.list = ExchangeList
    c.ExchangeFactory.submit = ExchangeSubmit
    c.ExchangeFactory.collect = ExchangeCollect

__all__ = [
    "Exchange",
    "ExchangeError",
    "ExchangeCollect",
    "ExchangeFetch",
    "ExchangeFetchAssignment",
    "ExchangeFetchFeedback",
    "ExchangeList",
    "ExchangeRelease",
    "ExchangeReleaseAssignment",
    "ExchangeReleaseFeedback",
    "ExchangeSubmit",
    "configureExchange",
]
