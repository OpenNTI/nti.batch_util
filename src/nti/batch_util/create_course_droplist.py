#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import codecs
import requests
import json
import csv
import cStringIO
import os.path
import sys
import re
import time
import datetime
import argparse
from getpass import getpass


def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]


def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """

    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")


class UnicodeDictReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)
        self.header = self.reader.next()

    def next(self):
        row = self.reader.next()
        vals = [unicode(s, "utf-8") for s in row]
        return dict((self.header[x], vals[x]) for x in range(len(self.header)))

    def __iter__(self):
        return self


class UnicodeWriter(object):
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


class UnicodeDictWriter(csv.DictWriter):
    def __init__(self, f, fieldnames, restval="", extrasaction="raise",
                 dialect="excel", *args, **kwds):
        csv.DictWriter.__init__(self, f, fieldnames, restval, extrasaction,
                                dialect, *args, **kwds)
        self.writer = UnicodeWriter(f, dialect, *args, **kwds)


requests_codes = requests.codes


def get_course_catalog_entries(site, user_name, pass_word):

    catalog_location = "/dataserver2/CourseAdmin/AllCatalogEntries"

    # example location to pull all catalog entries
    # url = "https://alpha.nextthought.com/dataserver2/CourseAdmin/AllCatalogEntries"
    url = 'https://%s%s' % (site, catalog_location)
    print url

    # populate the dictionary with items entry to avoid a failure in 'def get_course_catalog_summary', though the exception handling should work too
    catalog = {'Items': []}

    try:
        response = requests.get(url, auth=(user_name, pass_word))
        status = response.raise_for_status()
        if response.status_code == requests_codes.ok:
            catalog = response.json()
    except requests.exceptions.HTTPError as e:
        print e

    return catalog


def get_course_enrollment_csv(ntiid, site, user_name, pass_word):

    course_enrollment = "/dataserver2/CourseAdmin/@@CourseEnrollments?ntiid="

    # example location to pull all catalog entries
    # url = https://prmia.nextthought.com/dataserver2/CourseAdmin/@@CourseEnrollments?ntiid=tag:nextthought.com,2011-10:NTI-CourseInfo-Fall_2015_PRM_Designmation_Online_Training
    url = 'https://%s%s%s' % (site, course_enrollment, ntiid)
    print url

    summary_csv = ""

    try:
        response = requests.get(url, auth=(user_name, pass_word))
        print response.headers.get('content-type')
        status = response.raise_for_status()
        if response.status_code == requests_codes.ok:
            summary_csv = response.text
    except requests.exceptions.HTTPError as e:
        print e

    return summary_csv


def get_course_catalog_summary(site, user_name, pass_word):

    catalog_location = "/dataserver2/CourseAdmin/AllCatalogEntries"

    # get the catalog entries, in JSON format
    catalog = get_course_catalog_entries(site, catalog_location, user_name, pass_word)

    # go through each catalog entry pulling the stats via the @@summary call
    courses = []
    for item in catalog['Items']:
        title = item['title']
        for link in item['Links']:
            if link['rel'] == 'CourseInstance':
                # %s is a substitution placeholder, ENV the the Link
                url = 'https://%s%s' % (site, link['href'] + " ")
                print url

                try:
                    response = requests.get(url, auth=(user_name, pass_word))
                    status = response.raise_for_status()
                    if response.status_code == requests_codes.ok:
                        summary = response.json()
                        data = {
                            'Site': site,
                            'Title': title or 'No Title',
                            'Url': str(url) or 'No Url',
                            'TotalEnrollments': str(summary['TotalEnrollments']),
                            'ForCredit': str(summary['TotalEnrollmentsByScope']['ForCredit']),
                            'Public': str(summary['TotalEnrollmentsByScope']['Public']),
                            'ForCreditDegree': str(summary['TotalEnrollmentsByScope']['ForCreditDegree']),
                            'Purchased': str(summary['TotalEnrollmentsByScope']['Purchased']),
                            'ForCreditNonDegree': str(summary['TotalEnrollmentsByScope']['ForCreditNonDegree']),
                        }
                # print(json.dumps(data))
                    courses.append(data)
                except requests.exceptions.HTTPError as e:
                    print e

    return courses


def build_enrollment_summary(catalog, site, user_name, pass_word, course_age_limit):
    output = [['site', 'ntiid', 'username', 'realname', 'email', 'scope', 'created', 'created_date', 'course_age', 'drop_insructions']]  # store our CSV full output here

    # loop through all NTIIDs get the enrollment summary pull out the date and write back out to CSV
    for item in catalog['Items']:
        ntiid = item['NTIID']
        # print "ntiid: %s " % ntiid

        try:
            print "Getting enrollment summary from site: %s" % str(site)
            enrollment_summary_csv = get_course_enrollment_csv(ntiid, site, user_name, pass_word)
        except Exception as e:
            print e

        line = unicode_csv_reader(enrollment_summary_csv.splitlines(), delimiter=',', quotechar='|')

        #import pdb; pdb.set_trace()

        for row in line:
            if 'username' in row:  # skip the header record
                continue
            username = row[0]

            #import pdb; pdb.set_trace()

            udatetime = row[-1]
            date_list = row[-1].split('T')
            enroll_date = date_list[0]

            cdatetime = datetime.datetime.strptime(udatetime, '%Y-%m-%dT%H:%M:%S')
            now = datetime.datetime.now()
            acct_age = (now - cdatetime).days  # converts datetime.datetime to datetime.timedelta to integer

            drop_ins = ""

            if (acct_age > course_age_limit):
                drop_ins = "http -v -a %s:%s POST 'https://%s/dataserver2/CourseAdmin/UserCourseDrop' ntiid='%s' username=%s User-Agent:NextThought" % (user_name, pass_word, site, ntiid, username)
                print drop_ins

            row.insert(0, site)
            row.insert(1, ntiid)
            row.extend([enroll_date, str(acct_age).encode("utf-8"), drop_ins])
            # print row
            output.append(row)
    return output


def parse_args():
    arg_parser = argparse.ArgumentParser(description="Get enrollment summary")
    arg_parser.add_argument('output',
                            help="Output csv filename")
    arg_parser.add_argument('-cal', '--course_age_limit',
                            help="Course age limit. The default value is 400 days",
                            default=400)
    arg_parser.add_argument('-s', '--site',
                            help="Site name",
                            required=True)
    arg_parser.add_argument('-u', '--username',
                            help="Username",
                            required=True)
    return arg_parser.parse_args()


def main():
    args = parse_args()
    site = args.site
    file_out = args.output
    user_name = args.username
    pass_word = getpass('Password for %s@%s: ' % (args.username, args.site))

    course_age_limit = args.course_age_limit  # the client asked for 1 yr, we added some buffer to that.

    # this outer try block is to catch any unhandled execptions from main
    try:
        site = site.rstrip()  # trim any trailing spaces if sites are read in from a file
        print "Getting catalog from site: %s" % str(site)
        catalog = get_course_catalog_entries(site, user_name, pass_word)
    except Exception as e:
        print e

    output = build_enrollment_summary(catalog, site, user_name, pass_word, course_age_limit)

    with open(file_out, "wb") as csv_file:
        writer = UnicodeWriter(csv_file, delimiter=',')
        for line in output:
            writer.writerow(line)


if __name__ == '__main__':  # pragma: no cover
    main()
