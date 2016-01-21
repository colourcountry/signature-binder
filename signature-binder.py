#!/usr/bin/python

import pyPdf
import argparse
import logging
import os


class PageWrapper:
    page_source = None
    page_size = (595.0,842.0)
    margin_sf = 0.8
    margin_bottom = 0.15
    margin_odd = 0.15
    margin_even = 0.05

    def __init__(self, n, blank_reason=None):
        self.n = n
        self.blank_reason = blank_reason

    def __repr__(self):
        if self.n is not None:
            return '#%s' % self.n
        else:
            return 'blank:%s' % self.blank_reason

    def get_scale_factor(self):
        if self.n is not None:
            src_box = self.page_source[self.n].mediaBox
            src_w, src_h = src_box.getWidth(), src_box.getHeight()

            sf_x = PageWrapper.page_size[0] / src_w 
            sf_y = PageWrapper.page_size[1] / src_h

            return min(sf_x,sf_y) * PageWrapper.margin_sf
        else:
            return None

    def get_translation(self):
        if (self.n % 2):
            tr_x = PageWrapper.page_size[0] * PageWrapper.margin_even
        else:
            tr_x = PageWrapper.page_size[0] * PageWrapper.margin_odd
        tr_y = PageWrapper.page_size[1] * PageWrapper.margin_bottom

        return (tr_x, tr_y)

    def get_page(self):
        pg = pyPdf.pdf.PageObject.createBlankPage(None,
            PageWrapper.page_size[0], PageWrapper.page_size[1])

        if self.n is not None:
            # merge in scaled copy of the other page
            pg.mergeScaledTranslatedPage( self.page_source[self.n],
                self.get_scale_factor(),
                *self.get_translation() )

        return pg

parser = argparse.ArgumentParser(description="Convert a PDF into a 2-up double sided PDF suitable for printing and binding as signatures.")

parser.add_argument('pdf', type=str, help='Input PDF file')
parser.add_argument('output', type=str, help='Output PDF file')
parser.add_argument('-s', '--signature-size', type=int, help='Maximum number of pages per signature', default=16)
parser.add_argument('-S', '--start-blanks', type=int, help='Number of blank pages at start',default=4)
parser.add_argument('-E', '--end-blanks', type=int, help='Minimum number of blank pages at end',default=3)
parser.add_argument('-u', '--uneven', action='store_true', help='Make 1 or 2 signatures smaller as necessary (default:spread over more signatures)')
parser.add_argument('-m', '--min-signature-size', type=int, help='Minimum signature size', default=8)
parser.add_argument('-f', '--soft-spine', action='store_true', help='Add a blank leaf to the beginning of the last signature to wrap round the spine')
parser.add_argument('-x', '--skip-start', type=int, help='Skip this many pages at beginning of input file', default=0)
parser.add_argument('-X', '--skip-end', type=int, help='Skip this many pages at end of input file', default=0)
parser.add_argument('--debug', type=str, help='Set log level (default:WARN)', default=None)

args = parser.parse_args()

if args.debug:
    logging.root.setLevel(getattr(logging,args.debug))
else:
    logging.root.setLevel(logging.DEBUG)

if args.signature_size%4 != 0:
    raise ValueError('Signature size must divide by 4.')

reader = pyPdf.PdfFileReader( open(args.pdf,'r') )

pages = list(reader.pages)
skip_end = len(pages) - args.skip_end
pages = pages[args.skip_start:skip_end]
PageWrapper.page_source = pages

blanks = args.start_blanks + args.end_blanks + 2*args.soft_spine
num_pages = (len(pages) + blanks)/4*4

logging.info('%s pages in %s, plus %s blanks = %s' % (len(pages), args.pdf, blanks, num_pages))
signature_sizes = [args.signature_size] * (((num_pages-1) // args.signature_size) + 1)

logging.debug('%s // %s = %s' % (num_pages-1, args.signature_size, num_pages // args.signature_size))

total = sum(signature_sizes)

i = 0

while total > (num_pages+4):
    if signature_sizes[i]-4 < args.min_signature_size:
        break # can't remove any more pages without violating minimum
    signature_sizes[i] -= 4
    total -= 4

    if not args.uneven or signature_sizes[i] == args.min_signature_size:
            i = (i+1) % len(signature_sizes)

logging.info('Using signature sizes %s' % signature_sizes)

def build_signature(size,start):
    s = []
    for i in range(0,size/2,2):
        s.extend([size-i-1,i,i+1,size-i-2])
    return [x+start for x in s]

page_order = []

p = 0
for signature in signature_sizes:
    page_order.extend(build_signature(signature,p))
    p += signature

logging.debug('Page order: %s' % page_order)

page_map = [PageWrapper(None,'extra')]*len(page_order)

for i,p in enumerate(page_order):
    if args.soft_spine and i > len(page_order)-signature_sizes[-1]:
        j = i+2
        if j >= len(page_order):
            break # finished
        q = page_order[j]
    else:
        j = i
        q = p
    if q >= args.start_blanks:
        if q - args.start_blanks < len(pages):
            page_map[j] = PageWrapper(q - args.start_blanks)
        else:
            page_map[j] = PageWrapper(None,'end')
    else:
        page_map[j] = PageWrapper(None,'start')

logging.debug('Page map: %s' % page_map)

writer = pyPdf.PdfFileWriter()
last_page = pages[0]
logging.info('%sx%s' % (last_page.mediaBox.getWidth(),last_page.mediaBox.getHeight()))

for i,wrapper in enumerate(page_map):
    last_page = wrapper.get_page()
    writer.addPage(last_page)

writer.write( open(os.path.expanduser(args.output),'w') )

