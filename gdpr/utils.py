from typing import Any, List, Type, TYPE_CHECKING

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model, QuerySet

if TYPE_CHECKING:
    from auditlog.models import LogEntry


def str_to_class(class_string: str) -> Any:
    module_name, class_name = class_string.rsplit('.', 1)
    # load the module, will raise ImportError if module cannot be loaded
    m = __import__(module_name, globals(), locals(), [str(class_name)])
    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, class_name)
    return c


def get_number_guess_len(value):
    """
    Safety measure against key getting one bigger (overflow) on decrypt e.g. (5)=1 -> 5 + 8 = 13 -> (13)=2
    Args:
        value: Number convertible to int to get it's length

    Returns:
        The even length of the whole part of the number
    """
    guess_len = len(str(int(value)))
    return guess_len if guess_len % 2 != 0 else (guess_len - 1)


def get_field_or_none(model: Type[Model], field_name: str):
    """
    Use django's _meta field api to get field or return None.

    Args:
        model: The model to get the field on
        field_name: The name of the field

    Returns:
        The field or None

    """
    try:
        return model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return None


def get_auditlog_entries(obj: Model) -> QuerySet:
    from auditlog.models import LogEntry

    return LogEntry.objects.get_for_object(obj)


def get_auditlog_entry_model(entry: "LogEntry") -> Type[Model] | None:
    """Get object model of the entry."""
    return entry.content_type.model_class()


def is_auditlog_installed():
    try:
        import auditlog
        return True
    except ImportError:
        return False


def get_all_parent_objects(obj: Model) -> List[Model]:
    """Return all model parent instances."""
    parent_paths = [
        [path_info.join_field.name for path_info in parent_path]
        for parent_path in
        [obj._meta.get_path_to_parent(parent_model) for parent_model in obj._meta.get_parent_list()]
    ]

    parent_objects = []
    for parent_path in parent_paths:
        parent_obj = obj
        for path in parent_path:
            parent_obj = getattr(parent_obj, path, None)
        parent_objects.append(parent_obj)

    return [i for i in parent_objects if i is not None]

def chunked_queryset_iterator(queryset, chunk_size=10000, delete_qs=False):
    """
    Helper that chunks queryset to the smaler chunks to save memory.
    @param queryset: queryset that will be loaded in chunks
    @param chunk_size: maximum size of a chunk
    @param delete_qs: if purpose is remove imput queryset is used faster method for generating chunks
    @return: generator that generates smaler queryset from the input queryset
    """
    if delete_qs:
        while queryset.exists():
            yield queryset[:chunk_size]
    else:
        queryset = queryset.order_by("pk")
        last_pk = None
        while queryset.exists():
            batch_queryset = queryset.filter()
            if last_pk:
                batch_queryset = batch_queryset.filter(pk__gt=last_pk)
            batch_queryset = queryset.filter(pk__in=batch_queryset[:chunk_size].values("pk"))
            last_pk = batch_queryset[batch_queryset.count() - 1].pk
            yield batch_queryset
