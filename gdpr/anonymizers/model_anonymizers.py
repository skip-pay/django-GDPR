import hashlib
import random
import string
import warnings
from typing import (
    Any, Dict, ItemsView, Iterator, KeysView, List, Optional, TYPE_CHECKING, Tuple, Type, Union, ValuesView)

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db.models import Model, QuerySet
from django.db.models.fields import Field

from gdpr.anonymizers.base import BaseAnonymizer, FieldAnonymizer, RelationAnonymizer
from gdpr.fields import Fields
from gdpr.models import AnonymizedData, LegalReason
from gdpr.utils import get_field_or_none, is_auditlog_installed, get_auditlog_entries

if TYPE_CHECKING:
    from gdpr.purposes.default import AbstractPurpose
    from auditlog.models import LogEntry

FieldList = Union[List, Tuple, KeysView[str]]  # List, tuple or return of dict keys() method.
FieldMatrix = Union[str, Tuple[Any, ...]]


class ModelAnonymizerMeta(type):
    """
    Metaclass for anonymizers. The main purpose of the metaclass is to register anonymizers and find field anonymizers
    defined in the class as attributes and store it to the fields property.
    """

    def __new__(cls, name, bases, attrs):
        from gdpr.loading import anonymizer_register

        new_obj = super().__new__(cls, name, bases, attrs)

        # Also ensure initialization is only performed for subclasses of ModelAnonymizer
        # (excluding Model class itself).
        parents = [b for b in bases if isinstance(b, ModelAnonymizerMeta)]
        if not parents or not hasattr(new_obj, 'Meta'):
            return new_obj

        fields = getattr(new_obj, 'fields', {})
        anonymizers = getattr(new_obj, 'anonymizers', {})

        for name, obj in attrs.items():
            if isinstance(obj, BaseAnonymizer):
                anonymizers[name] = obj
                if isinstance(obj, FieldAnonymizer):
                    fields[name] = obj

        new_obj.fields = fields
        new_obj.anonymizers = anonymizers

        if not getattr(new_obj.Meta, 'abstract', False):
            anonymizer_register.register(new_obj.Meta.model, new_obj)
            new_obj.Meta.anonymize_auditlog = getattr(new_obj.Meta, 'anonymize_auditlog', False)
            new_obj.Meta.delete_auditlog = getattr(new_obj.Meta, 'delete_auditlog', False)
            new_obj.Meta.reversible_anonymization = getattr(new_obj.Meta, 'reversible_anonymization', True)

        return new_obj


