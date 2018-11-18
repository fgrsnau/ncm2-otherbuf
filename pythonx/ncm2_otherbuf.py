# -*- coding: utf-8 -*-

import itertools
import re

import vim
from ncm2 import Ncm2Source, getLogger


logger = getLogger(__name__)


class BufferData:

    __slots__ = ('changed', 'words')

    def __init__(self, words=None):
        self.changed = False
        if words is not None:
            self.words = set(words)
        else:
            self.words = set()


class Source(Ncm2Source):

    PATTERN = re.compile(r'\w+')
    WORDS_PER_BUFFER = 1000

    def __init__(self, nvim):
        super().__init__(nvim)
        self.buffers = dict()
        self.update()

    def update(self):
        buffers_present = set()

        for buf in self.nvim.buffers:
            schedule_update = (not buf.number in self.buffers) or (self.buffers[buf.number].changed)
            if schedule_update:
                self.buffers[buf.number] = self.rescan_buffer(buf)
            buffers_present.add(buf.number)

        self.buffers = {k: v for k, v in self.buffers.items() if k in buffers_present}

    def rescan_buffer(self, buf):
        logger.info('rescan_buffer(%s)', buf.number)

        words = dict()
        def inc_word(word):
            count = words.get(word, 0)
            words[word] = count + 1

        for line in buf:
            for word in self.PATTERN.finditer(line):
                inc_word(word.group())

        sorted_words = sorted(words.items(), reverse=True, key=lambda x: x[1])
        sorted_words = (word for word, count in sorted_words)
        result = BufferData(itertools.islice(sorted_words, self.WORDS_PER_BUFFER))
        logger.info('keyword refresh complete, count: %s', len(result.words))
        return result

    def on_event(self, event, bufnr):
        logger.info('Received event %s for buffer %s', event, bufnr)
        if event == 'BufLeave':
            buf = self.buffers[bufnr]
            buf.changed = True

        if event in ('BufAdd', 'BufDelete', 'BufLeave'):
            self.update()

    def on_complete(self, ctx):
        base = ctx['base']
        matcher = self.matcher_get(ctx['matcher'])
        matches = []
        for bufnr, buf in self.buffers.items():
            if bufnr != ctx['bufnr']:
                for word in buf.words:
                    item = self.match_formalize(ctx, word)
                    if matcher(base, item):
                        matches.append(item)
        self.complete(ctx, ctx['startccol'], matches)


source = Source(vim)

on_complete = source.on_complete
on_event = source.on_event
