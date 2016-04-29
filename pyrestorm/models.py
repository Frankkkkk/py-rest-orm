import six

from pyrestorm.exceptions import orm as orm_exceptions
from pyrestorm.query import RestQueryset


class RestOrmManager(object):
    # Ensure the objects is only available at the class level
    def __get__(self, instance, cls=None):
        if instance is not None:
            raise AttributeError('`RestOrmManager` isn\'t accessible via `%s` instances' % cls.__name__)
        return self

    # Since the OrmManager instance is instantiated on the RestModel, this allows us to know the parent class
    def contribute_to_class(self, cls):
        self.model = cls

    # Returns a new instance of the RestQueryset
    def _get_queryset(self):
        return RestQueryset(self.model)

    # Return RestQueryset for all elements
    def all(self, *args, **kwargs):
        return self._get_queryset()


class RestModelBase(type):
    # Called when class is imported got guarantee proper setup of child classes to parent
    def __new__(cls, name, bases, attrs):
        # Call to super
        super_new = super(RestModelBase, cls).__new__

        # Also ensure initialization is only performed for subclasses of Model
        # (excluding Model class itself).
        parents = [b for b in bases if isinstance(b, RestModelBase)]
        if not parents:
            return super_new(cls, name, bases, attrs)

        # Create the current class
        new_class = super_new(cls, name, bases, {'__module__': attrs.pop('__module__')})
        new_class._meta = attrs.pop('Meta', None)

        # Instantiate the manager instance
        new_class.objects = new_class.objects()

        # Make links to children if they ask for it, shamelessly stolen from Django
        for attr in [attr for attr in dir(new_class) if not callable(attr) and not attr.startswith('__')]:
            if hasattr(getattr(new_class, attr), 'contribute_to_class'):
                getattr(new_class, attr).contribute_to_class(new_class)

        return new_class


class RestModel(six.with_metaclass(RestModelBase)):
    # Bind the JSON data from a response to a new instance of the model
    def __init__(self, *args, **kwargs):
        data = kwargs.pop('data', {})
        super(RestModel, self).__init__()

        # Bind data to the model
        self._bind_data(self, data)

    # Manager to act like Django ORM
    objects = RestOrmManager

    # Defines shortcut for exceptions
    DoesNotExist = orm_exceptions.DoesNotExist
    MultipleObjectsReturned = orm_exceptions.MultipleObjectsReturned

    # Bind the JSON data to the new instance
    @staticmethod
    def _bind_data(obj, data):
        for key, val in data.iteritems():
            # Bind the data to the next level if need be
            if isinstance(val, dict):
                # Create the class if need be, otherwise do nothing
                setattr(obj, key, type(key.title(), (), {})) if not hasattr(obj, key) else None
                attr = getattr(obj, key)
                RestModel._bind_data(attr, val)
            else:
                setattr(obj, key, val)
