from backports import csv
import sys

import click

from .constants import SUMMARY_URL, TEST_SUMMARY_URL
from .summary import SummaryClient

@click.group()
def main():
    pass

@click.command()
@click.option('--test/--no-test', default=False)
def summary(test):
    if test:
        url = TEST_SUMMARY_URL
    else:
        url = SUMMARY_URL

    client = SummaryClient(url=url)    
    client.fetch()
    fieldnames = [
       'contest_code',
       'race_name',
       'precincts_total',
       'precincts_reporting',
       'vote_for',
       'contest_code',
       'race_name',
       'precincts_total',
       'precincts_reporting',
       'vote_for',
       'candidate_number',
       'full_name',
       'party',
       'vote_total',
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for race in client.races:
        race_attrs = race.serialize() 
        for candidate_result in race.candidates:
            row = dict(**race_attrs)
            row.update(candidate_result.serialize())
            writer.writerow(row)


main.add_command(summary)
