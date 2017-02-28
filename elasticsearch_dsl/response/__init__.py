from ..utils import AttrDict, AttrList

from .hit import Hit, HitMeta

class SuggestResponse(AttrDict):
    def success(self):
        return not self._shards.failed

class Response(AttrDict):
    def __init__(self, search, response):
        super(AttrDict, self).__setattr__('_search', search)
        super(Response, self).__init__(response)

    def __iter__(self):
        return iter(self.hits)

    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            # for slicing etc
            return self.hits[key]
        return super(Response, self).__getitem__(key)

    def __nonzero__(self):
        return bool(self.hits)
    __bool__ = __nonzero__

    def __repr__(self):
        return '<Response: %r>' % self.hits

    def __len__(self):
        return len(self.hits)

    def __getstate__(self):
        return (self._d_, self._search)

    def __setstate__(self, state):
        super(AttrDict, self).__setattr__('_d_', state[0])
        super(AttrDict, self).__setattr__('_search', state[1])

    def success(self):
        return self._shards.total == self._shards.successful and not self.timed_out

    def _get_result(self, hit):
        dt = hit['_type']
        for t in hit.get('inner_hits', ()):
            hit['inner_hits'][t] = Response(self._search, hit['inner_hits'][t])
        callback = self._search._doc_type_map.get(dt, Hit)
        callback = getattr(callback, 'from_es', callback)
        return callback(hit)

    @property
    def hits(self):
        if not hasattr(self, '_hits'):
            h = self._d_['hits']

            try:
                hits = AttrList(map(self._get_result, h['hits']))
            except AttributeError as e:
                # avoid raising AttributeError since it will be hidden by the property
                raise TypeError("Could not parse hits.", e)

            # avoid assigning _hits into self._d_
            super(AttrDict, self).__setattr__('_hits', hits)
            for k in h:
                setattr(self._hits, k, h[k])
        return self._hits

    @property
    def aggregations(self):
        return self.aggs

    @property
    def aggs(self):
        if not hasattr(self, '_aggs'):
            aggs = AggResponse(self._search.aggs, self._search, self._d_.get('aggregations', {}))

            # avoid assigning _aggs into self._d_
            super(AttrDict, self).__setattr__('_aggs', aggs)
        return self._aggs

class AggResponse(AttrDict):
    def __init__(self, aggs, search, data):
        super(AttrDict, self).__setattr__('_meta', {'search': search, 'aggs': aggs})
        super(AggResponse, self).__init__(data)

    def __getitem__(self, attr_name):
        if attr_name in self._meta['aggs']:
            # don't do self._meta['aggs'][attr_name] to avoid copying
            agg = self._meta['aggs'].aggs[attr_name]
            return agg.result(self._meta['search'], self._d_[attr_name])
        return super(AggResponse, self).__getitem__(attr_name)

    def __iter__(self):
        for name in self._meta['aggs']:
            yield self[name]

