from .exchange import Exchange
from .fetch_assignment import ExchangeFetchAssignment
from .fetch_feedback import ExchangeFetchFeedback
from .release_assignment import ExchangeReleaseAssignment
from .release_feedback import ExchangeReleaseFeedback
from .list import ExchangeList
from .submit import ExchangeSubmit
from .collect import ExchangeCollect


def configureExchange(c, ngshare_url=None):
    """Modifies nbgrader configuration to use ngshare_exchange as the exchange.
    c is the nbgrader config you get using get_config.
    To use, simply specify the following in your nbgrader_config.py file:

    import ngshare_exchage
    ngshare_exchange.configureExchange(get_config())
    """
    c.ExchangeFactory.exchange = Exchange
    c.ExchangeFactory.fetch_assignment = ExchangeFetchAssignment
    c.ExchangeFactory.fetch_feedback = ExchangeFetchFeedback
    c.ExchangeFactory.release_assignment = ExchangeReleaseAssignment
    c.ExchangeFactory.release_feedback = ExchangeReleaseFeedback
    c.ExchangeFactory.list = ExchangeList
    c.ExchangeFactory.submit = ExchangeSubmit
    c.ExchangeFactory.collect = ExchangeCollect
    if ngshare_url:
        c.ExchangeFactory.exchange._ngshare_url = ngshare_url
