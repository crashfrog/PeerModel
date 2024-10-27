from collections.abc import MutableMapping

"""
Dict-like interface into the IPLD merkle forest, with namespace support.

"""

class NamespacedIPLDDictionary(MutableMapping):

        def __init__(self, namespace, *args, **kwargs):
            pass

        def __getitem__(self, key):
            pass

        def __setitem__(self, key, value):
            pass

        def __delitem__(self, key):
            pass

        def __iter__(self):
            pass

        def __len__(self):
            pass