class ModelAnonymizerBase(BaseAnonymizer, metaclass=ModelAnonymizerMeta):

    can_anonymize_qs: bool
    fields: Dict[str, FieldAnonymizer]
    anonymizers: Dict[str, BaseAnonymizer]
    _base_encryption_key = None

    class IrreversibleAnonymizerException(Exception):
        pass

    def __init__(self, base_encryption_key: Optional[str] = None):
        self._base_encryption_key = base_encryption_key

    @property
    def model(self) -> Type[Model]:
        return self.Meta.model  # type: ignore

    @property
    def content_type(self) -> ContentType:
        """Get model ContentType"""
        return ContentType.objects.get_for_model(self.model)

    def __getitem__(self, item: str) -> FieldAnonymizer:
        return self.fields[item]

    def __contains__(self, item: str) -> bool:
        return item in self.fields.keys()

    def __iter__(self) -> Iterator[str]:
        for i in self.fields:
            yield i

    def keys(self) -> KeysView[str]:
        return self.fields.keys()

    def items(self) -> ItemsView[str, FieldAnonymizer]:
        return self.fields.items()

    def values(self) -> ValuesView[FieldAnonymizer]:
        return self.fields.values()

    def get(self, *args, **kwargs) -> Union[FieldAnonymizer, Any]:
        return self.fields.get(*args, **kwargs)

    def _get_encryption_key(self, obj, field_name: str):
        """Hash encryption key from `get_encryption_key` and append settings.GDPR_KEY or settings.SECRET_KEY."""
        return hashlib.sha256(
            f'{obj.pk}::{self.get_encryption_key(obj)}::'
            f'{settings.GDPR_KEY if hasattr(settings, "GDPR_KEY") else settings.SECRET_KEY}::{field_name}'.encode(
                'utf-8')).hexdigest()

    def is_reversible(self, obj) -> bool:
        return self.Meta.reversible_anonymization  # type: ignore

    def anonymize_auditlog(self, obj: Model, field_names: list[str], anonymization: bool):
        for entry in get_auditlog_entries(obj):
            for name in field_names:
                if name in entry.changes:
                    entry.changes[name] = self.get_value_from_entry(
                        self[name], obj, entry, name, anonymization=anonymization
                    )
            entry.save()

    def delete_auditlog(self, obj: Model, anonymization: bool):
        if anonymization:
            get_auditlog_entries(obj).delete()

    def get_encryption_key(self, obj) -> str:
        if not self.is_reversible(obj):
            return ''.join(random.choices(string.digits + string.ascii_letters, k=128))
        if self._base_encryption_key:
            return self._base_encryption_key
        raise NotImplementedError(
            f'The anonymizer \'{self.__class__.__name__}\' does not have `get_encryption_key` method defined or '
            '`base_encryption_key` supplied during anonymization or '
            'reversible_anonymization set to False.')

    def set_base_encryption_key(self, base_encryption_key: str):
        self._base_encryption_key = base_encryption_key

    def is_field_anonymized(self, obj: Model, name: str) -> bool:
        """Check if field have AnonymizedData record"""
        return AnonymizedData.objects.filter(
            field=name, is_active=True, content_type=self.content_type, object_id=str(obj.pk)
        ).exists()

    def get_related_model(self, field_name: str) -> Type[Model]:
        field = get_field_or_none(self.model, field_name)
        if field is None:
            anonymizer = self.anonymizers.get(field_name)
            if anonymizer and isinstance(anonymizer, (ModelAnonymizerBase, RelationAnonymizer)):
                return anonymizer.model
            raise RuntimeError(f'Field \'{field_name}\' is not defined on {str(self.model)}')
        elif hasattr(field, "related_model"):
            return field.related_model
        else:
            raise NotImplementedError(f'Relation {str(field)} not supported yet.')

    def get_value_from_obj(self, field: FieldAnonymizer, obj: Model, name: str, anonymization: bool = True) -> Any:
        return field.get_value_from_obj(obj, name, self._get_encryption_key(obj, name), anonymization=anonymization)

    def get_value_from_entry(
        self, field: FieldAnonymizer, obj: Model, entry: "LogEntry", name: str, anonymization: bool = True
    ) -> Any:
        return field.get_value_from_entry(
            obj, entry, name, self._get_encryption_key(obj, name), anonymization=anonymization
        )

    def update_field_as_anonymized(self, obj: Model, name: str, legal_reason: Optional[LegalReason] = None,
                                   anonymization: bool = True):
        if anonymization:
            AnonymizedData.objects.create(object=obj, field=name, expired_reason=legal_reason)
        else:
            AnonymizedData.objects.filter(
                field=name, is_active=True, content_type=self.content_type, object_id=str(obj.pk)
            ).delete()

    def _perform_update(self, obj: Model, updated_data: dict, legal_reason: Optional[LegalReason] = None,
                        anonymization: bool = True):
        for field_name, value in updated_data.items():
            setattr(obj, field_name, value)

        if is_auditlog_installed():
            # this handles cases where history for anonymized change is not tracked
            from auditlog.context import disable_auditlog
            with disable_auditlog():
                obj.save()
        else:
            obj.save()
        for field_name in updated_data.keys():
            self.update_field_as_anonymized(obj, field_name, legal_reason, anonymization=anonymization)

    def perform_update(self, obj: Model, updated_data: dict, legal_reason: Optional[LegalReason] = None,
                       anonymization: bool = True):
        self._perform_update(obj, updated_data, legal_reason, anonymization=anonymization)

    def anonymize_qs(self, qs: QuerySet) -> None:
        raise NotImplementedError()

    def deanonymize_qs(self, qs: QuerySet) -> None:
        raise NotImplementedError()

    def get_related_model_anonymizer_none(self, name):
        anonymizer = self.anonymizers.get(name)

        if anonymizer and isinstance(anonymizer, ModelAnonymizerBase):
            return anonymizer
        elif anonymizer and isinstance(anonymizer, RelationAnonymizer):
            return anonymizer.model_anonymizer
        else:
            return None

    def update_related_anonymizer_fields(self,
                                         field_name: str,
                                         anonymizer: RelationAnonymizer,
                                         obj: Model,
                                         related_fields: Fields,
                                         legal_reason: Optional[LegalReason] = None,
                                         purpose: Optional["AbstractPurpose"] = None,
                                         anonymization: bool = True):
        """
        Anonymize related object defined in related anonymization class.
        Args:
            field_name: name of the model field/property
            anonymizer: relation anonymizer defined it the model anonymization class
            obj: django model instance
            related_fields: fields which will be anonymized
            legal_reason: legal reason which raises anonymization
            purpose: deactivated purpose
            anonymization: anonymize or not
        """
        objs = anonymizer.get_related_objects(obj)
        for related_obj in objs:
            related_fields.anonymizer.update_obj(
                related_obj, legal_reason, purpose, related_fields,
                base_encryption_key=self._get_encryption_key(obj, field_name),
                anonymization=anonymization
            )

    def update_related_model_property_fields(self,
                                             field_name: str,
                                             obj: Model,
                                             related_fields: Fields,
                                             legal_reason: Optional[LegalReason] = None,
                                             purpose: Optional["AbstractPurpose"] = None,
                                             anonymization: bool = True):
        """
        Anonymize related object or objects get from model property.
        Args:
            field_name: name of the model field/property
            obj: django model instance
            related_fields: fields which will be anonymized
            legal_reason: legal reason which raises anonymization
            purpose: deactivated purpose
            anonymization: anonymize or not
        """
        related_attribute = getattr(obj, field_name, None)

        if hasattr(obj.__class__, field_name) and related_attribute is None:
            return
        elif isinstance(related_attribute, Model):
            related_fields.anonymizer.update_obj(
                related_attribute, legal_reason, purpose, related_fields,
                base_encryption_key=self._get_encryption_key(obj, field_name),
                anonymization=anonymization
            )
        elif isinstance(related_attribute, QuerySet):
            for related_obj in related_attribute:
                related_fields.anonymizer.update_obj(
                    related_obj, legal_reason, purpose, related_fields,
                    base_encryption_key=self._get_encryption_key(obj, field_name),
                    anonymization=anonymization
                )
        else:
            warnings.warn(f'Model anonymization discovered unreachable field {field_name} on model'
                          f'{obj.__class__.__name__} on obj {obj} with pk {obj.pk}')

    def update_related_model_fields(self,
                                    field_name: str,
                                    related_metafield: Field,
                                    obj: Model,
                                    related_fields: Fields,
                                    legal_reason: Optional[LegalReason] = None,
                                    purpose: Optional["AbstractPurpose"] = None,
                                    anonymization: bool = True):
        """
        Anonymize related object or objects get from model field.
        Args:
            field_name: name of the model field
            related_metafield: meta infromations get from django model field
            obj: django model instance
            related_fields: fields which will be anonymized
            legal_reason: legal reason which raises anonymization
            purpose: deactivated purpose
            anonymization: anonymize or not
        """
        related_attribute = getattr(obj, field_name, None)
        if related_metafield.one_to_many or related_metafield.many_to_many:
            for related_obj in related_attribute.all():
                related_fields.anonymizer.update_obj(
                    related_obj, legal_reason, purpose, related_fields,
                    base_encryption_key=self._get_encryption_key(obj, field_name),
                    anonymization=anonymization
                )
        elif related_metafield.many_to_one or related_metafield.one_to_one:
            if related_attribute is not None:
                related_fields.anonymizer.update_obj(
                    related_attribute, legal_reason, purpose, related_fields,
                    base_encryption_key=self._get_encryption_key(obj, field_name),
                    anonymization=anonymization
                )
        else:
            warnings.warn(f'Model anonymization discovered unreachable field {field_name} on model'
                          f'{obj.__class__.__name__} on obj {obj} with pk {obj.pk}')

    def update_related_fields(self, parsed_fields: Fields, obj: Model, legal_reason: Optional[LegalReason] = None,
                              purpose: Optional["AbstractPurpose"] = None, anonymization: bool = True):
        for name, related_fields in parsed_fields.related_fields.items():
            related_metafield = get_field_or_none(self.model, name)
            anonymizer = self.anonymizers.get(name)

            if anonymizer and isinstance(anonymizer, RelationAnonymizer):
                self.update_related_anonymizer_fields(
                    name, anonymizer, obj, related_fields, legal_reason, purpose, anonymization
                )
            elif related_metafield:
                self.update_related_model_fields(
                    name, related_metafield, obj, related_fields, legal_reason, purpose, anonymization
                )
            else:
                self.update_related_model_property_fields(
                    name, obj, related_fields, legal_reason, purpose, anonymization
                )

    def update_obj(self, obj: Model, legal_reason: Optional[LegalReason] = None,
                   purpose: Optional["AbstractPurpose"] = None,
                   fields: Union[Fields, FieldMatrix] = '__ALL__',
                   base_encryption_key: Optional[str] = None,
                   anonymization: bool = True):
        if not anonymization and not self.is_reversible(obj):
            raise self.IrreversibleAnonymizerException(f'{self.__class__.__name__} for obj "{obj}" is not reversible.')

        if base_encryption_key:
            self._base_encryption_key = base_encryption_key

        parsed_fields: Fields = Fields(fields, obj.__class__) if not isinstance(fields, Fields) else fields

        if anonymization:
            raw_local_fields = [i for i in parsed_fields.local_fields if not self.is_field_anonymized(obj, i)]
        else:
            raw_local_fields = [i for i in parsed_fields.local_fields if
                                self.is_field_anonymized(obj, i) and self[i].get_is_reversible(obj)]

        if raw_local_fields:
            update_dict = {
                name: self.get_value_from_obj(self[name], obj, name, anonymization) for name in raw_local_fields
            }
            if self.Meta.delete_auditlog:
                self.delete_auditlog(obj, anonymization)
            elif self.Meta.anonymize_auditlog:
                self.anonymize_auditlog(obj, raw_local_fields, anonymization)
            self.perform_update(obj, update_dict, legal_reason, anonymization=anonymization)

        self.update_related_fields(parsed_fields, obj, legal_reason, purpose, anonymization)

    def anonymize_obj(self, obj: Model, legal_reason: Optional[LegalReason] = None,
                      purpose: Optional["AbstractPurpose"] = None,
                      fields: Union[Fields, FieldMatrix] = '__ALL__', base_encryption_key: Optional[str] = None):

        self.update_obj(obj, legal_reason, purpose, fields, base_encryption_key, anonymization=True)

    def deanonymize_obj(self, obj: Model, fields: Union[Fields, FieldMatrix] = '__ALL__',
                        base_encryption_key: Optional[str] = None):

        self.update_obj(obj, fields=fields, base_encryption_key=base_encryption_key, anonymization=False)


