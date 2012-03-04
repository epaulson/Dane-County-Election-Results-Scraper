#!/usr/bin/env python
#
# Dane County Election Results Scraper
# Erik Paulson
# epaulson@unit1127.com
# This is not important enough to warrant a copyright
# or license, so do with it what you will
# 4 March 2012
#

import sys
import re
# I don't remember where I picked up this idea
# for trying different json packages
try: import simplejson as json
except ImportError: import json
import lxml.html

#
# Given a set of lines from the larger election results text,
# extract the structured data contained. Spit 3 times after
# trying to look at the formatting, because it's clearly
# not meant for machines to read
# 
# locallines - the slice of lines to consider, with the 
# description header, the diagonal candidate labels, vote
# totals, and footer information
# starts - the x positions of the start of each of the label
# columns. They're 5 columns wide
# top, bottom, dx - the lines on which the diagonals start 
# and stop. dx really should be dy, but it's the difference
# between top and bottom.
#
# elecdesc is the header text. It might be voter instructions, time, 
# random "OFFICIAL CANVASS" lines, candidate labels, etc. 
# There doesn't seem to be any rhyme or reason to what goes in
# that section, so basically, I shove all the extra text
# into that field and punt on the problem for now til I know 
# how someone might want to use it
#  

def parseResults(locallines, starts, dx, top, bottom,elecdesc):
    # clean up end of lines on the extracted text. This was leftover
    # from an early version and probably isn't necessary if later code
    # was more clever. 
    content =  [l.rstrip() for l in locallines[top:bottom+1]]

    # this looks nastier than it really is. Each candidate or question gets a column
    # of results, but that "column" is really 5 characters wide. We know where each
    # column begins (starts), and we iterate over that with i
    # We start the top (with j) and work our way down each line, adding the next character
    # to our string. 
    # The only crazy thing is that it's a diagonal, so at each line, we move one to the right
    # to follow the diagonal down. 
    # So, x-dx moves us left to the appropriate starting position
    # j moves us to the right at each line
    # i corrects for which of the 5 interior columns we're working with
    #  
    # each line may not extend horizontally far enough in the "wide column" (think long
    # first name and short last name - the spaces for the last name diagonal might not be
    # present). If that's the case, detect it and give it a blank space as filler. 
    #
    # When all is said and done, strip off any extra white space, and join the 5 diagonals into
    # a string for the wide column, then stick that string on to the labels array 
    labels = []
    for x in starts:
        diags = []
        for i in range(5):
            line = [content[j][x-dx+j+i] if len(content[j]) > (x-dx+j+i) else ' ' for j in range(dx+1)]
            diags.append(''.join(line))
        labels.append(' '.join([l.strip() for l in diags if len(l.strip()) > 0]))

    # Now, we're going to find results. Results for wards all start with a number
    # the totals and percentages have a unqiue string, so we'll find them that way
    wardpat = re.compile("^\d+")
    totalpat = re.compile("TOTALS")
    percentpat = re.compile("PERCENT")

    wards = []
    totalvotes = []
    percents = []

    # Note that there's a slight bug here - bottom is the bottom of the diagonal, not
    # the position of the dashes. If there were party labels, bottom is really 2 lines from
    # the start of results. However, because we search by regular expression, it doesn't matter
    for l in locallines[bottom+1:]:
        #
        # If the line starts with a number, it's a ward result. Split it up into chunks
        # the last columns are vote results, so slice that off. 
        # the first column is the ward number, so slice that off too
        # Anything leftover is a description of the ward, so just glue that back together
        # and treat it as freeform text
        #
        # when we're done, stick the results for thsi ward onto our wards list
        #
        if(wardpat.search(l)):
            atoms = l.split()
            votes = atoms[-len(labels):]
            ward = atoms[0].strip()
            desc = atoms[1:-len(labels)] 
            wardreport = {}
            wardreport['WardNumber'] = ward
            wardreport['WardDesc'] = ' '.join(desc)
            wardreport['Votes'] = votes
            wards.append(wardreport)
        #
        # total votes and perctanges, just take the results and save them
        # as an array. There will be one result per label
        # 
        # Percentages isn't always present - the total ballots report (which
        # some elections is posted and others isn't) doesn't do a breakdown
        # this way
        if(totalpat.search(l)): 
           atoms = l.split()
           totalvotes = atoms[-len(labels):]
        if(percentpat.search(l)): 
           atoms = l.split()
           percents = atoms[-len(labels):]
        #
        # There's no real end of record that you can look at
        # so as soon as we hit a line that's entirely blank, we
        # must be done
        if(len(l.strip()) is 0):
            #print "Found the end of the record!"
            break

    # put it all back together in structured format and return
    report = {}

    report['Candidates'] = labels
    report['WardData'] = wards
    report['VoteTotals'] = totalvotes
    report['Percentages'] = percents
    report['ElectionDescription'] = ' '.join(elecdesc)

    return report

