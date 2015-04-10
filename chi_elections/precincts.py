"""
Parse tabular precinct-level results.
"""
import json

from lxml import html
import requests
from six.moves.urllib.parse import urlencode


class PrecinctParser(object):
    def get_row_data(self, tr):
        return [td.text_content().strip() for td in tr.xpath('td')]

    def parse_candidates(self, row):
        candidates = {}
        for i, val in enumerate(row):
            if val in ("Pct", "%"):
                continue

            candidates[i] = val

        return candidates

    def parse_result_row(self, row, candidate_lookup):
        results = []
        result = None
        for i, val in enumerate(row):
            if i == 0:
                precinct_num = val
                continue

            try:
                candidate = candidate_lookup[i]
                if result is not None:
                    # If a previous result has been built, add it to our list
                    results.append(result)
                result = {
                    'precinct': precinct_num,
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

        rows = html.fromstring(html_string).xpath('/html/body/table[1]/tr')
        candidate_lookup = None
        for tr_idx, tr in enumerate(rows):
            row = self.get_row_data(tr)
            if len(row) < 2:
                # This is a blank row, so skip
                continue

            if row[0] == 'Pct':
                # This is the header row
                if candidate_lookup is None:
                    candidate_lookup = self.parse_candidates(row)
                continue

            row_results = self.parse_result_row(row, candidate_lookup)
            results.extend(row_results)

        return results


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
    def __init__(self, name=None, number=None):
        self.number = number
        self.name = name

        self._races_by_number = {}
        self._races_by_name = {}
        self._races = []

    @property
    def races(self):
        return self._races_by_number.values()

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
        # TODO: Implement this
        pass


class Race(object):
    def __init__(self, election, name=None, number=None):
        self.number = number
        self.name = name
        self.election = election

        election.add_race(self)

    def fetch_results(self):
        # TODO: Implement this
        pass


class Result(object):
    def __init__(self, candidate, votes, reporting_unit, percent=None, race=None):
        self.candidate = candidate
        self.votes = votes
        self.reporting_unit = reporting_unit
        self.percent = percent
        self.race = None

        self.reporting_unit.add_result(self)

    def __str__(self):
        return "{} - {} ({})".format(self.candidate, self.votes,
            self.reporting_unit)

    def __repr__(self):
        return "Result(candidate={}, reporting_unit={}, votes={})".format(
            repr(self.candidate), repr(self.reporting_unit), self.votes
        )


class PrecinctClient(object):
    DEFAULT_PRECINCT_URL = 'http://www.chicagoelections.com/en/pctlevel3.asp'

    def __init__(self, precinct_url=None):
        if precinct_url is None:
            precinct_url = self.DEFAULT_PRECINCT_URL
        self._precinct_url = precinct_url
        self._parser = PrecinctParser()
        self._wards = {}
        self._candidates_by_name = {}

    def get_precinct_result_url(self, elec_code, race_number, ward):
        url = self._precinct_url
        query_params = {
            'Ward': ward,
            'elec_code': elec_code,
            'race_number': race_number,
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

    def create_result(self, result_dict, ward_num):
        ward = self.get_or_create_ward(ward_num)
        if result_dict['precinct'] == 'Total':
            reporting_unit = ward
        else:
            reporting_unit = ward.get_or_create_precinct(result_dict['precinct'])

        candidate = self.get_or_create_candidate_by_name(result_dict['candidate'])

        return Result(
            candidate=candidate,
            votes=result_dict['votes'],
            reporting_unit=reporting_unit,
            percent=result_dict.get('percent', None)
        )

    def fetch_precinct_results(self, elec_code, race_number, ward_num):
        html_string = self.fetch_precinct_results_html(elec_code, race_number,
            ward_num)
        results = self._parser.parse(html_string)
        return [self.create_result(rd, ward_num) for rd in results]

# TODO: Remove this if Abe's not using it, or reimplement it using
# PrecinctClient
def get_precincts_for_ward(ward):
    tmpl = 'http://www.chicagoelections.com/en/pctlevel3.asp?Ward=%d&elec_code=%s&race_number=%d'
    precincts = []
    # The 2015 mayoral primary code
    election_code = 10
    # Mayoral (primary?) race number
    race_number = 10
    precinct = {}

    text = requests.get(tmpl % (ward, election_code, race_number)).text
    for tr_idx, tr in enumerate(html.fromstring(text).xpath('/html/body/table[1]/tr')):
        if tr_idx == 0:
            # This is a blank row, so skip
            headers = []
            continue
        if precinct:
            precincts.append(precinct)
        precinct = {}
        for td_idx, td in enumerate(tr.xpath('td')):
            if tr_idx == 1:
                # This is the header row
                headers.append(td.text_content().strip())
            elif td_idx == 0:
                if td.text_content() == 'Total':
                    # We're done, so exit
                    return precincts
                else:
                    precinct['id'] = '%02d%03d' % (ward, int(td.text_content().strip()))
            elif headers[td_idx] == '%':
                continue
            else:
                try:
                    precinct[headers[td_idx]] = int(td.text_content().strip())
                except:
                    print 'Error with line %d, col %d (%s)' % (tr_idx, td_idx, headers[td_idx])
                    precinct[headers[td_idx]] = 0

if __name__ == '__main__':
    # TODO: Remove this if Abe's not using it, or reimplement it using
    # PrecinctClient
    precincts = []
    for ward in range(1, 51):
        precincts.extend(get_precincts_for_ward(ward))
    print json.dumps(precincts)
