from traitlets.config import Config

from .. import configure_exchange
from ..collect import ExchangeCollect
from ..exchange import Exchange
from ..fetch_assignment import ExchangeFetchAssignment
from ..fetch_feedback import ExchangeFetchFeedback
from ..list import ExchangeList
from ..release_assignment import ExchangeReleaseAssignment
from ..release_feedback import ExchangeReleaseFeedback
from ..submit import ExchangeSubmit


def check_classes(c: Config):
    assert c.ExchangeFactory.collect == ExchangeCollect
    assert c.ExchangeFactory.exchange == Exchange
    assert c.ExchangeFactory.fetch_assignment == ExchangeFetchAssignment
    assert c.ExchangeFactory.fetch_feedback == ExchangeFetchFeedback
    assert c.ExchangeFactory.list == ExchangeList
    assert c.ExchangeFactory.release_assignment == ExchangeReleaseAssignment
    assert c.ExchangeFactory.release_feedback == ExchangeReleaseFeedback
    assert c.ExchangeFactory.submit == ExchangeSubmit


def test():
    url = 'http://ngshare'
    c = Config()
    configure_exchange.configureExchange(c, url)
    check_classes(c)
    assert c.ExchangeFactory.exchange.ngshare_url.fget(Exchange) == url


def test_no_url():
    c = Config()
    configure_exchange.configureExchange(c)
    check_classes(c)
