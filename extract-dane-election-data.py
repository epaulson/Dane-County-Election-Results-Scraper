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
import argparse
import csv

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

def parseResults(locallines, starts, dx, top, bottom,elecdesc,electionNumber):
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
    totalspat = re.compile("TOTALS")
    totalpat = re.compile("TOTAL")
    percentpat = re.compile("PERCENT")
    # from http://stackoverflow.com/questions/4703390/how-to-extract-a-floating-number-from-a-string-in-python
    floatingpointpat = re.compile("[-+]?\d*\.\d+|\d+")

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
        if(totalspat.search(l)): 
           atoms = l.split()
           totalvotes = atoms[-len(labels):]
           #
           # OK, this sorta blows - sometimes you'll get lines like this:
           #  (from spring 2001 election in Mazo - three(!) writein slots, none used)
           #
           # 0051 VILLAGE OF MAZOMANIE WDS 1-2         67      72      49      47      33      63      79       0       0       0
           #                               TOTALS      67      72      49      47      33      63      79
           #                      PERCENT OF TOTAL   16.34   17.56   11.95   11.46    8.04   15.36   19.26
           #
           #   so, we'll look for a position where see a number, and take the slice to the end, 
           #   treat that as our new list of totals, and stick zeros on the end
           #
           for u in range(len(totalvotes)):
               if(floatingpointpat.search(totalvotes[u])):
                   validtotals = totalvotes[u:]
                   validtotals.extend(list('0' for n in range(len(labels) - len(validtotals))))
                   totalvotes = validtotals
                   break
        # 
        # Play the same trick as above for missing percentages
        if(percentpat.search(l)): 
           atoms = l.split()
           percents = atoms[-len(labels):]
           for u in range(len(percents)):
               if(floatingpointpat.search(percents[u])):
                   validpercents = percents[u:]
                   validpercents.extend(list('0' for n in range(len(labels) - len(validpercents))))
                   percents = validpercents
                   break
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
    if args['header']:
        report['ElectionDescription'] = providedDesc['Race%d' % (electionNumber)]
    else:
        report['ElectionDescription'] = ' '.join(elecdesc)

    return report

# Start of actual code

parser = argparse.ArgumentParser(description='Download and parse Dane County Election Results')

group = parser.add_mutually_exclusive_group()

parser.add_argument('url', help='The Election URL to scrape')
parser.add_argument('dir', help='Directory in which to store resulting CSV files. Must exist before running the script')
parser.add_argument('-header', action="store", help='A CSV File, with a mapping of Races to Descriptions')
group.add_argument('-json', action="store_true", default=False, help='Format the results as a single JSON object')
group.add_argument('-summary', action="store_true", default=False, help='One-line summary of each election in the results')
group.add_argument('-genheader', action="store_true", default=False, help="Create a CSV file of potential headers")

args = vars(parser.parse_args())


providedDesc = {}
if args['header']:
    headerdata = list(csv.reader(open(args['header'], 'rt')))
    for row in headerdata[1:]:
       providedDesc[row[0]] = row[1]


if args['url']:
    try:
        doc = lxml.html.parse(args['url']).getroot()
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

electionNumber = 0
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
        extracted.append(parseResults(lines[previousStart:n], starts, dx, top-previousStart, bottom-previousStart,elecdesc,electionNumber))

        # reset the state machine, clear out election description
        previousStart = n 
        headerOver = False
        searching = True
        seenAnything = False
        electionNumber += 1
        elecdesc = []

# dump it out and call it a day
if args['json']:
    print json.dumps(extracted)
elif args['summary']:
    def addtwo(x,y): return float(x)+float(y)

    for i in range(electionNumber):
        #print "\nProcessing Race%d.csv -- %s " % (i, extracted[i]['ElectionDescription'])
        election_summary =  zip(extracted[i]['Candidates'], map(int, extracted[i]['VoteTotals']), map(float, extracted[i]['Percentages']) if extracted[i]['Percentages'] else list((float(extracted[i]['VoteTotals'][n]) / float(reduce(addtwo, extracted[i]['VoteTotals'] )) * 100.0) for n in range(len(extracted[i]['Candidates']))))
        # from http://stackoverflow.com/questions/457215/comprehension-for-flattening-a-sequence-of-sequences 
        joined =  reduce(election_summary[0].__class__.__add__, election_summary)
        print "Race%d,%s,%s" % (i, extracted[i]['ElectionDescription'], ','.join(str(e) for e in joined))
elif args['genheader']:
   f = open("headers.csv", "wt")
   fields = ["RaceID", "RaceDesc"]
   output = csv.writer(f) 
   output.writerow(fields)
   for i in range(electionNumber):
      output.writerow(["Race%d" % (i), extracted[i]['ElectionDescription']])
   f.close()
else:
    for i in range(electionNumber):
        f = open("%s/race%d.csv" % (args['dir'], i), 'wt')
        fields = ["WardNumber", "WardDesc"] + extracted[i]['Candidates']
        print "\nProcessing Race%d.csv -- %s " % (i, extracted[i]['ElectionDescription'])
        print fields
        output = csv.writer(f)
        output.writerow(fields)
        for row in extracted[i]['WardData']:
            output.writerow([row['WardNumber'], row['WardDesc']] + row['Votes'])
        f.close()
    print "\n\nExtracted %d elections" % (electionNumber)