# Start of actual code
if (len(sys.argv) <= 1):
    print("Usage: python extract-dane-election-data.py URL")
    exit(1)

try:
    doc = lxml.html.parse(sys.argv[1]).getroot()
except e:
    # TODO - do something with this
    pass

#
# It's easy to find the start of the report, after ignoring
# the header table and other crap. Each race and question gets
# an anchor named race or raceX, where X > 0
# However, each race is not wrapped nicely in a div or anything,
# so you can't extract it as any sort of XMLish element. 
# So, rather than jumping race to race, just find the start 
# and pull out all of the text. 
# you could also look for the <PRE> data
# 
race = doc.xpath("//a[@name='race']")
lines = race[0].text_content().splitlines()

top = None
bottom = None

# pattern is any two characters next to each other, ie
# a non-blank line. Lines containing diagonals will never
# have two characters next to each other.

pattern = re.compile("\w\w")
partylabels = re.compile("\(\w\w\w\)")

# The names will be sandwiched between some header text and
# a line with '-----' per column. We need to remember where each 
# column is located to know how to combine the diagonals into
# actual names
#
# Unfortunately, there can be multiple lines of header before
# the diagonal, or NO lines of header before the diagonal,  and there's 
# not really any good "You will always see  this phrase" to go by. 
# The best heurstic seems to be "lines with
# diagonals never have two characters next to each other, the header
# always ends before the diagonals start"
# So, we'll keep a few states around to keep track of what's happening 
#
headerOver = False
searching = True
seenAnything = False

# our list for where we'll keep everything when we're done. Once
# we extract data, we reset our state machine and continue on through
# the lines
extracted = []
previousStart = 0

# elecdesc is any extract crap that we don't know what
# to do with. 
# 
elecdesc = []
for n in range(len(lines)):
    #
    # the normal case - we found some consecutive characters
    # but we haven't seen the dashes yet, so shove it in
    # to the election description, and remember that we've seen
    # at least one line.
    #
    # We are scanning through the entire record, looking for a blank line
    # to tell us that we're done. Use 'headerOver' to keep track of that, so
    # we don't put vote total and percentage text into the election description
    if(pattern.search(lines[n]) and not headerOver):
        if not (partylabels.search(lines[n])):
            elecdesc.append(lines[n].strip())
            seenAnything = True
    #
    # something above failed - either we didn't see two consective chars
    # or the header is over. If we're now into non-blank lines but have
    # not seen consective characters, there wasn't a header. If there was,
    # we will have noted it ealier, and go ahead and mark this as the start of
    # diagonals and stop looking for header
    elif searching:
        if seenAnything: 
            top = n 
            searching = False

    #
    # look for lines with '-----'
    # this gives us back a list with the location of every place it occurs
    #
    results = [m.start() for m in re.finditer('-----', lines[n])]
    if(len(results) > 0):
        # We found a line with a bunch of dashes, so we know where the header ends
        # We need to check if the party labels are in between the dashes and the
        # diagonal names or if this is a non-partisan race
        if(partylabels.search(lines[n-1])):
            # TODO - capture the party labels and return them
            bottom = n-2
        else:
            bottom = n-1
        starts = results
        headerOver = True

    if(headerOver and len(lines[n].strip()) is 0):
        dx = bottom - top 
        #print "Top: %d Bottom %d Total height: %d Start: %d end %d" % (top-previousStart, bottom-previousStart, dx, previousStart, n)
        extracted.append(parseResults(lines[previousStart:n], starts, dx, top-previousStart, bottom-previousStart,elecdesc))

        # reset the state machine, clear out election description
        previousStart = n 
        headerOver = False
        searching = True
        seenAnything = False
        elecdesc = []

# dump it out and call it a day
print json.dumps(extracted)
