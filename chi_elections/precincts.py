"""
Parse tabular precinct-level results.
"""
from collections import OrderedDict

from lxml import html
import requests
from six.moves.urllib.parse import urlencode, urlparse, parse_qs
from six import text_type

from chi_elections.transforms import replace_single_quotes

class BaseParser(object):
    @classmethod
    def clean_cell(cls, s):
        return text_type(s).strip()

    def get_row_data(self, tr):
        return [self.clean_cell(td.text_content()) for td in tr.xpath('td')]

    @classmethod
    def clean_candidate_name(cls, s):
        return replace_single_quotes(s)

    def parse_candidates(self, row):
        candidates = {}
        for i, val in enumerate(row):
            if val in (self.reporting_unit_column_name, "%"):
                continue

            candidates[i] = self.clean_candidate_name(val)

        return candidates

    def parse_result_row(self, row, candidate_lookup):
        results = []
        result = None
        for i, val in enumerate(row):
            if i == 0:
                reporting_unit_id = val
                continue

            try:
                candidate = candidate_lookup[i]
                if result is not None:
                    # If a previous result has been built, add it to our list
                    results.append(result)
                result = {
                    'reporting_unit_id': reporting_unit_id,
                    'candidate': candidate,
                    'votes': int(val),
                }
            except KeyError:
                # No candidate at this column index.
                # Assume it's the percentage column
                result['percent'] = float(val.strip('%'))

        if result is not None:
            results.append(result)

        return results

    def parse(self, html_string):
        results = []

        rows = html.fromstring(html_string).xpath('//table[1]/tr')
        candidate_lookup = None
        for tr_idx, tr in enumerate(rows):
            row = self.get_row_data(tr)
            if len(row) < 2:
                # This is a blank row, so skip
                continue

            if row[0] == self.reporting_unit_column_name:
                # This is the header row
                if candidate_lookup is None:
                    candidate_lookup = self.parse_candidates(row)
                continue

            row_results = self.parse_result_row(row, candidate_lookup)
            results.extend(row_results)

        return results


class WardParser(BaseParser):
    reporting_unit_column_name = 'Ward'


class PrecinctParser(BaseParser):
    reporting_unit_column_name = 'Pct'


class ReportingUnit(object):
    def __init__(self, number):
        self.number = number
        self._results = []

    def add_result(self, result):
        self._results.append(result)

    @property
    def results(self):
        return self._results


class Ward(ReportingUnit):
    level = 'ward'

    def __init__(self, number):
        super(Ward, self).__init__(number)
        self._precincts = {}

    def get_or_create_precinct(self, number):
        try:
            return self._precincts[number]
        except KeyError:
            self._precincts[number] = Precinct(number, self)
            return self._precincts[number]

    def __str__(self):
        return "{:02d}".format(self.number)

    def __repr__(self):
        return "Ward({})".format(self.__str__())


class Precinct(ReportingUnit):
    level = 'precinct'

    def __init__(self, number, ward):
        super(Precinct, self).__init__(number)
        self.ward = ward

    def __str__(self):
        return "{:02d}{:03d}".format(int(self.ward.number),
            int(self.number))

    def __repr__(self):
        return "Precinct({})".format(self.__str__())


class Candidate(object):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return "Candidate({})".format(self.name)


class Election(object):
    def __init__(self, elec_code, name=None, client=None):
        self.elec_code = elec_code
        self.name = name

        if client is None:
            self.client = PrecinctClient()

        self._races_by_number = None
        self._races_by_name = None
        self._races = None

    @property
    def races(self):
        if self._races is None:
            self.fetch_races()

        return self._races

    def add_race(self, race):
        if race.number is not None:
            self._races_by_number[race.number] = race

        if race.name is not None:
            self._races_by_name[race.name] = race

        self._races.append(race)

    def get_race_by_number(self, race_number):
        return self._races_by_number[race_number]

    def get_race_by_name(self, race_name):
        return self._races_by_name[race_name]

    def fetch_races(self):
        race_html = self.client.fetch_election_html(self.elec_code)
        option_els = html.fromstring(race_html).xpath(
            "//select[@name='D3']/option")

        self._races_by_number = {}
        self._races_by_name = {}
        self._races = []

        for option_el in option_els:
            race_name = option_el.get('value')
            if not race_name:
                continue
            race = Race(self, name=race_name)


class Race(object):
    def __init__(self, election, name=None, number=None):
        self.number = number
        self.name = name
        self.election = election
        self.client = election.client

        election.add_race(self)

        self._results = None
        self._wards = None

    def __str__(self):
        if self.name and self.number:
            return "{} ({})".format(self.name, self.number)
        elif self.name:
            return self.name
        elif self.number:
            return self.number
        else:
            return ""

    @property
    def results(self):
        if self._results is None:
            self._results = self.fetch_results()

        return self._results

    @property
    def wards(self):
        if self._wards is None:
            self.fetch_wards()

        return self._wards.values()

    def fetch_wards(self):
        ward_results_html = self.client.fetch_ward_results_html(
            elec_code=self.election.elec_code,
            race_name=self.name
        )

        if self.number is None:
            first_ward_url = html.fromstring(ward_results_html).xpath('//a[1]')[0].get('href')
            # TODO: Factor this out
            query_string = urlparse(first_ward_url).query
            query_string_parsed = parse_qs(query_string)
            self.number = int(query_string_parsed['race_number'][0])

        parser = WardParser()
        results_attrs = parser.parse(ward_results_html)
        self._wards = {}

        for result_attrs in results_attrs:
            if result_attrs['reporting_unit_id'] == "Total":
                continue

            ward_number = int(result_attrs['reporting_unit_id'])
            self._wards.setdefault(ward_number, Ward(
                number=ward_number,
            ))

    def fetch_results(self):
        results = []
        for ward in self.wards:
            ward_results =  self.client.fetch_precinct_results(
                elec_code=self.election.elec_code,
                race=self,
                ward_num=ward.number)
            results.extend(ward_results)

        return results


