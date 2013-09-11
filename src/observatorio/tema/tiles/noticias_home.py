# -*- coding: utf-8 -*-

import itertools
import time
import feedparser

from zope.component import getUtility

from plone.memoize import request
from plone.memoize.interfaces import ICacheChooser
from collective.cover.tiles.base import IPersistentCoverTile, PersistentCoverTile
from plone.tiles.interfaces import ITileDataManager
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope import schema
from Products.validation import validation


def isUrlList(data):
    verify=validation.validatorFor("isURL")
    for url in (x.strip() for x in data.split()):
        if verify(url)!=True:
            return False
    return True


class INoticiasHomeTile(IPersistentCoverTile):
    """
    """


    titulo_noticia = schema.TextLine(
        title = u"Titulo Noticia",
        default = u"Notícia",
        required = True,
    )

    titulo_clipping = schema.TextLine(
        title = u"Titulo clipping",
        description = u"Clipping SPM",
        default = u"",
        required = False,
    )

    rss_clipping = schema.URI(
        title = u"Fonte RSS do clipping",
        description = u"",
        required = False,
    )

    titulo_blogosfera = schema.TextLine(
        title = u"Titulo bloglosfera",
        description = u"",
        default = u"Blogosfera",
        required = False,
    )

    rss_blogosfera = schema.ASCII(
        title=u"URL(s) dos feeds da blogosfera",
        description=u"Insira as URLs de todos os feeds, um por linha",
        required=True,
        constraint=isUrlList
    )

    cache_timeout = schema.Choice(
        title=u"Tempo maximo para fazer o cache dos dados",
        description=u"",
        default=3600,
        required=True,
        vocabulary="collective.portlet.feedmixer.timeouts"
    )

    items_show = schema.Int(
        title=u"Numeros de itens para exibir",
        description=u"",
        default=5,
        required=True,
    )

    uuid = schema.TextLine(
        title=u'Collection uuid',
        readonly=True,
    )


class NoticiasHomeTile(PersistentCoverTile):
    index = ViewPageTemplateFile("templates/noticias_home.pt")
    is_configurable = False
    is_editable = True
    limit = 3

    def results(self):
        uuid = self.data.get('uuid', None)
        if uuid is not None:
            obj = uuidToObject(uuid)
            return obj

    def populate_with_object(self, obj):
#        super(NoticiasHomeTile, self).populate_with_object(obj)
        if obj.portal_type in self.accepted_ct():
            uuid = IUUID(obj, None)
            data_mgr = ITileDataManager(self)
            data_mgr.set({'uuid': uuid})

    def accepted_ct(self):
        return ['Collection']

    def get_uid(self, obj):
        return IUUID(obj)

    def cleanFeed(self, feed):
        """Sanitize the feed.
        """
        for entry in feed.entries:
            entry["feed"]=feed.feed
            if not "published_parsed" in entry['feed']:
                entry["published_parsed"]=entry["updated_parsed"]
                entry["published"]=entry["updated"]


    def getFeed(self, url):
        """Fetch a feed.
        """
        now=time.time()

        chooser=getUtility(ICacheChooser)
        cache=chooser("collective.portlet.feedmixer.FeedCache")

        cached_data=cache.get(url, None)
        if cached_data is not None:
            (timestamp, feed)=cached_data
            if now-timestamp<self.data.get('cache_timeout'):
                return feed

            newfeed=feedparser.parse(url,
                etag=getattr(feed, "etag", None),
                modified=getattr(feed, "modified", None))
            if newfeed.status==304:
                self.cleanFeed(feed)
                cache[url]=(now+self.data.get('cache_timeout'), feed)
                return feed

        feed=feedparser.parse(url)
        self.cleanFeed(feed)
        cache[url]=(now+self.data.get('cache_timeout'), feed)

        return feed


    def mergeEntriesFromFeeds(self, feeds):
        if not feeds:
            return []
        if len(feeds)==1:
            return feeds[0].entries

        entries=list(itertools.chain(*(feed.entries for feed in feeds)))
        entries.sort(key=lambda x: x["published_parsed"], reverse=True)

        return entries

#    @request.cache(get_key=lambda func,self:self.data.get('rss_blogosfera'),
#                   get_request="self.request")
    def get_entries(self, feeds):
        feeds=self.data.get(feeds)
        if feeds is None:
            feeds = ''
        feeds=[self.getFeed(url) for url in self.feed_urls(feeds)]
        feeds=[feed for feed in feeds if feed is not None]
        entries=self.mergeEntriesFromFeeds(feeds)
        return entries

    def feed_urls(self, feeds):
        return (url.strip() for url in feeds.split())

    def entries(self, feeds):
        return self.get_entries(feeds)[:self.data.get('items_show')]
