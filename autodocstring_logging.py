import logging
import textwrap

# - possible parameters for format at :
#   https://hg.python.org/cpython/file/5c4ca109af1c/Lib/logging/__init__.py#l399

LOG_FORMAT = "%(name)s:%(levelname)s:%(lineno)s: %(message)s"

logger = logging.getLogger("auto_docstring")

logger.setLevel(logging.WARNING)
# logger.setLevel(logging.DEBUG)


class _CustomFilter(logging.Filter, object):
    def filter(self, record):
        if '\n' not in record.msg:
            record.msg = '\n'.join(textwrap.wrap(record.msg, width=65))
        spaces = ' ' * (len(record.levelname) + 2)
        record.msg = record.msg.replace('\n', '\n' + spaces)
        return super(_CustomFilter, self).filter(record)


for _handler in logger.handlers:
    logger.removeHandler(_handler)

for _filter in logger.filters:
    logger.removeFilter(_filter)

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT))
logger.addHandler(_handler)

logger.addFilter(_CustomFilter())
logger.propagate = False

##
## EOF
##
