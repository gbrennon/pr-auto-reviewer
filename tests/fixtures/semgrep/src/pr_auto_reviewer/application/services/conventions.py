from dataclasses import field

# ruleid: python-no-mutable-default-arguments
def list_default(values=[]):
    return values

# ruleid: python-no-mutable-default-arguments
def dict_default(values={}):
    return values

# ruleid: python-no-mutable-default-arguments
def set_default(values=set()):
    return values


# ruleid: python-no-mutable-default-arguments
async def async_list_default(values=[]):
    return values

def valid_defaults(values=None, labels=field(default_factory=list)):
    return values, labels

# ruleid: python-no-production-suppression-directives
value_noqa = 1  # noqa

# ruleid: python-no-production-suppression-directives
value_type_ignore = 2  # type: ignore

# ruleid: python-no-production-suppression-directives
value_pyright_ignore = 3  # pyright: ignore

# ruleid: python-no-production-suppression-directives
value_pylint_disable = 4  # pylint: disable=unused-variable

# ruleid: python-no-production-suppression-directives
value_nosec = 5  # nosec

# ruleid: python-no-production-wildcard-imports
from pr_auto_reviewer.domain.value_objects import *

from pr_auto_reviewer.domain.value_objects import CodeReview
