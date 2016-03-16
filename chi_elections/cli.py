from backports import csv
import sys

import click

from .constants import SUMMARY_URL, TEST_SUMMARY_URL
from .precincts import PrecinctClient, Election
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


@click.command()
@click.argument('elections', nargs=-1)
@click.option('--race', '-r', default=None, multiple=True)
def precincts(elections, race):
    fieldnames = [
       'race_name',
       'race_number',
       'candidate',
       'reporting_unit_level',
       'reporting_unit_number',
       'votes',
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for election_id in elections:
        election = Election(elec_code=election_id)
        if len(race):
            races_set = set()
            for rid in race:
                try:
                    race_identifier = int(rid)
                except ValueError:
                    race_identifier = rid

                races_set.add(race_identifier)

            races = [r for r in election.races
                     if r.number in races_set or r.name in races_set]

        else:
            races = election.races

        for race in races:
            for result in race.results:
                try:
                    writer.writerow(result.serialize())
                except UnicodeDecodeError:
                    print(result.serialize())
                    raise

main.add_command(precincts)