class ModelAnonymizer(ModelAnonymizerBase):
    """
    Default model anonymizer that supports anonymization per object.
    Child must define Meta class with model (like factoryboy)
    """

    can_anonymize_qs = False
    chunk_size = 10000


class DeleteModelAnonymizer(ModelAnonymizer):
    """
    The simplest anonymization class that is used for removing whole input queryset.

    For anonymization add `__SELF__` to the FieldMatrix.
    """

    can_anonymize_qs = True

    DELETE_FIELD_NAME = '__SELF__'

    def update_obj(self, obj: Model, legal_reason: Optional[LegalReason] = None,
                   purpose: Optional["AbstractPurpose"] = None,
                   fields: Union[Fields, FieldMatrix] = '__ALL__',
                   base_encryption_key: Optional[str] = None,
                   anonymization: bool = True):
        parsed_fields: Fields = Fields(fields, obj.__class__) if not isinstance(fields, Fields) else fields

        if self.DELETE_FIELD_NAME in parsed_fields.local_fields and anonymization is True:
            self.update_related_fields(parsed_fields, obj, legal_reason, purpose, anonymization)

            obj.__class__.objects.filter(pk=obj.pk).delete()

            if self.Meta.delete_auditlog:
                self.delete_auditlog(obj, anonymization)

        elif self.DELETE_FIELD_NAME in parsed_fields.local_fields:
            parsed_fields.local_fields = [i for i in parsed_fields.local_fields if i != self.DELETE_FIELD_NAME]
            super().update_obj(obj, legal_reason, purpose, parsed_fields, base_encryption_key, anonymization)
        else:
            super().update_obj(obj, legal_reason, purpose, parsed_fields, base_encryption_key, anonymization)

    def anonymize_qs(self, qs):
        qs.delete()