class Result(object):
    def __init__(self, candidate, votes, reporting_unit, percent=None, race=None):
        self.candidate = candidate
        self.votes = votes
        self.reporting_unit = reporting_unit
        self.percent = percent
        self.race = race

        self.reporting_unit.add_result(self)

    def __str__(self):
        return "{} - {} ({})".format(self.candidate, self.votes,
            self.reporting_unit)

    def __repr__(self):
        return "Result(candidate={}, reporting_unit={}, votes={})".format(
            repr(self.candidate), repr(self.reporting_unit), self.votes
        )

    @property
    def ward_number(self):
        if self.reporting_unit.level == "ward":
            return self.reporting_unit.number
        elif self.reporting_unit.level == "precinct":
            return self.reporting_unit.ward.number
        else:
            return None

    @property
    def precinct_number(self):
        if self.reporting_unit.level == "precinct":
            return self.reporting_unit.number
        else:
            return None

    def serialize(self):
        return OrderedDict((
            ('race_name', self.race.name),
            ('race_number', self.race.number),
            ('candidate', self.candidate.name),
            ('ward', self.ward_number),
            ('precinct', self.precinct_number),
            ('votes', self.votes),
        ))


class PrecinctClient(object):
    DEFAULT_PRECINCT_URL = 'http://www.chicagoelections.com/en/pctlevel3.asp'
    DEFAULT_ELECTION_URL = 'http://www.chicagoelections.com/en/wdlevel3.asp'

    def __init__(self, election_url=None, precinct_url=None):
        if election_url is None:
            election_url = self.DEFAULT_ELECTION_URL

        self._election_url = election_url

        if precinct_url is None:
            precinct_url = self.DEFAULT_PRECINCT_URL

        self._precinct_url = precinct_url

        self._parser = PrecinctParser()
        self._wards = {}
        self._candidates_by_name = {}

    def get_election_url(self, elec_code):
        url = self._election_url
        query_params = {
            'elec_code': elec_code,
        }
        qs = urlencode(query_params)
        return url + '?' + qs

    def fetch_election_html(self, elec_code):
        url = self.get_election_url(elec_code)
        return requests.get(url).text

    def fetch_ward_results_html(self, elec_code, race_name):
        url = self.get_election_url(elec_code)
        return requests.post(url, data={
                'VTI-GROUP': 0,
                'flag': 1,
                'B1': 'View The Results',
                'D3': race_name,
            }).text

    def get_precinct_result_url(self, elec_code, race_number, ward):
        url = self._precinct_url
        query_params = {
            'elec_code': elec_code,
            'race_number': race_number,
            'Ward': ward,
        }
        qs = urlencode(query_params)
        return url + '?' + qs

    def fetch_precinct_results_html(self, elec_code, race_number, ward):
        url = self.get_precinct_result_url(elec_code, race_number, ward)
        return requests.get(url).text

    def get_or_create_ward(self, ward_num):
        try:
            return self._wards[ward_num]
        except KeyError:
            self._wards[ward_num] = Ward(ward_num)
            return self._wards[ward_num]

    def get_or_create_candidate_by_name(self, name):
        try:
            return self._candidates_by_name[name]
        except KeyError:
            self._candidates_by_name[name] = Candidate(name)
            return self._candidates_by_name[name]

    def create_ward_result(self, result_dict, ward):
        candidate = self.get_or_create_candidate_by_name(result_dict['candidate'])
        return Result(candidate, result_dict['votes'],
            percent=result_dict['percent'], reporting_unit=ward)

    def create_result(self, result_dict, race, ward_num):
        ward = self.get_or_create_ward(ward_num)
        if result_dict['reporting_unit_id'] == 'Total':
            reporting_unit = ward
        else:
            reporting_unit = ward.get_or_create_precinct(result_dict['reporting_unit_id'])

        candidate = self.get_or_create_candidate_by_name(result_dict['candidate'])

        if isinstance(race, Race):
            race_model = race
        else:
            race_model = Race(number=race)

        return Result(
            candidate=candidate,
            votes=result_dict['votes'],
            reporting_unit=reporting_unit,
            percent=result_dict.get('percent', None),
            race=race_model
        )

    def fetch_precinct_results(self, elec_code, race, ward_num):
        if isinstance(race, Race):
            race_number = race.number
        else:
            race_number = race

        html_string = self.fetch_precinct_results_html(elec_code, race_number,
            ward_num)
        results = self._parser.parse(html_string)
        return [self.create_result(rd, race, ward_num) for rd in results]
