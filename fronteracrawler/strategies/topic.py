# -*- coding: utf-8 -*-
from urlparse import urlparse
from crawlfrontier.contrib.canonicalsolvers.basic import BasicCanonicalSolver
from crawlfrontier.contrib.backends.hbase import _state
from fronteracrawler.classifier.classifier import TopicClassifier
from fronteracrawler.classifier.content_processor import ContentProcessor, ParsedContent


class CrawlStrategy(object):

    S_QUEUED = _state.get_id('QUEUED')
    S_NOT_CRAWLED = _state.get_id('NOT_CRAWLED')
    S_ERROR = _state.get_id('ERROR')
    fetch_limit = 300000

    def __init__(self):
        self.canonicalsolver = BasicCanonicalSolver()
        self.content_processor = ContentProcessor()

    def configure(self, config):
        self.classifier = TopicClassifier.from_keywords(config['included'], config['excluded'])
        self.max_doc_count = config['nResults']
        self.results = {}
        self.stats = {
            'downloaded': 0,
            'errors': 0,
            'scheduled': 0
        }

    def add_seeds(self, seeds):
        scores = {}
        for seed in seeds:
            if seed.meta['state'] is None:
                url, fingerprint, _ = self.canonicalsolver.get_canonical_url(seed)
                scores[fingerprint] = 1.0
                seed.meta['state'] = self.S_QUEUED
        return scores

    def page_crawled(self, response, links):
        scores = {}
        response.meta['state'] = _state.get_id('CRAWLED')
        pc = self.content_processor.process_response(response)
        score = self.classifier.score_paragraphs(pc)
        drill_down = self.classifier.classify_paragraphs(score)

        if drill_down:
            self.results[response.meta['fingerprint']] = score

        scheduled = 0
        for link in links:
            if link.meta['state'] is None:
                url, fingerprint, _ = self.canonicalsolver.get_canonical_url(link)
                scores[fingerprint] = score
                link.meta['state'] = self.S_QUEUED if drill_down else self.S_NOT_CRAWLED
                scheduled += 1
        self.stats['downloaded'] += 1
        self.stats['scheduled'] += scheduled
        return scores

    def page_error(self, request, error):
        url, fingerprint, _ = self.canonicalsolver.get_canonical_url(request)
        request.meta['state'] = self.S_ERROR
        self.stats['errors'] += 1
        return {fingerprint: 0.0}

    def finished(self):
        return self.stats['downloaded'] + self.stats['errors'] > self.fetch_limit
